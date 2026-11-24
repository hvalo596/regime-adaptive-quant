import numpy as np
import pandas as pd
import pytest

from regime_quant.audit import calendar_checks, extreme_days, night_session_break
from regime_quant.config import InferenceParams
from regime_quant.data.activity import product_activity
from regime_quant.hypotheses import h5_event_test
from regime_quant.nondefining import (abnormal_volume, b2_bootstrap, event_study, events_from_mask, llorente_stats, oi_growth, seat_panel, state_signature_table,
                                       zscore_own)
from regime_quant.step2 import Ledger, multiplicity_summary


def test_llorente_exact_planted_pair():
    rng = np.random.default_rng(3)
    T, N = 4000, 20
    r = rng.standard_normal((T, N))
    av = rng.standard_normal((T, N))
    series = np.zeros((T, N))
    series[0] = r[0]
    for t in range(T - 1):
        series[t + 1] = 0.2 * av[t] * series[t] + 0.5 * rng.standard_normal(N)
    stats = llorente_stats(series, av)
    res = b2_bootstrap(stats, np.ones(T, dtype=bool), InferenceParams(n_boot=100), np.random.default_rng(1))
    assert abs(res["b2"] - 0.2) < 0.05
    series2 = np.zeros((T, N))
    series2[0] = r[0]
    for t in range(T - 1):
        series2[t + 1] = -0.2 * av[t] * series2[t] + 0.5 * rng.standard_normal(N)
    res2 = b2_bootstrap(llorente_stats(series2, av), np.ones(T, dtype=bool), InferenceParams(n_boot=100), np.random.default_rng(1))
    assert res2["b2"] < -0.1 and res2["ci_hi"] < 0


def test_signature_table_and_zscore():
    rng = np.random.default_rng(1)
    n = 1500
    lab = np.array(["IV"] * n, dtype=object)
    lab[300:700] = "I"
    z = rng.standard_normal(n)
    z[300:700] += 1.0
    t = state_signature_table({"z": z}, lab, "IV", InferenceParams(n_boot=200, n_shift=300), np.random.default_rng(0))
    row = t[(t.state == "I")].iloc[0]
    assert row["diff"] > 0.8 and row["ci_lo"] > 0
    x = rng.standard_normal((600, 3))
    zz = zscore_own(x)
    assert np.isnan(zz[50]).all() and abs(np.nanstd(zz[400:])) < 1.3


def test_oi_growth_and_av_point_in_time():
    rng = np.random.default_rng(2)
    oi = np.exp(np.cumsum(rng.normal(0, 0.01, (500, 2)), axis=0)) * 1000
    a = oi_growth(oi)
    oi2 = oi.copy()
    oi2[300:] *= 3
    b = oi_growth(oi2)
    assert np.allclose(a[:300], b[:300], equal_nan=True)
    vol = np.exp(rng.normal(0, 0.3, (500, 2)))
    v2 = vol.copy()
    v2[400:] *= 5
    assert np.allclose(abnormal_volume(vol)[:400], abnormal_volume(v2)[:400], equal_nan=True)


def test_seat_panel_aggregation():
    idx = pd.bdate_range("2020-01-01", periods=12)
    oi = pd.DataFrame({"RB": 1000.0}, index=idx)
    rows = []
    for d in idx:
        for b in range(3):
            rows.append({"trade_date": d.strftime("%Y%m%d"), "symbol": "RB2005", "broker": f"B{b}", "long_hld": 100 + 10 * (d - idx[0]).days / 7, "short_hld": 50})
    out = seat_panel(pd.DataFrame(rows), oi, ["RB"], k=5)
    assert out["d_net_over_oi"]["RB"].iloc[-1] > 0
    assert out["d_gross_over_oi"]["RB"].iloc[:5].isna().all()


def test_events_and_event_study():
    T = 600
    mask = pd.DataFrame({"A": False}, index=range(T))
    mask.loc[[100, 105, 300], "A"] = True
    ev = events_from_mask(mask, min_gap=20)
    assert list(ev["A"]) == [100, 300]
    x = np.zeros(T)
    x[101:111] = 1.0
    x[301:311] = 1.0
    r = event_study(ev, {"A": x}, horizon=10, guard=20, ip=InferenceParams(n_boot=100))
    assert r["n_events"] == 2 or np.isnan(r["mean_diff"])


