import numpy as np
import pandas as pd

from regime_quant.backtest import build_legs, run_leg
from regime_quant.benchmarks import risk_standardise, spread_d
from regime_quant.config import CostParams, InferenceParams, ProxyParams, StrategyParams
from regime_quant.diagnostics import expanding_tercile_bins, state_proxies, variance_ratio
from regime_quant.signals import ex_ante_vol, momentum_weights, reversal_weights
from regime_quant.synthetic import generate

SP, CP = StrategyParams(), CostParams()


def test_generator_reproducible_and_seed_sensitive():
    a = generate("regime", n_days=500, seed=3)
    b = generate("regime", n_days=500, seed=3)
    c = generate("regime", n_days=500, seed=4)
    pd.testing.assert_frame_equal(a.returns, b.returns)
    assert (a.states == b.states).all()
    assert not a.returns.equals(c.returns)


def test_null_const_has_single_state_and_regime_has_three():
    assert generate("null_const", n_days=300, seed=0).states.nunique() == 1
    assert generate("regime", n_days=3000, seed=0).states.nunique() == 3


def test_regimes_have_designed_microstructure():
    m = generate("regime", n_days=30000, seed=0)
    names, r = m.state_names, m.returns
    st = m.states.to_numpy()
    rushed = names.index("rushed")
    x = r.to_numpy()
    mask = (st[1:] == rushed) & (st[:-1] == rushed)
    ac = np.corrcoef(x[1:][mask].ravel(), x[:-1][mask].ravel())[0, 1]
    assert ac < -0.1  # negative lag-1 autocorrelation in the rushed state
    vol = {n: x[st == i].std() for i, n in enumerate(names)}
    assert vol["rushed"] > vol["slow"] > vol["calm"]


def test_weights_are_point_in_time():
    r = generate("regime", n_days=800, seed=1).returns
    t0 = 500
    future_changed = r.copy()
    future_changed.iloc[t0 + 1 :] = future_changed.iloc[t0 + 1 :] * 3 + 0.01
    for fn in (momentum_weights, reversal_weights):
        w_full = fn(r, SP).iloc[: t0 + 1]
        w_alt = fn(future_changed, SP).iloc[: t0 + 1]
        pd.testing.assert_frame_equal(w_full, w_alt)


def test_diagnostics_are_point_in_time():
    r = generate("regime", n_days=900, seed=1).returns
    pp = ProxyParams()
    t0 = 600
    alt = r.copy()
    alt.iloc[t0 + 1 :] = alt.iloc[t0 + 1 :] * 5
    p1, p2 = state_proxies(r, pp), state_proxies(alt, pp)
    pd.testing.assert_frame_equal(p1.iloc[: t0 + 1], p2.iloc[: t0 + 1])
    b1 = expanding_tercile_bins(p1["vr_short"], pp.bin_min_obs)
    b2 = expanding_tercile_bins(p2["vr_short"], pp.bin_min_obs)
    pd.testing.assert_series_equal(b1.iloc[: t0 + 1], b2.iloc[: t0 + 1])


def test_risk_standardisation_uses_only_past_vol():
    s = pd.Series(np.random.default_rng(0).standard_normal(300))
    base = risk_standardise(s, 60)
    s2 = s.copy()
    s2.iloc[200:] *= 10
    alt = risk_standardise(s2, 60)
    # the return on day 200 is itself scaled, but its denominator is unchanged
    assert np.isclose(alt.iloc[200] * 1.0, base.iloc[200] * 10)


def test_vectorised_pnl_matches_naive_loop():
    m = generate("regime", n_days=700, seed=2)
    r = m.returns
    w = momentum_weights(r, SP)
    vol = ex_ante_vol(r, SP.vol_window)
    res = run_leg(r, w, vol, CP)

    wv, rv, vv = w.fillna(0).to_numpy(), r.to_numpy(), vol.to_numpy()
    prev = np.zeros(r.shape[1])
    gross, cost = [], []
    for t in range(len(r)):
        held = wv[t - 1] if t > 0 else np.zeros(r.shape[1])
        gross.append(float(held @ rv[t]))
        vprev = np.nan_to_num(vv[t - 1]) if t > 0 else np.zeros(r.shape[1])
        cost.append(float((np.abs(held - prev) * (CP.fee_bps / 1e4 + CP.slip_vol_frac * vprev)).sum()))
        prev = held
    np.testing.assert_allclose(res.gross.to_numpy(), gross, atol=1e-12)
    np.testing.assert_allclose(res.cost.to_numpy(), cost, atol=1e-12)


def test_no_position_before_warmup():
    r = generate("regime", n_days=400, seed=0).returns
    res = build_legs(r, SP, CP)["mom"]
    warm = max(SP.mom_lookback + SP.mom_hold, SP.vol_window)
    assert res.gross.iloc[: warm - 1].abs().sum() == 0.0


def test_spread_d_finite_and_aligned():
    m = generate("regime", n_days=1500, seed=5)
    d = spread_d(build_legs(m.returns, SP, CP), SP)
    assert d.index.equals(m.returns.index)
    assert np.isfinite(d.dropna()).all()


def test_variance_ratio_detects_autocorrelation():
    rng = np.random.default_rng(0)
    n = 4000
    iid = pd.DataFrame(rng.standard_normal((n, 4)))
    mr = iid.copy()
    for t in range(1, n):
        mr.iloc[t] = -0.4 * mr.iloc[t - 1] + iid.iloc[t]
    assert variance_ratio(iid, 5, 250).mean() > variance_ratio(mr, 5, 250).mean() + 0.2
