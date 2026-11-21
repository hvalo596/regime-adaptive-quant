"""Step 2: state existence on a (real or fallback) China-futures panel, doc sections 5, 6 and 8 (H0-H8, H10-H13; H9 is step 4).

Pieces: dataset construction (own roll adjustment, same-contract close-to-close returns), per-panel calibration with the real
availability pattern, the state pipeline of step 1, hypothesis tests with interval + cyclic-shift null + pipeline-level null,
per-product and sector panels, non-defining signatures, alternative-channel checks, data audits. Every statistic that is
computed is appended to a trial ledger."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from .backtest import next_value
from .config import (InferenceParams, LegSpec, MOM_MAIN, MOM_SECOND, REV_MAIN, REV_SECOND, REV_SECOND_GAP, StateParams)
from .data.activity import carry_proxy, product_activity
from .data.panel import Panel, PanelParams, build_panel
from .data.roll import RollParams
from .data.store import RawStore
from .data.universe import COMMODITY_SECTORS, PRODUCTS
from .hypotheses import h5_event_test
from .inference import mean_ci, mean_diff_test, quantile_ci, sharpe, stationary_bootstrap_indices, theta_test
from .nullcal import ALL_SPECS, calibrate, calibrate_c_null
from .pipeline import StateRun, run_state_pipeline
from .statemachine import segments
from .world import WorldSpec, generate

IP = InferenceParams()
STATE_NAMES = ("I", "II", "III", "IV")


@dataclass
class Ledger:
    rows: list = field(default_factory=list)

    def add(self, panel: str, hypothesis: str, spec: str, stat: str, value: float, **extra) -> None:
        self.rows.append({"panel": panel, "hypothesis": hypothesis, "spec": spec, "stat": stat, "value": value, **extra})

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


@dataclass
class Dataset:
    source: str
    panels: dict[str, Panel]  # "commodity", "index", "bond"
    activity: dict[str, dict[str, pd.DataFrame]]  # panel -> {oi, vol, amount}
    carry: dict[str, pd.DataFrame]
    sector_of: dict[str, str]
    basic: pd.DataFrame
    daily: pd.DataFrame | None = None
    holding: pd.DataFrame | None = None
    settle_params: pd.DataFrame | None = None
    truth: object = None  # synthetic only: the world
    notes: list = field(default_factory=list)


def group_products(sector_of: dict[str, str]) -> dict[str, list[str]]:
    return {
        "commodity": [p for p, s in sector_of.items() if s in COMMODITY_SECTORS],
        "index": [p for p, s in sector_of.items() if s == "index"],
        "bond": [p for p, s in sector_of.items() if s == "bond"],
    }


def build_dataset(basic: pd.DataFrame, daily: pd.DataFrame, mappings: dict[str, pd.DataFrame], products: list[str], source: str,
                  roll: RollParams = RollParams(), panel_params: PanelParams = PanelParams(), with_carry: bool = True) -> Dataset:
    sector_of = {p: PRODUCTS[p][1] for p in products}
    groups = group_products(sector_of)
    panels, act, carry = {}, {}, {}
    daily = daily.copy()
    if not pd.api.types.is_datetime64_any_dtype(daily["trade_date"]):
        daily["trade_date"] = pd.to_datetime(daily["trade_date"].astype(str), format="%Y%m%d")
    for g, plist in groups.items():
        if not plist:
            continue
        try:
            panels[g] = build_panel(plist, basic, daily, mappings, roll, panel_params)
        except ValueError:
            continue
        act[g] = product_activity(daily, basic, list(panels[g].returns.columns))
        if with_carry:
            held = pd.DataFrame({p: c["held"] for p, c in panels[g].continuous.items()})
            carry[g] = carry_proxy(daily, basic, held, list(panels[g].returns.columns))
    return Dataset(source=source, panels=panels, activity=act, carry=carry, sector_of=sector_of, basic=basic, daily=daily)


def load_real(raw_dir: str | Path, products: list[str] | None = None, **kw) -> Dataset:
    store = RawStore(raw_dir)
    basic = store.basic()
    if basic.empty:
        raise FileNotFoundError(f"no cached Tushare data under {raw_dir}: run scripts/fetch_tushare_futures.py first (needs TUSHARE_TOKEN)")
    products = products or [p for p in PRODUCTS if (basic["fut_code"] == p).any()]
    codes = basic[basic["fut_code"].isin(products)]["ts_code"].tolist()
    daily = store.load_daily(codes)
    mappings = {p: store.mapping(p) for p in products}
    ds = build_dataset(basic, daily, mappings, products, "real", **kw)
    hold_files = list(Path(raw_dir).glob("fut_holding/*.csv.gz"))
    if hold_files:
        ds.holding = pd.concat([store.read("fut_holding", f.name) for f in hold_files], ignore_index=True)
    sp = Path(raw_dir) / "fut_settle.csv.gz"
    if sp.exists():
        ds.settle_params = store.read("fut_settle.csv.gz")
    return ds


def synthetic_dataset(kind: str = "regime", effect: float = 0.15, n_days: int = 2500, seed: int = 7, n_commodity: int = 40, with_carry: bool = False, **world_kw) -> Dataset:
    """Fallback: a planted-state world pushed through the fake Tushare API, the cache, the roll adjustment and the panel builder.
    Commodity (n_commodity), index (4) and bond (4) products are columns of one world. NOT evidence about real markets."""
    from .data.fake_tushare import FakeTushareTransport, make_synthetic_futures
    from .data.store import fetch_universe
    from .data.tushare_client import TushareClient, TushareConfig
    from .data.universe import commodity_products

    commodity = commodity_products()[:n_commodity]
    index = ["IF", "IH", "IC", "IM"]
    bond = ["TS", "TF", "T", "TL"]
    products = commodity + index + bond
    world = generate(WorldSpec(kind=kind, n_assets=len(products), n_days=n_days, effect=effect, seed=seed, **world_kw))
    fut = make_synthetic_futures(world, products, seed=seed, index_products=tuple(index))
    client = TushareClient(TushareConfig(token="synthetic"), transport=FakeTushareTransport(fut), sleep=lambda s: None)
    client._limiter.wait = lambda: None
    with tempfile.TemporaryDirectory() as tmp:
        store = RawStore(tmp)
        fetch_universe(client, store, products, start="20100101", progress=lambda *_: None)
        basic = store.basic()
        daily = store.load_daily(basic[basic["fut_code"].isin(products)]["ts_code"].tolist())
        mappings = {p: store.mapping(p) for p in products}
    ds = build_dataset(basic, daily, mappings, products, "synthetic", with_carry=with_carry)
    ds.truth = world
    ds.notes.append("synthetic fallback: plumbing check only")
    return ds


# --------------------------------------------------------------------------------------------- calibration


def calibrate_panel(returns: pd.DataFrame, specs=ALL_SPECS, n_sims: int = 30, seed0: int = 910_000, min_assets: int = 5) -> dict:
    """Null calibration with the panel's own length, width and availability pattern (nullcal.calibrate with mask)."""
    mask = ~returns.isna().to_numpy()
    cal = calibrate(specs, n_sims=n_sims, seed0=seed0, n_days=len(returns), n_assets=returns.shape[1], mask=mask)
    return cal


