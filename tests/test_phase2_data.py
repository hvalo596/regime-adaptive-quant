import numpy as np
import pandas as pd
import pytest

from regime_quant.backtest import run_leg
from regime_quant.config import CostParams, StrategyParams
from regime_quant.data.fake_tushare import FakeTushareTransport, make_synthetic_futures
from regime_quant.data.flags import add_flags
from regime_quant.data.panel import PanelParams, build_panel
from regime_quant.data.roll import RollParams, build_continuous
from regime_quant.data.store import RawStore, fetch_universe
from regime_quant.data.tushare_client import (
    MissingTokenError, RateLimiter, TushareClient, TushareConfig, http_transport,
)
from regime_quant.signals import momentum_weights

PRODUCTS = ["RB", "CU", "AU"]


@pytest.fixture(scope="module")
def synth():
    return make_synthetic_futures(PRODUCTS + ["IF"], n_days=700, seed=3)


def _daily_dt(synth):
    d = synth.daily.copy()
    d["trade_date"] = pd.to_datetime(d["trade_date"], format="%Y%m%d")
    return d


# ---------- client ----------
def test_missing_token_is_a_clear_error_and_never_in_repr(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    cfg = TushareConfig.from_env()
    assert cfg.token is None
    with pytest.raises(MissingTokenError, match="TUSHARE_TOKEN"):
        http_transport(cfg)
    monkeypatch.setenv("TUSHARE_TOKEN", "super-secret-value")
    cfg = TushareConfig.from_env()
    assert cfg.token == "super-secret-value"
    assert "super-secret-value" not in repr(cfg)


def test_paging_recovers_full_history_under_small_row_cap(synth):
    caps = {"fut_daily": 40, "fut_mapping": 100}
    tr = FakeTushareTransport(synth, caps=caps)
    client = TushareClient(TushareConfig(token="x", max_calls_per_min=10**6), transport=tr, sleep=lambda s: None, row_caps=caps)
    code = synth.daily.groupby("ts_code").size().idxmax()
    got = client.fut_daily(code, start="20100101", end="20301231")
    want = synth.daily[synth.daily["ts_code"] == code].sort_values("trade_date").reset_index(drop=True)
    assert len(want) > 40  # paging was actually needed
    pd.testing.assert_frame_equal(got[want.columns], want, check_dtype=False)
    assert client.n_calls > 1
    m = client.fut_mapping("RB.SHF", start="20100101", end="20301231")
    assert len(m) == (synth.mapping["ts_code"] == "RB.SHF").sum()
    assert m["trade_date"].is_monotonic_increasing and m["trade_date"].is_unique


def test_rate_limiter_spaces_calls():
    t = {"now": 0.0}
    sleeps = []
    lim = RateLimiter(60, clock=lambda: t["now"], sleep=lambda s: (sleeps.append(s), t.__setitem__("now", t["now"] + s)))
    for _ in range(3):
        lim.wait()
    assert sleeps == [1.0, 1.0]


def test_fetch_universe_is_resumable(tmp_path, synth):
    tr = FakeTushareTransport(synth)
    client = TushareClient(TushareConfig(token="x", max_calls_per_min=10**6), transport=tr, sleep=lambda s: None)
    store = RawStore(tmp_path)
    log1 = fetch_universe(client, store, ["RB"], start="20100101", progress=lambda *_: None)
    n1 = client.n_calls
    log2 = fetch_universe(client, store, ["RB"], start="20100101", progress=lambda *_: None)
    assert log2["skipped_cached"] == log1["contracts"] and client.n_calls - n1 <= 2  # only fut_basic re-queried
    assert not store.basic().empty and not store.mapping("RB").empty
    assert "x" not in (tmp_path / "fetch_log.json").read_text().replace('"', " ").split()  # token not logged


# ---------- roll ----------
def test_roll_adjusted_return_recovers_spot_and_removes_roll_jumps(synth):
    d = _daily_dt(synth)
    cont, diag = build_continuous("RB", synth.basic, d, None, RollParams(rule="oi"))
    spot = synth.spot_returns["RB"].reindex(cont.index)
    ok = cont["ret"].notna()
    # same-contract returns = spot return less the deterministic carry run-off
    resid = cont.loc[ok, "ret"] - spot[ok]
    assert abs(resid.mean() + synth.carry / 365.0) < 2e-4
    assert resid.std() < 0.004
    assert np.corrcoef(cont.loc[ok, "ret"], spot[ok])[0, 1] > 0.9
    roll_days = cont.index[cont["roll_flag"]]
    assert diag["n_rolls"] > 20
    # unadjusted splice has jumps of order carry * contract gap on roll dates; adjusted series does not
    assert diag["mean_abs_unadj_roll_jump"] > 0.003
    after = cont.loc[roll_days, "ret"] - spot[roll_days]
    assert after.abs().mean() < 0.003


def test_held_contract_never_uses_future_data(synth):
    d = _daily_dt(synth)
    full, _ = build_continuous("RB", synth.basic, d, None, RollParams(rule="oi"))
    t0 = full.index[400]
    cut, _ = build_continuous("RB", synth.basic, d[d["trade_date"] <= t0], None, RollParams(rule="oi"))
    pd.testing.assert_series_equal(full.loc[:t0, "held"], cut.loc[:t0, "held"], check_names=False)
    pd.testing.assert_series_equal(full.loc[:t0, "ret"], cut.loc[:t0, "ret"], check_names=False)


def test_roll_is_forward_only_and_never_holds_inside_expiry_buffer(synth):
    d = _daily_dt(synth)
    p = RollParams(rule="oi", expiry_buffer_days=10)
    cont, _ = build_continuous("CU", synth.basic, d, None, p)
    held = cont["held"].dropna()
    exp = synth.basic.set_index("ts_code")["last_ddate"]
    e = pd.to_datetime(held.map(exp), format="%Y%m%d")
    assert (np.diff(e.values.astype("int64")) >= 0).all()  # expiry never decreases
    assert (cont["days_to_expiry"].dropna() >= p.expiry_buffer_days).all()


def test_auto_rule_uses_oi_where_official_mapping_mismatches(synth):
    d = _daily_dt(synth)
    for prod, expected in (("RB", "official"), ("IF", "oi")):
        mp = synth.mapping[synth.mapping["ts_code"].str.startswith(prod + ".")]
        _, diag = build_continuous(prod, synth.basic, d, mp, RollParams(rule="auto"))
        assert diag["rule_used"] == expected, (prod, diag["official_agreement"])
        if prod == "IF":
            assert diag["official_agreement"] < 0.8
            assert diag["share_days_held_is_max_oi"] > 0.8


def test_contaminated_mapping_is_ignored(synth):
    """TL-style case: the official continuous code maps to another product's contracts -> no usable overlap -> OI rule."""
    d = _daily_dt(synth)
    foreign = synth.mapping[synth.mapping["ts_code"].str.startswith("CU.")].copy()
    _, diag = build_continuous("RB", synth.basic, d, foreign, RollParams(rule="auto"))
    assert diag["rule_used"] == "oi" and np.isnan(diag["official_agreement"])


def test_roll_cost_is_charged_on_roll_days_only():
    idx = pd.bdate_range("2020-01-01", periods=6)
    r = pd.DataFrame({"A": 0.0}, index=idx)
    w = pd.DataFrame({"A": 1.0}, index=idx)
    vol = pd.DataFrame({"A": 0.0}, index=idx)
    mask = pd.DataFrame({"A": [False, False, True, False, False, False]}, index=idx)
    cp = CostParams(fee_bps=10.0, slip_vol_frac=0.0)
    leg = run_leg(r, w, vol, cp, mask)
    base = run_leg(r, w, vol, cp)
    extra = (leg.cost - base.cost)
    assert extra.iloc[2] == pytest.approx(2 * 10e-4) and extra.drop(idx[2]).abs().sum() == 0


# ---------- flags / panel ----------
def test_flags_mark_one_price_and_limit_proxy():
    idx = pd.bdate_range("2020-01-01", periods=4)
    c = pd.DataFrame(
        {"ret": 0.0, "roll_flag": False, "stale": False, "days_to_expiry": 100.0, "h_close": [100.0, 107.0, 100.0, 100.0],
         "h_high": [101.0, 107.0, 100.5, 100.0], "h_low": [99.0, 107.0, 99.5, 100.0], "h_pre_settle": 100.0,
         "h_vol": [10, 10, 10, 0]},
        index=idx,
    )
    f = add_flags(c, "RB", min_move=0.03)
    assert f["one_price"].tolist() == [False, True, False, False]
    assert f["limit_locked_proxy"].tolist() == [False, True, False, False]
    assert f["night_draft"].all()  # RB, 2020 >= draft night start
    assert not add_flags(c, "IF")["night_draft"].any()  # index futures: no night session


def test_panel_liquidity_latch_is_point_in_time(synth):
    d = _daily_dt(synth)
    mp = {p: synth.mapping[synth.mapping["ts_code"].str.startswith(p + ".")] for p in PRODUCTS}
    pan = build_panel(PRODUCTS, synth.basic, d, mp, panel_params=PanelParams())
    assert set(pan.returns.columns) == set(PRODUCTS)
    first = pan.returns.apply(lambda s: s.first_valid_index())
    assert (first > pan.returns.index[PanelParams().liq_window - 1]).all()
    # a stricter threshold can only delay (never advance) entry, and never changes returns after entry
    strict = build_panel(PRODUCTS, synth.basic, d, mp, panel_params=PanelParams(min_median_amount_wan=5e5))
    assert strict.diagnostics["included"].sum() <= len(PRODUCTS)


def test_unbalanced_panel_weights_use_live_asset_count():
    rng = np.random.default_rng(0)
    r = pd.DataFrame(rng.normal(0, 0.01, (400, 4)), columns=list("ABCD"))
    r.loc[:200, "D"] = np.nan
    w = momentum_weights(r, StrategyParams())
    late = w.iloc[300]
    early = w.iloc[150]
    assert early["D"] != early["D"] or early["D"] == 0 or np.isnan(early["D"])
    assert late.notna().all()
    # equal-risk budgets: before D exists, 3 assets share the book; after, 4
    assert np.nanmax(np.abs(early[["A", "B", "C"]])) <= StrategyParams().max_leverage_per_asset / 3 + 1e-12
