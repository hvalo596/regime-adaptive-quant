import numpy as np
import pandas as pd
import pytest

from regime_quant.config import InferenceParams, ProxyParams
from regime_quant.data.fake_tushare import FakeTushareTransport, make_synthetic_futures
from regime_quant.data.store import RawStore, fetch_universe
from regime_quant.data.tushare_client import TushareClient, TushareConfig
from regime_quant.existence import (
    ExistenceParams, TrialLedger, circular_shift_null, existence_row, limit_adjacent_mask, segment_level_test,
)
from regime_quant.kai_dims import DIM_NAMES, dependence_report, kai_dims
from regime_quant.phase2 import run_phase2, write_artifacts


def _panel(n=900, k=8, seed=0, common_vol=0.01, idio_vol=0.01, heavy=None):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, common_vol, n)
    e = rng.normal(0, idio_vol, (n, k))
    if heavy is not None:
        e[:, 0] *= heavy
    return pd.DataFrame(f[:, None] + e, index=pd.bdate_range("2015-01-01", periods=n), columns=[f"A{i}" for i in range(k)])


def test_kai_dims_identity_and_ordering():
    d = kai_dims(_panel(), window=60)
    rep = dependence_report(d)
    assert rep["max_abs_identity_residual"] < 1e-9  # logit(share) == 2*(sys - idio): two degrees of freedom
    assert rep["vif"].max() > 5  # the draft trio is nearly collinear in sample; say so
    hi_common = kai_dims(_panel(common_vol=0.03), window=60)
    assert hi_common["sys_share"].mean() > d["sys_share"].mean() + 0.2
    assert hi_common["sys_level"].mean() > d["sys_level"].mean() + 0.5


def test_kai_concentration_detects_one_noisy_asset():
    even = kai_dims(_panel(seed=1), window=60)["idio_conc"].mean()
    conc = kai_dims(_panel(seed=1, heavy=6.0), window=60)["idio_conc"].mean()
    assert conc > even + 0.3 and 0 <= even <= 1 and conc <= 1


def test_kai_dims_are_point_in_time():
    r = _panel()
    t0 = 600
    alt = r.copy()
    alt.iloc[t0 + 1 :] = alt.iloc[t0 + 1 :] * 4 + 0.02
    pd.testing.assert_frame_equal(kai_dims(r).iloc[: t0 + 1], kai_dims(alt).iloc[: t0 + 1])


def test_kai_dims_need_enough_assets():
    r = _panel(k=3)
    d = kai_dims(r, window=60, min_assets=5)
    assert d[list(DIM_NAMES)].isna().all().all()


def _planted(effect, n=3000, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n)
    state = np.zeros(n)
    s = 0
    for t in range(n):
        if rng.random() < 0.02:
            s = rng.integers(0, 3)
        state[t] = s
    proxy = pd.Series(state + rng.normal(0, 0.3, n), index=idx)
    d = pd.Series(effect * (state - 1) + rng.normal(0, 1, n), index=idx)
    return proxy, d


EP = ExistenceParams(n_boot=300, n_shift=300)
IP, PP = InferenceParams(), ProxyParams(bin_min_obs=250)


def test_existence_row_finds_planted_effect_and_rejects_noise():
    rng = np.random.default_rng(1)
    proxy, d = _planted(0.8)
    hit = existence_row("vr_short", proxy, d, IP, EP, PP, n_primary=6, rng=rng)
    assert hit["verdict"] in ("pass (adj)", "pass (unadj only)") and hit["diff"] > 0.5
    assert hit["shift_p_two_sided"] < 0.2
    proxy0, d0 = _planted(0.0)
    miss = existence_row("vr_short", proxy0, d0, IP, EP, PP, n_primary=6, rng=rng)
    assert not miss["pass_adj"]


