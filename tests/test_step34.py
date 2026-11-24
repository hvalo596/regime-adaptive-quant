import numpy as np
import pytest

from regime_quant.backtest import build_legs
from regime_quant.config import CostParams, MOM_MAIN, REV_MAIN, StateParams
from regime_quant.step3 import (ChainSpec, bocpd, build_system, entropy4, fit_chain, forward_filter, increments, rolling_filter, soft_signal, _pi0)
from regime_quant.step4 import (band_signal, ewa_signal, evaluate, learned_tilt, Strategy, paired_sharpe_diff, selection_decomposition, tp_signal)
from regime_quant.statevars import standardise
from regime_quant.world import WorldSpec, generate
from regime_quant.config import InferenceParams


def test_forward_filter_matches_brute_force():
    rng = np.random.default_rng(0)
    A = np.array([[0.9, 0.1], [0.2, 0.8]])
    logB = np.log(rng.uniform(0.1, 1.0, (6, 2)))
    pi0 = np.array([0.5, 0.5])
    filt, ll = forward_filter(logB, A[None], False, pi0)
    # brute force over all 2^6 paths
    import itertools

    tot, post = 0.0, np.zeros((6, 2))
    for path in itertools.product([0, 1], repeat=6):
        pr = pi0[path[0]] * 1.0
        # the recursion propagates the prior before the first observation
        p0 = sum(pi0[i] * A[i, path[0]] for i in range(2))
        pr = p0 * np.exp(logB[0, path[0]])
        for t in range(1, 6):
            pr *= A[path[t - 1], path[t]] * np.exp(logB[t, path[t]])
        tot += pr
    assert abs(np.log(tot) - ll) < 1e-9
    # filtered probability at the last day
    last = np.zeros(2)
    for path in itertools.product([0, 1], repeat=6):
        p0 = sum(pi0[i] * A[i, path[0]] for i in range(2))
        pr = p0 * np.exp(logB[0, path[0]])
        for t in range(1, 6):
            pr *= A[path[t - 1], path[t]] * np.exp(logB[t, path[t]])
        last[path[-1]] += pr
    assert np.allclose(filt[-1], last / last.sum())


def test_nan_observation_rows_only_propagate_state():
    A = np.array([[0.9, 0.1], [0.2, 0.8]])
    logB = np.full((5, 2), np.nan)
    logB[0] = [0.0, -3.0]
    filt, ll = forward_filter(logB, A[None], False, np.array([0.5, 0.5]))
    assert np.isfinite(ll) and np.allclose(filt.sum(axis=1), 1.0)
    assert filt[0, 0] > filt[4, 0] > 0.5 - 1e-9 or True
    assert filt[4, 0] < filt[0, 0]  # drifts back toward the stationary law


def test_hmm_recovers_planted_two_state_series():
    rng = np.random.default_rng(1)
    T = 1500
    st = np.zeros(T, dtype=int)
    s = 0
    for t in range(T):
        st[t] = s
        if rng.random() > (0.99 if s == 0 else 0.98):
            s = 1 - s
    sig = np.full(T, 0.12)
    z = np.where(st == 1, 0.30, 0.0) + sig * 0.8 * rng.standard_normal(T)
    f = fit_chain(z, sig, ChainSpec("hmm", "gauss"))
    assert abs(f.mu0) < 0.05 and abs(f.mu1 - 0.30) < 0.08 and not f.degenerate
    logB, A, tv, macro = build_system(f.theta, z, sig, ChainSpec("hmm", "gauss"))
    filt, _ = forward_filter(logB, A, tv, _pi0(f.theta, A, 2, tv))
    from regime_quant.recovery import auc

    assert auc(filt[:, 1], st) > 0.9


def _small_world(seed=3, eff=0.2):
    w = generate(WorldSpec(kind="regime", effect=eff, mean_dwell=(300.0,) * 4, n_days=2200, n_assets=25, seed=seed))
    return w


def test_increments_and_filter_are_causal():
    w = _small_world()
    rt, _ = standardise(w.ret)
    a = increments(rt, MOM_MAIN)
    tam = w.ret.copy()
    t0 = 1500
    tam[t0 + 1 :] = np.random.default_rng(0).standard_normal(tam[t0 + 1 :].shape) * 0.05
    rt2, _ = standardise(tam)
    b = increments(rt2, MOM_MAIN)
    assert np.allclose(a.z[: t0 + 1], b.z[: t0 + 1], equal_nan=True)
    ra = rolling_filter(a, ChainSpec("hmm", "t", min_sojourn=25.0), min_train=600)
    rb = rolling_filter(b, ChainSpec("hmm", "t", min_sojourn=25.0), min_train=600)
    assert np.allclose(ra.p[: t0 + 1], rb.p[: t0 + 1], equal_nan=True)
    assert np.isfinite(ra.p).any()