def test_h5_event_test_detects_planted_loss_and_not_noise():
    rng = np.random.default_rng(4)
    T, N = 1500, 30
    pnl = rng.standard_normal((T, N)) * 0.5
    excl = np.zeros((T, N), dtype=bool)
    for t0 in range(100, 1400, 90):
        excl[t0 : t0 + 9, int(rng.integers(0, N))] = True
    bad = pnl.copy()
    bad[excl] -= 0.5
    ip = InferenceParams(n_boot=200)
    assert h5_event_test(bad, excl, ip, np.random.default_rng(0))["reject"]
    fires = [h5_event_test(rng.standard_normal((T, N)) * 0.5, excl, ip, np.random.default_rng(k))["reject"] for k in range(30)]
    assert np.mean(fires) <= 0.15


def test_extreme_days_and_night_break_and_calendar():
    from regime_quant.data.panel import Panel

    idx = pd.bdate_range("2014-01-01", periods=1500)
    rng = np.random.default_rng(5)
    gap = np.where(idx < pd.Timestamp("2016-01-04"), 0.01, 0.004) * rng.standard_normal(len(idx))
    c = pd.DataFrame({"ret": rng.normal(0, 0.01, len(idx)), "unadj_ret": 0.0, "roll_flag": False, "stale": False, "h_close": 100.0, "h_low": 99.0, "h_high": 101.0,
                      "h_pre_settle": 100.0, "h_settle": 100.0, "h_vol": 10.0, "one_price": False, "held": "X", "h_open": 100 * np.exp(gap), "h_pre_close": 100.0}, index=idx)
    c.loc[idx[800], ["ret", "h_close", "h_low", "h_high"]] = [0.2, 125.0, 120.0, 124.0]  # close outside the day's range -> data error candidate
    pan = Panel(returns=pd.DataFrame({"RB": c["ret"]}), roll=None, limit_locked=None, one_price=None, stale=None, night_draft=None, extreme_ret=None, diagnostics=None, continuous={"RB": c})
    ed = extreme_days(pan)
    assert len(ed) == 1 and ed.iloc[0]["suspect"] == "data error candidate"
    nb = night_session_break(pan, draft={"RB": "2016-01-04"}, search_days=300)
    assert abs(nb.iloc[0]["days_from_draft"]) < 40 and nb.iloc[0]["var_ratio_post_over_pre"] < 0.4
    cal = calendar_checks(pd.DataFrame({"trade_date": pd.Series(idx).dt.strftime("%Y%m%d")}))
    assert cal["weekend_dates"] == 0


def test_multiplicity_summary():
    df = pd.DataFrame({"p_shift": [0.001] + [0.5] * 39})
    m = multiplicity_summary(df)
    assert m["n_reject_5pct"] == 1 and m["n_holm_reject"] == 1


def test_product_activity_sums_contracts():
    basic = pd.DataFrame({"ts_code": ["RB2001.SHF", "RB2005.SHF"], "fut_code": ["RB", "RB"]})
    daily = pd.DataFrame({"ts_code": ["RB2001.SHF", "RB2005.SHF"], "trade_date": pd.to_datetime(["2019-12-02", "2019-12-02"]), "oi": [100.0, 300.0], "vol": [1.0, 2.0], "amount": [5.0, 7.0]})
    act = product_activity(daily, basic, ["RB"])
    assert act["oi"].iloc[0, 0] == 400.0 and act["vol"].iloc[0, 0] == 3.0


def test_end_to_end_synthetic_fallback_and_blocked_path(tmp_path, monkeypatch):
    """The whole step-2 code path (fake Tushare -> cache -> own roll -> panel -> pipeline -> tests -> files) runs without a token;
    without data and without a token the real path stops with a BLOCKED note instead of inventing anything."""
    import subprocess
    import sys
    from pathlib import Path

    from regime_quant.step2 import synthetic_dataset
    from regime_quant.step2_run import run_all

    ds = synthetic_dataset("regime", 0.2, n_days=1400, seed=11, n_commodity=9)
    assert ds.source == "synthetic" and "commodity" in ds.panels
    summ = run_all(ds, tmp_path / "out", scale=0.05)
    for f in ("hypotheses.csv", "theta_by_panel.csv", "trial_ledger.csv", "power_real_dims.csv", "nondefining_signatures.csv", "audit_extreme_days_commodity.csv",
              "audit_night_session_commodity.csv", "per_product_theta.csv", "summary.json", "coverage_panel.csv", "coverage_products.csv"):
        assert (tmp_path / "out" / f).exists(), f
    assert "verdict" in summ["H0_commodity"]
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in __import__("os").environ.items() if k != "TUSHARE_TOKEN"}
    r = subprocess.run([sys.executable, str(root / "scripts" / "run_step2.py"), "--raw-dir", str(tmp_path / "nodata"), "--out", str(tmp_path / "blocked")], capture_output=True, text=True, env=env)
    assert r.returncode == 3 and (tmp_path / "blocked" / "BLOCKED.md").exists()