# --------------------------------------------------------------------------------------------- analysis of one panel


@dataclass
class PanelResult:
    name: str
    returns: pd.DataFrame
    run: StateRun
    cal: dict
    combos: dict
    labels: np.ndarray
    notes: list = field(default_factory=list)


def analyze_panel(name: str, returns: pd.DataFrame, cal: dict, ledger: Ledger, min_assets: int = 5, combos=None, seed: int = 11, sp: StateParams = StateParams(),
                  ip: InferenceParams = IP) -> PanelResult:
    ret = returns.to_numpy(dtype=float)
    combos = combos or [(MOM_MAIN, REV_MAIN), (MOM_SECOND, REV_MAIN), (MOM_MAIN, REV_SECOND_GAP), (MOM_SECOND, REV_SECOND_GAP)]
    cache: dict = {}
    res, main_run = {}, None
    rng = np.random.default_rng(seed)
    for m, r in combos:
        run = run_state_pipeline(ret, cal, m, r, sp, cache=cache, with_portfolio=False, min_assets=min_assets)
        th = theta_test(run.s, run.D_next, ip, rng)
        res[f"{m.name}|{r.name}"] = th
        for stat in ("theta_raw", "theta_c", "lo_one_sided", "p_shift", "detect", "mean_s"):
            ledger.add(name, "H0", f"{m.name}|{r.name}", stat, float(getattr(th, stat)))
        if main_run is None:
            main_run = run
    labels = np.where(main_run.valid, main_run.quad, None)
    return PanelResult(name, returns, main_run, cal, res, labels)