def test_existence_false_positive_rate_on_no_regime_noise_is_small():
    rng = np.random.default_rng(2)
    hits = 0
    for seed in range(25):
        r = np.random.default_rng(seed)
        idx = pd.bdate_range("2010-01-01", periods=2000)
        proxy = pd.Series(np.cumsum(r.normal(size=2000)) * 0.1 + r.normal(size=2000), index=idx)  # persistent, unrelated
        d = pd.Series(r.normal(size=2000), index=idx)
        hits += existence_row("vr_short", proxy, d, IP, ExistenceParams(n_boot=150, n_shift=50), PP, 6, rng)["pass_unadj"]
    assert hits <= 4  # one-sided 2.5% nominal with persistent labels; allow slack


def test_wrong_direction_is_reported_not_hidden():
    rng = np.random.default_rng(3)
    proxy, d = _planted(-0.8)
    row = existence_row("vr_short", proxy, d, IP, EP, PP, 6, rng)  # pre-registered +1, truth is negative
    assert row["verdict"] == "wrong-direction significant" and not row["pass_unadj"]


def test_circular_shift_null_is_centred_without_association():
    rng = np.random.default_rng(4)
    d = rng.normal(size=3000)
    bins = np.repeat(rng.integers(0, 3, 60).astype(float), 50)
    null = circular_shift_null(d, bins, 500, rng, min_shift=250)
    assert abs(null.mean()) < 0.05 and len(null) == 500
    assert circular_shift_null(d[:500], bins[:500], 10, rng, min_shift=250).size == 0


def test_segment_level_test_counts_segments():
    idx = pd.bdate_range("2020-01-01", periods=200)
    bins = pd.Series(np.repeat([2.0, 0.0] * 5, 20)[:200], index=idx)
    d = pd.Series(np.where(bins == 2.0, 1.0, -1.0), index=idx)
    res = segment_level_test(pd.DataFrame({"D": d, "bin": bins}), np.random.default_rng(0), 10, 200, 0.95)
    assert res["seg_n_high"] == 5 and res["seg_n_low"] == 5 and res["seg_diff"] == pytest.approx(2.0)


def test_limit_adjacent_mask_covers_day_and_next_day():
    idx = pd.bdate_range("2020-01-01", periods=5)
    ll = pd.DataFrame({"A": [False, True, False, False, False], "B": False}, index=idx)
    assert limit_adjacent_mask(ll).tolist() == [False, True, True, False, False]


def test_trial_ledger_counts():
    led = TrialLedger()
    led.add("a")
    led.add("b", window=60)
    assert led.n == 2 and list(led.frame().columns) == ["trial", "window"]


def test_end_to_end_synthetic_fallback_writes_artifacts(tmp_path):
    products = ["RB", "HC", "I", "CU", "AL", "ZN", "AU", "AG"]
    data = make_synthetic_futures(products, n_days=1100, seed=5)
    store = RawStore(tmp_path / "raw")
    client = TushareClient(TushareConfig(token="x", max_calls_per_min=10**6), transport=FakeTushareTransport(data), sleep=lambda s: None)
    fetch_universe(client, store, products, start="20100101", progress=lambda *_: None)
    res = run_phase2(
        store, products=products, source="synthetic-fallback", ep=ExistenceParams(n_boot=100, n_shift=100, n_panel_null=3),
        progress=lambda *_: None,
    )
    assert res.meta["n_products_panel"] == 8 and res.meta["roll_days"] > 50
    assert set(res.primary["proxy"]) == {"vr_short", "vr_long", *DIM_NAMES}
    assert res.d_net.abs().max() < 50  # no vol-denominator blow-ups on the unbalanced panel
    write_artifacts(res, tmp_path / "out")
    text = (tmp_path / "out" / "summary.md").read_text()
    assert "SYNTHETIC FALLBACK" in text and "DRAFT" in text
    for f in ("existence_primary.csv", "existence_robustness.csv", "trials.csv", "run_meta.json", "d_by_proxy_bin.png"):
        assert (tmp_path / "out" / f).exists()
