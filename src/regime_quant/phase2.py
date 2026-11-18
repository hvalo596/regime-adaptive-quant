"""Phase 2 driver: raw store -> roll-adjusted panel -> existence tests (step 2) -> artifacts.

`source` is recorded in every artifact: "tushare" (real data in the raw store) or "synthetic-fallback" (plumbing
check on a generated market with known truth; NOT evidence about Chinese futures).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import CostParams, InferenceParams, ProxyParams, StrategyParams  # noqa: E402
from .data.panel import Panel, PanelParams, build_panel  # noqa: E402
from .data.roll import RollParams  # noqa: E402
from .data.store import RawStore  # noqa: E402
from .data.universe import PRODUCTS, commodity_products  # noqa: E402
from .diagnostics import expanding_tercile_bins  # noqa: E402
from .existence import (  # noqa: E402
    EXPECTED_SIGN, ExistenceParams, TrialLedger, compute_d, compute_proxies, conditional_tables,
    existence_row, limit_adjacent_mask, panel_null_pvalues, panel_null_stats,
)
from .inference import performance_summary  # noqa: E402
from .kai_dims import dependence_report  # noqa: E402


@dataclass
class Phase2Result:
    panel: Panel
    proxies: pd.DataFrame
    d_net: pd.Series
    d_gross: pd.Series
    primary: pd.DataFrame
    robustness: pd.DataFrame
    null_panel: pd.DataFrame
    conditional: pd.DataFrame
    legs_perf: pd.DataFrame
    dependence: dict
    ledger: TrialLedger
    meta: dict


def load_raw(store: RawStore, products: list[str]):
    basic = store.basic()
    if basic.empty:
        raise FileNotFoundError(f"no fut_basic in {store.root}; run scripts/fetch_tushare_futures.py first")
    codes = basic.loc[basic["fut_code"].isin(products), "ts_code"]
    daily = store.load_daily(codes)
    mappings = {p: store.mapping(p) for p in products}
    return basic, daily, mappings


def run_phase2(
    store: RawStore,
    products: list[str] | None = None,
    source: str = "tushare",
    sp: StrategyParams = StrategyParams(),
    cp: CostParams = CostParams(),
    pp: ProxyParams = ProxyParams(),
    ip: InferenceParams = InferenceParams(),
    ep: ExistenceParams = ExistenceParams(),
    roll: RollParams = RollParams(),
    panel_params: PanelParams = PanelParams(),
    n_null: int | None = None,
    progress=print,
) -> Phase2Result:
    products = products or commodity_products()
    basic, daily, mappings = load_raw(store, products)
    progress(f"building panel from {daily['ts_code'].nunique()} contracts ...")
    panel = build_panel(products, basic, daily, mappings, roll, panel_params)
    ret = panel.returns
    live = ret.dropna(how="all")
    progress(f"panel: {ret.shape[1]} products, {live.index[0].date()} .. {live.index[-1].date()}")

    d_net, d_gross, legs = compute_d(ret, sp, cp, panel.roll)
    proxies = compute_proxies(ret, pp, ep)
    ledger = TrialLedger()
    for name in proxies.columns:
        ledger.add(name, universe="commodity", window=ep.kai_window if name in ("sys_level", "sys_share", "idio_level", "idio_conc") else "vr",
                   expected_sign=EXPECTED_SIGN[name])
    n_primary = ledger.n

    rng = np.random.default_rng(ep.seed)
    rows = [existence_row(n, proxies[n], d_net, ip, ep, pp, n_primary, rng) for n in proxies.columns]
    primary = pd.DataFrame(rows)

    # robustness variants (not counted as primary tests; reported alongside)
    rob = []
    excl = limit_adjacent_mask(panel.limit_locked)
    mid = d_net.dropna().index[len(d_net.dropna()) // 2]
    variants = {
        "excl_limit_adjacent": dict(exclude=excl),
        "first_half": dict(exclude=pd.Series(d_net.index >= mid, index=d_net.index)),
        "second_half": dict(exclude=pd.Series(d_net.index < mid, index=d_net.index)),
        **{f"block_{b}": dict(mean_block=b) for b in ep.block_lens if b != ip.mean_block},
    }
    for vname, kw in variants.items():
        for n in proxies.columns:
            r = existence_row(n, proxies[n], d_net, ip, ep, pp, n_primary, rng, **kw)
            r["variant"] = vname
            if vname == "excl_limit_adjacent":
                r["share_days_excluded"] = float(excl.reindex(d_net.dropna().index).mean())
            rob.append(r)
    robustness = pd.DataFrame(rob)

    n_rep = ep.n_panel_null if n_null is None else n_null
    null_panel = pd.DataFrame()
    if n_rep > 0:
        progress(f"pipeline-level null: {n_rep} block-resampled panels ...")
        null = panel_null_stats(ret, panel.roll, sp, cp, pp, ep, n_rep)
        obs = {r["proxy"]: r["diff"] for r in rows}
        null_panel = panel_null_pvalues(obs, null)
        null_panel.attrs["null_draws"] = null

    legs_perf = pd.DataFrame(
        [
            {"series": name, **performance_summary(s.dropna(), np.random.default_rng(ep.seed + k), 500, ip.mean_block, ip.ci_level)}
            for k, (name, s) in enumerate(
                {"mom_net": legs["mom"].net, "rev_net": legs["rev"].net,
                 "mom_gross": legs["mom"].gross, "rev_gross": legs["rev"].gross,
                 "D_net": d_net, "D_gross": d_gross}.items()
            )
        ]
    )
    flags = panel.diagnostics
    meta = {
        "source": source,
        "n_products_panel": int(ret.shape[1]),
        "products": list(ret.columns),
        "first_date": str(live.index[0].date()),
        "last_date": str(live.index[-1].date()),
        "n_days_with_D": int(d_net.notna().sum()),
        "n_primary_tests": n_primary,
        "limit_locked_proxy_asset_days": int(panel.limit_locked.to_numpy().sum()),
        "one_price_asset_days": int(panel.one_price.to_numpy().sum()),
        "extreme_ret_asset_days": int(panel.extreme_ret.to_numpy().sum()),
        "stale_asset_days": int(panel.stale.to_numpy().sum()),
        "roll_days": int(panel.roll.to_numpy().sum()),
        "kai_dims_status": "DRAFT (not Kai's formulas)",
        "params": {"strategy": sp.__dict__, "cost": cp.__dict__, "proxy": pp.__dict__, "inference": ip.__dict__,
                   "existence": ep.__dict__, "roll": roll.__dict__, "panel": panel_params.__dict__},
        "products_excluded": flags.loc[~flags["included"], ["product", "reason"]].to_dict("records") if "included" in flags else [],
    }
    return Phase2Result(
        panel=panel, proxies=proxies, d_net=d_net, d_gross=d_gross, primary=primary, robustness=robustness,
        null_panel=null_panel, conditional=conditional_tables(proxies, d_net, pp, ip), legs_perf=legs_perf,
        dependence=dependence_report(proxies), ledger=ledger, meta=meta,
    )


def _fmt(df: pd.DataFrame, cols: list[str], digits: int = 4) -> str:
    d = df[cols].copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.{digits}f}")
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in d.to_numpy())


def write_artifacts(res: Phase2Result, out: str | Path, plots: bool = True) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    res.panel.diagnostics.to_csv(out / "roll_quality_by_product.csv", index=False)
    res.primary.to_csv(out / "existence_primary.csv", index=False)
    res.robustness.to_csv(out / "existence_robustness.csv", index=False)
    res.conditional.to_csv(out / "conditional_D_by_bin.csv", index=False)
    res.legs_perf.to_csv(out / "legs_performance.csv", index=False)
    res.ledger.frame().to_csv(out / "trials.csv", index=False)
    res.dependence["corr"].to_csv(out / "dim_correlation.csv")
    res.dependence["vif"].to_csv(out / "dim_vif.csv")
    if len(res.null_panel):
        res.null_panel.to_csv(out / "pipeline_null.csv", index=False)
    (out / "run_meta.json").write_text(json.dumps(res.meta, indent=2, default=str, ensure_ascii=False))

    m = res.meta
    banner = (
        "> **SYNTHETIC FALLBACK**: generated market with known truth, run through the real ingest/roll/flag/test path. "
        "A plumbing check, not evidence about Chinese futures.\n\n"
        if m["source"] != "tushare"
        else ""
    )
    prim_cols = ["proxy", "expected_sign", "diff", "ci_lo", "ci_hi", "ci_adj_lo", "ci_adj_hi", "seg_high", "seg_low",
                 "seg_diff", "seg_ci_lo", "seg_ci_hi", "shift_p_two_sided", "verdict"]
    prim_cols = [c for c in prim_cols if c in res.primary.columns]
    rob = res.robustness
    rob_view = rob.pivot_table(index="proxy", columns="variant", values="diff", aggfunc="first")
    rob_ver = rob.pivot_table(index="proxy", columns="variant", values="verdict", aggfunc="first")
    lines = [
        f"# Phase 2 existence test (step 2): {m['source']}\n",
        banner,
        f"- data: {m['first_date']} .. {m['last_date']}, {m['n_products_panel']} products "
        f"({', '.join(m['products'])}); {m['n_days_with_D']} days with D",
        f"- flags: {m['limit_locked_proxy_asset_days']} limit-locked-proxy asset-days, {m['one_price_asset_days']} one-price, "
        f"{m['stale_asset_days']} stale, {m['roll_days']} roll days, {m['extreme_ret_asset_days']} |ret|>12% (data-error candidates)",
        f"- primary tests (Bonferroni family): {m['n_primary_tests']}; Kai dims are **DRAFT**, not Kai's formulas",
        "",
        "## Legs and D (net/gross, 95% block-bootstrap Sharpe interval)\n",
        _fmt(res.legs_perf, ["series", "ann_ret", "ann_vol", "sharpe", "sharpe_lo", "sharpe_hi", "max_dd"]),
        "",
        "## Primary: high-tercile minus low-tercile mean D (pre-registered sign; adj = Bonferroni)\n",
        _fmt(res.primary, prim_cols),
        "",
        "## Robustness: diff by variant\n",
        _fmt(rob_view.reset_index(), ["proxy"] + list(rob_view.columns)),
        "",
        "verdicts by variant:\n",
        _fmt(rob_ver.reset_index(), ["proxy"] + list(rob_ver.columns)),
        "",
    ]
    if len(res.null_panel):
        lines += [
            "## Pipeline-level no-regime null (panel block-resampled; destroys persistence beyond the block)\n",
            _fmt(res.null_panel, ["proxy", "observed_diff", "null_mean", "null_sd", "z", "p_two_sided", "p_expected_side", "p_familywise_maxz"]),
            "",
        ]
    dep = res.dependence
    lines += [
        "## Kai-dimension dependence (draft definitions)\n",
        f"logit(sys_share) = 2*(sys_level - idio_level) holds exactly (max residual {dep['max_abs_identity_residual']:.2e}); "
        "the three carry two degrees of freedom.\n",
        _fmt(dep["vif"].reset_index().rename(columns={"index": "dim"}), ["dim", "vif"], 2),
        "",
        "## Roll quality by product\n",
        _fmt(res.panel.diagnostics, [c for c in ["product", "included", "first_date", "last_date", "n_contracts", "n_rolls", "rule_used",
                                                 "official_agreement", "max_abs_unadj_roll_jump", "liquid_from", "reason"] if c in res.panel.diagnostics.columns]),
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines))

    if plots:
        _plots(res, out)


def _plots(res: Phase2Result, out: Path) -> None:
    names = [c for c in res.proxies.columns]
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.5), sharey=True)
    for ax, name in zip(axes.ravel(), names):
        t = res.conditional[res.conditional["proxy"] == name].set_index("bin").reindex(["low", "mid", "high"])
        ax.bar(t.index, t["mean_D"], color=["#4c72b0", "#999999", "#c44e52"])
        ax.axhline(0, color="k", lw=0.6)
        ax.set_title(f"{name} (exp. sign {EXPECTED_SIGN[name]:+d})", fontsize=9)
    axes[0, 0].set_ylabel("mean next-day D")
    fig.tight_layout()
    fig.savefig(out / "d_by_proxy_bin.png", dpi=110)
    plt.close(fig)
