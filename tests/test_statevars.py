import numpy as np

from regime_quant.config import MOM_MAIN, REV_MAIN, StateParams, kappa_LH, min_dwell, pairs_in_window
from regime_quant.inference import theta_test
from regime_quant.rolling import roll_sum
from regime_quant.statemachine import hysteresis, segments
from regime_quant.statevars import (concentration, exclusion_mask, flag_sets, loo_factor_regress, mean_sq_corr, mr_stat, null_c_threshold,
                                    scalar_rolling_ols, standardise)
from regime_quant.world import Theta, WorldSpec, generate, kernel, rho_theory, solve_states


def test_kappa_values_match_doc():
    assert abs(kappa_LH(20, 5) - 4.6) < 1e-12
    assert abs(kappa_LH(5, 3) - 2.4666666) < 1e-6
    assert kappa_LH(1, 1) == 1.0
    assert abs(kappa_LH(60, 20) - 17.78) < 0.01


def test_pairs_and_dwell():
    assert pairs_in_window(MOM_MAIN) == 200 - 20 - 5 + 1
    assert min_dwell(MOM_MAIN) == 5 and min_dwell(REV_MAIN) == 5


def test_standardise_uses_only_the_past():
    rng = np.random.default_rng(0)
    r = rng.standard_normal((300, 4)) * 0.01
    a, _ = standardise(r)
    r2 = r.copy()
    r2[200:] *= 50.0
    b, _ = standardise(r2)
    assert np.allclose(a[:200], b[:200], equal_nan=True)
    # the shock at t = 200 is divided by the OLD sigma, hence clipped at the cap
    assert np.nanmax(np.abs(b[200])) <= 5.0 + 1e-12


def test_mr_stat_bias_is_negative_and_scales_like_sqrt_LH_over_T():
    r = np.random.default_rng(1).standard_normal((3000, 30))
    for spec in (MOM_MAIN, REV_MAIN):
        st = mr_stat(r, spec)
        T = pairs_in_window(spec)
        assert abs(np.nanmean(st.rho) + np.sqrt(spec.L * spec.H) / T) < 0.012


def test_mr_stat_detects_planted_autocorrelation():
    rng = np.random.default_rng(2)
    T, N = 1500, 30
    e = rng.standard_normal((T, N))
    x = np.zeros((T, N))
    for t in range(1, T):
        x[t] = 0.4 * x[t - 1] + e[t]  # AR(1): positive short-lag autocorrelation
    st = mr_stat(x, REV_MAIN)  # rho^(5,3) > 0, i.e. R < 0
    bias = -np.sqrt(REV_MAIN.L * REV_MAIN.H) / pairs_in_window(REV_MAIN)
    assert np.nanmean(st.rho[500:]) - bias > 0.1


def test_hysteresis_semantics():
    tau = np.array([0, 0, 2.0, 0.9, 0.9, 0.3, 2.0, 0.3, 0.3, 0.3, 0.3])
    d, _ = hysteresis(tau, 1.28, 0.5, d_min=1)
    assert list(d) == [0, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    d3, _ = hysteresis(tau, 1.28, 0.5, d_min=3)
    # switch on at t=2, locked for t=2,3,4; off allowed at t=5; the next on at t=6 is locked (5->8); off at t=8? on at 6 blocked
    assert list(d3) == [0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    dn, v = hysteresis(np.array([np.nan, np.nan, 2.0]), 1.28, 0.5, 1)
    assert list(v) == [False, False, True] and list(dn) == [0, 0, 1]


def test_segments():
    lab = np.array(["I", "I", "IV", "I", "I", "I"], dtype=object)
    assert segments(lab, "I", 1) == [(0, 2), (3, 6)]
    assert segments(lab, "I", 3) == [(3, 6)]


def test_flag_set_single_event_is_feasible_for_wide_panel():
    """One asset with a 6x abnormal ratio in a 40-asset panel must be flaggable (the doc's 50%-of-u-mass rule is not)."""
    rng = np.random.default_rng(3)
    T, N = 400, 40
    e = rng.standard_normal((T, N)) * 0.01
    e[-6:, 7] *= 6.0
    conc = concentration(e)
    sp = StateParams()
    assert conc.flagged[-1, 7]
    assert conc.flagged[-1].sum() == 1
    assert not conc.flagged[:250].any()
    mass = conc.p[-1, 7]
    assert mass < 0.5  # the doc's rule would have returned an empty set


def test_exclusion_mask_window():
    F = np.zeros((20, 3), dtype=bool)
    F[5, 1] = True
    m = exclusion_mask(F, 4)
    assert list(np.flatnonzero(m[:, 1])) == [5, 6, 7, 8]
    assert not m[:, 0].any()


def test_null_c_threshold_decreases_with_n():
    a = null_c_threshold(10, 6.0, n_rep=300)
    b = null_c_threshold(40, 6.0, n_rep=300)
    assert a > b > 0


def test_rolling_ols_matches_numpy():
    rng = np.random.default_rng(4)
    x = rng.standard_normal(400)
    y = 0.5 + 2.0 * x + 0.1 * rng.standard_normal(400)
    a, b = scalar_rolling_ols(x, y, 100, 50, lag=1)
    sl = slice(299, 399)
    coef = np.polyfit(x[sl], y[sl], 1)
    assert abs(b[399] - coef[0]) < 1e-9 and abs(a[399] - coef[1]) < 1e-9


def test_closed_form_matches_simulation():
    th = Theta(s=0.3, phi=0.9, f=0.0, a=0.5)
    g0, g = kernel(th.s, th.phi, th.f, th.a)
    assert abs(g0 - 1.0) < 1e-12
    # lag-k autocovariance of the simulated return series
    w = generate(WorldSpec(kind="regime", effect=0.1, states_used=(0,), mean_dwell=(1e6,) * 4, n_days=6000, n_assets=40, seed=11))
    s = solve_states(0.1)["I"]
    g0, g = kernel(s.s, s.phi, s.f, s.a)
    r = w.ret / np.nanstd(w.ret, axis=0)
    ac1 = np.mean([np.corrcoef(r[1:, i], r[:-1, i])[0, 1] for i in range(40)])
    assert abs(ac1 - g[0] / g0) < 0.03


def test_solve_states_hits_planted_effects():
    th = solve_states(0.1)
    n = th["I"].nets()
    assert abs(n["M-B"] - 0.1) < 1e-6 and abs(th["II"].nets()["R-A"] - 0.1) < 1e-6
    assert abs(th["IV"].nets()["M-B"]) < 1e-12


def test_theta_test_centering_removes_pure_tilt():
    """E[s] != 0 and E[D] != 0 but no timing: raw Theta is positive, the centred decision rule must not fire."""
    rng = np.random.default_rng(5)
    n = 2200
    s = np.zeros(n)
    t = 0
    while t < n:
        d = int(rng.integers(30, 120))
        s[t : t + d] = rng.choice([-1.0, 0.0, 1.0], p=[0.1, 0.2, 0.7])
        t += d
    D = 0.2 + rng.standard_normal(n)
    fires = [theta_test(s, 0.2 + np.random.default_rng(k).standard_normal(n), rng=np.random.default_rng(k)).detect for k in range(40)]
    assert np.mean(fires) <= 0.12
    assert s.mean() > 0.2