def pipeline_null_theta(returns: pd.DataFrame, cal: dict, n_sims: int = 200, kinds=("N0z", "N0"), seed0: int = 920_000, min_assets: int = 5, mom=MOM_MAIN, rev=REV_MAIN) -> np.ndarray:
    """Theta_c distribution of the whole pipeline on stateless worlds with the panel's own shape and availability."""
    mask = ~returns.isna().to_numpy()
    T, N = mask.shape
    out = []
    for k in range(n_sims):
        w = generate(WorldSpec(kind=kinds[k % len(kinds)], n_days=T, n_assets=N, seed=seed0 + k))
        r = np.where(mask, w.ret[:T], np.nan)
        run = run_state_pipeline(r, cal, mom, rev, with_portfolio=False, min_assets=min_assets)
        th = theta_test(run.s, run.D_next, InferenceParams(n_boot=50, n_shift=100), np.random.default_rng(k))
        out.append(th.theta_c)
    return np.array(out, dtype=float)


# --------------------------------------------------------------------------------------------- hypothesis battery


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def ols_boot(y: np.ndarray, X: np.ndarray, ip: InferenceParams, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OLS coefficients with stationary-block-bootstrap 95% CI (rows resampled in blocks)."""
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y, X = y[ok], X[ok]
    n = len(y)
    if n < 60:
        k = X.shape[1]
        return np.full(k, np.nan), np.full(k, np.nan), np.full(k, np.nan)
    b = _ols(X, y)
    idx = stationary_bootstrap_indices(n, ip.mean_block, ip.n_boot, rng)
    bs = np.empty((ip.n_boot, X.shape[1]))
    for i in range(ip.n_boot):
        bs[i] = _ols(X[idx[i]], y[idx[i]])
    lo, hi = np.quantile(bs, [(1 - ip.ci_level) / 2, 1 - (1 - ip.ci_level) / 2], axis=0)
    return b, lo, hi


def state_battery(pr: PanelResult, ledger: Ledger, ip: InferenceParams = IP, seed: int = 21, delay_ref: dict | None = None) -> pd.DataFrame:
    """H0-H8 for one panel. Returns one row per statistic with interval, p and a plain verdict."""
    rng = np.random.default_rng(seed)
    run = pr.run
    lab = pr.labels
    v = run.valid
    xm, xr, D = run.legs.mom.x_next, run.legs.rev.x_next, run.D_next
    masks = {k: (lab == k) for k in STATE_NAMES}
    rows = []

    def add(h, stat, value, lo=np.nan, hi=np.nan, p=np.nan, verdict="", note=""):
        rows.append({"panel": pr.name, "hypothesis": h, "stat": stat, "value": value, "ci_lo": lo, "ci_hi": hi, "p": p, "verdict": verdict, "note": note})
        ledger.add(pr.name, h, "main", stat, value if np.isfinite(value) else np.nan)

    # segments per state
    for k in STATE_NAMES:
        segs = len(segments(lab, k, ip.min_segment_len))
        add("occupancy", f"share_{k}", float(masks[k][v].mean()) if v.any() else np.nan, note=f"segments>={ip.min_segment_len}d: {segs}")
        add("occupancy", f"segments_{k}", float(segs))
    enough = {k: len(segments(lab, k, ip.min_segment_len)) >= ip.min_segments for k in STATE_NAMES}

    # H0
    th = pr.combos["M-B|R-A"]
    add("H0", "theta_c", th.theta_c, th.ci_lo, th.ci_hi, th.p_shift, "found" if th.detect else "not rejected", f"mean s={th.mean_s:.3f}, raw theta={th.theta_raw:.2e}, boot one-sided lo={th.lo_one_sided:.2e}")

    # H1, H2
    for h, k, sign in (("H1", "I", +1), ("H2", "II", -1)):
        r = mean_diff_test(D, masks[k], masks["IV"], ip, rng)
        ok = (r.ci_lo > 0) if sign > 0 else (r.ci_hi < 0)
        add(h, f"D_{k}-D_IV", r.diff, r.ci_lo, r.ci_hi, r.p_shift, "supported" if ok and enough[k] else ("direction ok, CI includes 0" if np.sign(r.diff) == sign else "wrong sign"), f"segments {k}: {r.segs_a}, IV: {r.segs_b}")
        leg = xm if k == "I" else xr
        mm, lo, hi = mean_ci(leg[masks[k] & np.isfinite(leg)], ip, rng)
        add(h, f"x_{'MOM' if k == 'I' else 'REV'}|{k}", mm, lo, hi, np.nan, "supported" if lo > 0 else "CI includes 0" if hi > 0 else "negative")

    # H2b: slope of x_REV on z(Phi-perp) in II
    m2 = masks["II"] & np.isfinite(xr) & np.isfinite(run.env.zPhi_perp)
    if m2.sum() > 60:
        X = np.column_stack([np.ones(m2.sum()), run.env.zPhi_perp[m2]])
        b, lo, hi = ols_boot(xr[m2], X, ip, rng)
        add("H2b", "slope_xREV_on_zPhiPerp|II", b[1], lo[1], hi[1], np.nan, "supported" if lo[1] > 0 else "CI includes 0" if hi[1] > 0 else "negative")
    else:
        add("H2b", "slope_xREV_on_zPhiPerp|II", np.nan, verdict="too few II days")

    # H2c
    ok = v & np.isfinite(xm)
    thr = np.quantile(xm[ok], 0.05)
    worst = ok & (xm <= thr)
    share = float(masks["II"][ok].mean())
    k_in = int((worst & masks["II"]).sum())
    n_w = int(worst.sum())
    p_bin = float(sps.binom.sf(k_in - 1, n_w, share)) if n_w else np.nan
    add("H2c", "worst5%_MOM_days_in_II_minus_share", k_in / max(n_w, 1) - share, np.nan, np.nan, p_bin, "supported" if p_bin < 0.05 else "not significant", f"{k_in}/{n_w} vs II share {share:.3f}")

    # H3
    for leg, nm in ((xm, "MOM"), (xr, "REV")):
        mm, lo, hi = mean_ci(leg[masks["III"] & np.isfinite(leg)], ip, rng)
        add("H3", f"x_{nm}|III", mm, lo, hi, np.nan, "positive" if lo > 0 else "CI includes 0" if hi > 0 else "negative", f"III segments: {len(segments(lab, 'III', ip.min_segment_len))}")

    # H4: TOST on annualised Sharpe in IV
    for leg, nm in ((xm, "MOM"), (xr, "REV")):
        x = leg[masks["IV"] & np.isfinite(leg)]
        if len(x) > 60:
            idx = stationary_bootstrap_indices(len(x), ip.mean_block, ip.n_boot, rng)
            sr = np.array([sharpe(x[i]) for i in idx])
            lo, hi = np.quantile(sr, [0.05, 0.95])
            add("H4", f"sharpe_{nm}|IV", sharpe(x), lo, hi, np.nan, "equivalent to 0 (|SR|<0.3)" if (lo > -0.3 and hi < 0.3) else "not shown equivalent" + (" (significantly > 0)" if lo > 0 else ""), "TOST at 5% = 90% CI inside (-0.3, 0.3)")
        else:
            add("H4", f"sharpe_{nm}|IV", np.nan, verdict="too few IV days")

    # H5
    h5 = h5_event_test(run.legs.rev.asset_pnl_next, run.excl, ip, rng)
    add("H5", "x_REV_F - x_REV_Fc", h5["diff"], h5["ci_lo"], h5["ci_hi"], h5["p_neg"], "supported" if h5["reject"] else ("underpowered (events<5)" if h5["underpowered"] else "not supported"), f"events {h5['n_events']}, days {h5['n_days']}")

    # H6: separability
    Z = np.column_stack([run.env.zV, run.env.zPhi_perp])
    X = np.column_stack([np.ones(len(xm)), run.tau_m, run.tau_r, Z])
    for leg, nm in ((xm, "MOM"), (xr, "REV")):
        b, lo, hi = ols_boot(leg, X, ip, rng)
        add("H6", f"{nm}_leg: b_tauM", b[1], lo[1], hi[1])
        add("H6", f"{nm}_leg: b_tauR", b[2], lo[2], hi[2])
    # H7: stickiness
    for nm, d in (("M", run.delta_m), ("R", run.delta_r)):
        dd = d[v]
        occ = float(dd.mean())
        stay = float(np.mean(dd[1:][dd[:-1] == 1] == 1)) if (dd[:-1] == 1).any() else np.nan
        runs_on = [b - a for a, b in segments(np.where(dd == 1, "x", "o").astype(object), "x", 1)]
        mean_on = float(np.mean(runs_on)) if runs_on else np.nan
        ref = (delay_ref or {"M": 62.0, "R": 31.0})[nm]
        add("H7", f"delta{nm}: P(stay on)-occupancy", stay - occ, note=f"occupancy {occ:.3f}, P(stay) {stay:.3f}")
        add("H7", f"delta{nm}: mean on-spell / ref detection delay", mean_on / ref, note=f"mean spell {mean_on:.1f}d, ref delay {ref:.0f}d", verdict=">=2" if mean_on / ref >= 2 else "<2")

    # H8
    zV = run.env.zV
    qs = np.nanquantile(zV[v], [1 / 3, 2 / 3])
    for nm, m in (("low", v & (zV <= qs[0])), ("mid", v & (zV > qs[0]) & (zV <= qs[1])), ("high", v & (zV > qs[1]))):
        t3 = theta_test(np.where(m, run.s, np.nan), np.where(m, D, np.nan), ip, rng)
        add("H8", f"theta_c in zV {nm} tercile", t3.theta_c, t3.ci_lo, t3.ci_hi, t3.p_shift, "positive" if t3.lo_one_sided > 0 else "not significant", f"n={t3.n}")
    Xc = np.column_stack([np.ones(len(D)), run.s, run.env.zV, run.env.zPhi_perp])
    b, lo, hi = ols_boot(D, Xc, ip, rng)
    add("H8", "coef_s | controls zV, zPhiPerp", b[1], lo[1], hi[1], np.nan, "positive" if lo[1] > 0 else "CI includes 0")
    return pd.DataFrame(rows)


def h12_bond_vs_commodity(res_c: PanelResult, res_b: PanelResult, ip: InferenceParams = IP, seed: int = 31) -> pd.DataFrame:
    """Frequency of state II and mean reversal return in II: commodity vs bond panel (prediction: commodity > bond)."""
    rng = np.random.default_rng(seed)
    idx_c, idx_b = res_c.returns.index, res_b.returns.index
    common = idx_c.intersection(idx_b)
    pos_c = idx_c.get_indexer(common)
    pos_b = idx_b.get_indexer(common)
    a = (res_c.labels[pos_c] == "II").astype(float)
    b = (res_b.labels[pos_b] == "II").astype(float)
    ok = res_c.run.valid[pos_c] & res_b.run.valid[pos_b]
    a, b = a[ok], b[ok]
    d = a - b
    idx = stationary_bootstrap_indices(len(d), ip.mean_block, ip.n_boot, rng)
    boot = d[idx].mean(axis=1)
    lo, hi = quantile_ci(boot, ip.ci_level)
    rows = [{"stat": "freq_II commodity - bond", "value": float(d.mean()), "ci_lo": lo, "ci_hi": hi, "verdict": "supported" if lo > 0 else "CI includes 0" if hi > 0 else "reversed"}]
    xr_c = res_c.run.legs.rev.x_next[pos_c][ok][a == 1]
    xr_b = res_b.run.legs.rev.x_next[pos_b][ok][b == 1]
    for nm, x in (("x_REV|II commodity", xr_c), ("x_REV|II bond", xr_b)):
        mm, l, h = mean_ci(x[np.isfinite(x)], ip, rng)
        rows.append({"stat": nm, "value": mm, "ci_lo": l, "ci_hi": h, "verdict": f"n={int(np.isfinite(x).sum())}"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------- per product and sector


def per_product(returns: pd.DataFrame, cal1: dict, ledger: Ledger, ip: InferenceParams = IP, seed: int = 41, min_days: int = 700) -> tuple[pd.DataFrame, dict]:
    """Single-asset version of the whole pipeline (N_eff = 1, calibrated on N=1 stateless worlds)."""
    rows, runs = [], {}
    for j, p in enumerate(returns.columns):
        r = returns[[p]].dropna()
        if len(r) < min_days:
            continue
        arr = returns[[p]].to_numpy(dtype=float)
        run = run_state_pipeline(arr, cal1, with_portfolio=False, min_assets=1)
        runs[p] = run
        th = theta_test(run.s, run.D_next, ip, np.random.default_rng(seed + j))
        lab = np.where(run.valid, run.quad, None)
        row = {"product": p, "n_days": th.n, "theta_c": th.theta_c, "ci_lo": th.ci_lo, "ci_hi": th.ci_hi, "p_shift": th.p_shift, "detect": th.detect,
               "share_I": float(np.mean(lab[run.valid] == "I")), "share_II": float(np.mean(lab[run.valid] == "II")), "share_III": float(np.mean(lab[run.valid] == "III")), "share_IV": float(np.mean(lab[run.valid] == "IV"))}
        rows.append(row)
        ledger.add(f"product:{p}", "H0", "M-B|R-A (N=1)", "theta_c", th.theta_c)
        ledger.add(f"product:{p}", "H0", "M-B|R-A (N=1)", "p_shift", th.p_shift)
    return pd.DataFrame(rows), runs


def multiplicity_summary(df: pd.DataFrame) -> dict:
    """Per-product Theta tests: how many reject at 5% against the 5% expected by chance, plus Holm-adjusted rejections."""
    p = df["p_shift"].to_numpy()
    n = len(p)
    order = np.argsort(p)
    holm = np.zeros(n, dtype=bool)
    for rank, i in enumerate(order):
        if p[i] <= 0.05 / (n - rank):
            holm[i] = True
        else:
            break
    binom_p = float(sps.binom.sf(int((p < 0.05).sum()) - 1, n, 0.05)) if n else np.nan
    return {"n_products": n, "n_reject_5pct": int((p < 0.05).sum()), "expected_by_chance": 0.05 * n, "binomial_p_for_count": binom_p, "n_holm_reject": int(holm.sum())}