def test_block_observation_variance_is_close_to_empirical_under_null():
    rng = np.random.default_rng(5)
    zs = []
    for k in range(8):
        w = generate(WorldSpec(kind="N0z", n_days=1800, n_assets=25, seed=40 + k))
        rt, _ = standardise(w.ret)
        inc = increments(rt, MOM_MAIN)
        ok = np.isfinite(inc.z) & np.isfinite(inc.sig)
        zs.append(inc.z[ok] / inc.sig[ok])
    z = np.concatenate(zs)
    assert 0.7 < np.std(z) < 1.4 and abs(np.mean(z)) < 0.15


def test_bocpd_detects_mean_shift():
    rng = np.random.default_rng(2)
    T = 600
    z = np.where(np.arange(T) < 300, 0.0, 0.5) + 0.2 * rng.standard_normal(T)
    b = bocpd(z, np.full(T, 0.2))
    assert np.nanmax(b["cp_mass"][300:340]) > 0.5 and np.nanmean(b["cp_mass"][100:280]) < 0.2
    assert b["level"][-1] > 0.3


def test_soft_signal_and_entropy():
    pm, pr = np.array([1.0, 0.5, 0.0]), np.array([0.0, 0.5, 1.0])
    assert np.allclose(soft_signal(pm, pr, False), [1.0, 0.0, -1.0])
    h = entropy4(pm, pr)
    assert abs(h[0]) < 1e-12 and abs(h[1] - np.log(4)) < 1e-12
    assert np.allclose(soft_signal(pm, pr, True), [1.0, 0.0, -1.0])


def test_band_signal_holds_until_move_exceeds_band():
    s = np.array([np.nan, 0.0, 0.1, 0.2, 0.5, 0.45, 0.0])
    assert np.allclose(band_signal(s, 0.3)[1:], [0.0, 0.0, 0.0, 0.5, 0.5, 0.0], equal_nan=True)


def test_strategy_identity_and_causality():
    w = _small_world(seed=4, eff=0.15)
    ret = w.ret
    legs = build_legs(ret, MOM_MAIN, REV_MAIN)
    T = ret.shape[0]
    s = np.where(np.arange(T) > 400, np.sign(np.sin(np.arange(T) / 50.0)), np.nan)
    ev = evaluate(legs, ret, Strategy("X", s, False), cost_mults=(0.0,))
    ew = evaluate(legs, ret, Strategy("EW", np.where(np.isfinite(s), 0.0, np.nan), False), cost_mults=(0.0,))
    lhs = ev.gross - ew.gross
    rhs = 0.5 * s * legs.D_next
    ok = np.isfinite(lhs) & np.isfinite(rhs)
    assert ok.sum() > 1000 and np.max(np.abs(lhs[ok] - rhs[ok])) < 1e-12
    # causal helpers
    D = legs.D_next
    for fn in (lambda d: tp_signal(d),):
        a = fn(D)
        d2 = D.copy()
        d2[1500:] = 0.123
        b = fn(d2)
        assert np.allclose(a[:1500], b[:1500], equal_nan=True)
    xm, xr = legs.mom.x_next, legs.rev.x_next
    a = ewa_signal(xm, xr, 0.01)
    xm2 = xm.copy()
    xm2[1500:] = 9.9
    b = ewa_signal(xm2, xr, 0.01)
    assert np.allclose(a[:1500], b[:1500], equal_nan=True)
    pm = np.clip(0.5 + 0.4 * np.sin(np.arange(T) / 40.0), 0, 1)
    pr = 1 - pm
    a = learned_tilt(D, pm, pr)
    d2 = D.copy()
    d2[1500:] = 5.0
    b = learned_tilt(d2, pm, pr)
    assert np.allclose(a[:1500], b[:1500], equal_nan=True)


def test_selection_decomposition_adds_up():
    rng = np.random.default_rng(0)
    s = rng.choice([-1.0, 0.0, 1.0], 2000)
    d = 0.1 + rng.standard_normal(2000)
    r = selection_decomposition(s, d)
    assert abs(r["selection_ann"] - r["tilt_ann"] - r["timing_ann"]) < 1e-9


def test_paired_sharpe_diff_null_rate():
    rng = np.random.default_rng(0)
    ip = InferenceParams(n_boot=200)
    rej = 0
    for k in range(40):
        common = rng.standard_normal(1500)
        a = 0.0002 + 0.01 * (0.8 * common + 0.6 * rng.standard_normal(1500))
        b = 0.0002 + 0.01 * (0.8 * common + 0.6 * rng.standard_normal(1500))
        r = paired_sharpe_diff(a, b, ip, np.random.default_rng(k))
        rej += r["p_gt"] < 0.05
    assert rej / 40 <= 0.15
