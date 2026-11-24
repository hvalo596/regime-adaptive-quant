import numpy as np
import pandas as pd
import pytest

from regime_quant.data.fake_tushare import FakeTushareTransport, make_synthetic_futures
from regime_quant.data.flags import add_flags
from regime_quant.data.panel import PanelParams, build_panel
from regime_quant.data.roll import RollParams, build_continuous
from regime_quant.data.store import RawStore, fetch_universe
from regime_quant.data.tushare_client import MissingTokenError, RateLimiter, TushareClient, TushareConfig, http_transport
from regime_quant.world import WorldSpec, generate

PRODUCTS = ["RB", "CU", "AU", "IF"]


@pytest.fixture(scope="module")
def synth():
    w = generate(WorldSpec(kind="regime", n_assets=4, n_days=700, effect=0.1, seed=3))
    return make_synthetic_futures(w, PRODUCTS, seed=3, index_products=("IF",))


def _daily_dt(synth):
    d = synth.daily.copy()
    d["trade_date"] = pd.to_datetime(d["trade_date"], format="%Y%m%d")
    return d


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


def test_official_endpoint_only():
    from regime_quant.data.tushare_client import ENDPOINT

    assert ENDPOINT == "http://api.tushare.pro"


def test_paging_recovers_full_history_under_small_row_cap(synth):
    caps = {"fut_daily": 40, "fut_mapping": 100}
    tr = FakeTushareTransport(synth, caps=caps)
    client = TushareClient(TushareConfig(token="x", max_calls_per_min=10**6), transport=tr, sleep=lambda s: None, row_caps=caps)
    code = synth.daily.groupby("ts_code").size().idxmax()
    got = client.fut_daily(code, start="20100101", end="20301231")
    want = synth.daily[synth.daily["ts_code"] == code].sort_values("trade_date").reset_index(drop=True)
    assert len(want) > 40
    pd.testing.assert_frame_equal(got[want.columns], want, check_dtype=False)
    assert client.n_calls > 1


def test_rate_limiter_spaces_calls():
    t = {"now": 0.0}
    sleeps = []
    lim = RateLimiter(60, clock=lambda: t["now"], sleep=lambda s: (sleeps.append(s), t.__setitem__("now", t["now"] + s)))
    for _ in range(3):
        lim.wait()
    assert sleeps == [1.0, 1.0]


def test_fetch_universe_is_resumable_and_token_not_logged(tmp_path, synth):
    tr = FakeTushareTransport(synth)
    client = TushareClient(TushareConfig(token="tok-123", max_calls_per_min=10**6), transport=tr, sleep=lambda s: None)
    store = RawStore(tmp_path)
    log1 = fetch_universe(client, store, ["RB"], start="20100101", progress=lambda *_: None)
    n1 = client.n_calls
    log2 = fetch_universe(client, store, ["RB"], start="20100101", progress=lambda *_: None)
    assert log2["skipped_cached"] == log1["contracts"] and client.n_calls - n1 <= 2
    assert "tok-123" not in (tmp_path / "fetch_log.json").read_text()


def test_roll_adjusted_return_recovers_spot_and_removes_roll_jumps(synth):
    d = _daily_dt(synth)
    cont, diag = build_continuous("RB", synth.basic, d, None, RollParams(rule="oi"))
    spot = np.expm1(synth.spot_returns["RB"]).reindex(cont.index)
    ok = cont["ret"].notna()
    resid = cont.loc[ok, "ret"] - spot[ok]
    assert abs(resid.mean() + synth.carry / 365.0) < 2e-4
    assert resid.std() < 0.004
    assert np.corrcoef(cont.loc[ok, "ret"], spot[ok])[0, 1] > 0.95
    assert diag["n_rolls"] > 15 and diag["mean_abs_unadj_roll_jump"] > 0.003
    after = cont.loc[cont.index[cont["roll_flag"]], "ret"] - spot[cont.index[cont["roll_flag"]]]
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
    assert (np.diff(e.values.astype("int64")) >= 0).all()
    assert (cont["days_to_expiry"].dropna() >= p.expiry_buffer_days).all()


def test_auto_rule_uses_oi_where_official_mapping_mismatches(synth):
    d = _daily_dt(synth)
    for prod, expected in (("RB", "official"), ("IF", "oi")):
        mp = synth.mapping[synth.mapping["ts_code"].str.startswith(prod + ".")]
        _, diag = build_continuous(prod, synth.basic, d, mp, RollParams(rule="auto"))
        assert diag["rule_used"] == expected, (prod, diag["official_agreement"])


def test_contaminated_mapping_is_ignored(synth):
    d = _daily_dt(synth)
    foreign = synth.mapping[synth.mapping["ts_code"].str.startswith("CU.")].copy()
    _, diag = build_continuous("RB", synth.basic, d, foreign, RollParams(rule="auto"))
    assert diag["rule_used"] == "oi" and np.isnan(diag["official_agreement"])


def test_flags_mark_one_price_and_limit_proxy():
    idx = pd.bdate_range("2020-01-01", periods=4)
    c = pd.DataFrame({"ret": 0.0, "roll_flag": False, "stale": False, "days_to_expiry": 100.0, "h_close": [100.0, 107.0, 100.0, 100.0],
                      "h_high": [101.0, 107.0, 100.5, 100.0], "h_low": [99.0, 107.0, 99.5, 100.0], "h_pre_settle": 100.0, "h_vol": [10, 10, 10, 0]}, index=idx)
    f = add_flags(c, "RB", min_move=0.03)
    assert f["one_price"].tolist() == [False, True, False, False]
    assert f["limit_locked_proxy"].tolist() == [False, True, False, False]


def test_panel_liquidity_latch_is_point_in_time(synth):
    d = _daily_dt(synth)
    mp = {p: synth.mapping[synth.mapping["ts_code"].str.startswith(p + ".")] for p in PRODUCTS[:3]}
    pan = build_panel(PRODUCTS[:3], synth.basic, d, mp, panel_params=PanelParams())
    first = pan.returns.apply(lambda s: s.first_valid_index())
    assert (first > pan.returns.index[PanelParams().liq_window - 1]).all()
    assert {"h_settle", "h_open", "h_pre_close"} <= set(pan.continuous["RB"].columns)


def test_fetch_settle_roundtrip_and_events(tmp_path, synth):
    from regime_quant.data.store import fetch_settle
    from regime_quant.nondefining import margin_events_from_settle

    tr = FakeTushareTransport(synth)
    client = TushareClient(TushareConfig(token="x", max_calls_per_min=10**6), transport=tr, sleep=lambda s: None)
    store = RawStore(tmp_path)
    dates = [d.strftime("%Y%m%d") for d in pd.bdate_range("2012-02-20", "2012-04-20")]
    assert fetch_settle(client, store, dates, ["SHFE"]) == []
    st = store.read("fut_settle.csv.gz")
    idx = pd.bdate_range("2012-02-20", "2012-04-20")
    code = st[st["ts_code"].str.startswith("RB")]["ts_code"].iloc[0]
    held = pd.DataFrame({"RB": code}, index=idx)
    ev = margin_events_from_settle(st, held)
    assert ev["RB"].sum() == 1  # the planted step up (Feb -> March), the step down in April is not a hike
