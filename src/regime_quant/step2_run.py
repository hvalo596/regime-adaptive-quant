"""Orchestration of step 2: run everything on a Dataset (real or synthetic fallback) and write the artifacts."""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import audit as audit_mod
from . import altchannels as alt
from .config import InferenceParams, MOM_MAIN, REV_MAIN
from .data.universe import COMMODITY_SECTORS
from .inference import mean_diff_test
from .nondefining import (abnormal_volume, amihud, b2_bootstrap, events_from_mask, event_study, llorente_stats, margin_events_from_settle, oi_growth,
                          panel_series, seat_panel, state_signature_table, zscore_own)
from .nullcal import ALL_SPECS, calibrate, calibrate_c_null
from .step2 import (Dataset, Ledger, PanelResult, analyze_panel, calibrate_panel, h12_bond_vs_commodity, multiplicity_summary, per_product, pipeline_null_theta,
                    state_battery)
from .world import WorldSpec, generate

warnings.filterwarnings("ignore")
IP = InferenceParams()


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def power_at_real_dims(returns: pd.DataFrame, cal: dict, efforts=(0.0, 0.05, 0.10, 0.15, 0.20), n_sims: int = 40, seed0: int = 930_000) -> pd.DataFrame:
    """Planted-state worlds with the panel's own length, width and availability: detection rate and mean Theta_c of the decision rule."""
    from .inference import theta_test
    from .pipeline import run_state_pipeline

    mask = ~returns.isna().to_numpy()
    T, N = mask.shape
    rows = []
    for dwell_name, dwell in (("doc-dwell", (120.0, 20.0, 30.0, 120.0)), ("long-dwell", (300.0,) * 4)):
        for eff in efforts:
            det, th_c = [], []
            for k in range(n_sims):
                w = generate(WorldSpec(kind="regime", n_days=T, n_assets=N, effect=eff, mean_dwell=dwell, seed=seed0 + int(eff * 1000) * 7 + k))
                r = np.where(mask, w.ret[:T], np.nan)
                run = run_state_pipeline(r, cal, with_portfolio=False)
                t = theta_test(run.s, run.D_next, InferenceParams(n_boot=200, n_shift=300), np.random.default_rng(k))
                det.append(t.detect)
                th_c.append(t.theta_c)
            rows.append({"world": dwell_name, "effect": eff, "n_sims": n_sims, "detect_rate": float(np.mean(det)), "mean_theta_c": float(np.nanmean(th_c)), "sd_theta_c": float(np.nanstd(th_c))})
    return pd.DataFrame(rows)


def signatures(ds: Dataset, pr: PanelResult, ip: InferenceParams, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    run, name = pr.run, pr.name
    idx = pr.returns.index
    act = ds.activity[name]
    cols = list(pr.returns.columns)
    oi = act["oi"].reindex(idx)[cols].to_numpy(dtype=float)
    vol = act["vol"].reindex(idx)[cols].to_numpy(dtype=float)
    amt = act["amount"].reindex(idx)[cols].to_numpy(dtype=float) if "amount" in act else None
    rt = run.legs.rt
    g = oi_growth(oi)
    av = abnormal_volume(vol)
    shock = np.abs(rt) > 2.0
    series = {"g_OI (panel mean)": panel_series(g), "g_OI on |r~|>2 days": panel_series(g, shock), "AV": panel_series(av), "g_OI flagged assets": panel_series(g, run.excl)}
    if amt is not None:
        series["Amihud (log, z)"] = panel_series(amihud(pr.returns.to_numpy(dtype=float), amt))
    labels = pr.labels
    table = state_signature_table(series, labels, "IV", ip, rng)
    # Llorente b2 per state, and on flagged asset-days
    stats_all = llorente_stats(rt, av)
    stats_F = llorente_stats(rt, av, cell_mask=run.excl)
    rows = []
    for k in ("I", "II", "III", "IV"):
        r = b2_bootstrap(stats_all, labels == k, ip, rng)
        rows.append({"sample": f"state {k}", **r})
    r = b2_bootstrap(stats_F, run.excl.any(axis=1), ip, rng)
    rows.append({"sample": "flagged assets (F), exclusion-window days", **r})
    r = b2_bootstrap(stats_all, np.ones(len(labels), dtype=bool), ip, rng)
    rows.append({"sample": "all days", **r})
    b2 = pd.DataFrame(rows)
    # seats (semi-direct evidence), only when fut_holding was fetched
    extra = {}
    if ds.holding is not None and len(ds.holding):
        sp = seat_panel(ds.holding, act["oi"].reindex(idx), cols)
        seat_series = {f"seats: {k}": panel_series(v.reindex(idx)[cols].to_numpy(dtype=float)) for k, v in sp.items()}
        table = pd.concat([table, state_signature_table(seat_series, labels, "IV", ip, rng)], ignore_index=True)
    else:
        extra["seats"] = "fut_holding not fetched: seat signatures not computed"
    return table, b2, extra


def h10_judgement(sig: pd.DataFrame, b2: pd.DataFrame, h11: pd.DataFrame | None) -> pd.DataFrame:
    """Doc 5.3: a state's mechanism is 'consistent' when all of its starred signatures have the predicted sign and at least two are
    significant at 5%."""
    def sg(signature, state):
        r = sig[(sig.signature == signature) & (sig.state == state)]
        return r.iloc[0] if len(r) else None

    def b2row(sample):
        r = b2[b2["sample"] == sample]
        return r.iloc[0] if len(r) else None

    stars = []
    r = sg("g_OI (panel mean)", "I")
    if r is not None:
        stars.append(("I", "g_OI up vs IV", r["diff"] > 0, r["ci_lo"] > 0))
    r = b2row("state I")
    if r is not None:
        stars.append(("I", "b2 >= 0", r["b2"] >= 0, r["ci_lo"] > 0))
    r = sg("g_OI on |r~|>2 days", "II")
    if r is not None:
        stars.append(("II", "g_OI down on shock days vs IV", r["diff"] < 0, r["ci_hi"] < 0))
    r = sg("AV", "II")
    if r is not None:
        stars.append(("II", "AV up vs IV", r["diff"] > 0, r["ci_lo"] > 0))
    r = b2row("state II")
    if r is not None:
        stars.append(("II", "b2 < 0", r["b2"] < 0, r["ci_hi"] < 0))
    if h11 is not None and len(h11):
        r = h11[h11.outcome == "tau_R"]
        if len(r):
            stars.append(("II", "tau_R up after margin/limit events", r.iloc[0]["mean_diff"] > 0, r.iloc[0]["ci_lo"] > 0))
    r = b2row("flagged assets (F), exclusion-window days")
    if r is not None:
        stars.append(("V", "b2 > 0 on flagged assets", r["b2"] > 0, r["ci_lo"] > 0))
    df = pd.DataFrame(stars, columns=["state", "star signature", "right_direction", "significant_5pct"])
    out = []
    for st, g in df.groupby("state"):
        out.append({"state": st, "n_stars": len(g), "n_right_direction": int(g.right_direction.sum()), "n_significant": int(g.significant_5pct.sum()),
                    "mechanism_consistent": bool(g.right_direction.all() and g.significant_5pct.sum() >= 2)})
    return df, pd.DataFrame(out)


def verdict(th_c, ci_lo, ci_hi, detect, p_pipe, benchmark_theta, power_rate):
    """Plain verdict for H0: found / not found / underpowered."""
    if detect and p_pipe < 0.05:
        return "FOUND: decision rule and pipeline-level null both reject"
    if np.isfinite(ci_hi) and np.isfinite(benchmark_theta) and ci_hi < benchmark_theta:
        return f"NOT FOUND: the upper end of the 95% interval ({ci_hi:.2e}) is below the Theta a planted effect of 0.10 produces here ({benchmark_theta:.2e})"
    return f"UNDERPOWERED: not rejected, but the interval still contains the Theta of a planted 0.10 effect ({benchmark_theta:.2e}); detection rate of such an effect at this sample is {power_rate:.0%}"


def coverage_tables(ds: Dataset, results: dict[str, "PanelResult"], min_years: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-product and per-panel coverage: raw first/last bar, first date inside the panel (after the liquidity latch and 250-day
    history), analysis window (first / last day with a defined selection signal), live products, N_eff, drop reasons."""
    prod_rows, panel_rows = [], []
    for g, pan in ds.panels.items():
        d = pan.diagnostics.copy()
        first_ret = pan.returns.apply(lambda c: c.first_valid_index())
        for r in d.itertuples():
            prod_rows.append({"panel": g, "product": r.product, "raw_first_bar": getattr(r, "first_date", None), "raw_last_bar": getattr(r, "last_date", None),
                              "n_rollable_days": getattr(r, "n_days", None), "included": r.included, "drop_reason": r.reason, "liquid_from": getattr(r, "liquid_from", None),
                              "first_return_in_panel": str(first_ret.get(r.product).date()) if r.included and pd.notna(first_ret.get(r.product)) else None})
        ret = pan.returns
        first_any = ret.dropna(how="all").index[0]
        row = {"panel": g, "n_products_included": int(d["included"].sum()), "n_products_total": len(d), "first_return_date": str(first_any.date()), "last_date": str(ret.index[-1].date()),
               "live_products_mean": float(ret.notna().sum(axis=1).mean()), "live_products_min": int(ret.notna().sum(axis=1).min()), "live_products_max": int(ret.notna().sum(axis=1).max())}
        pr = results.get(g)
        if pr is not None:
            v = pr.run.valid
            if v.any():
                i0, i1 = np.flatnonzero(v)[[0, -1]]
                dates = ret.index
                row.update({"analysis_first_day": str(dates[i0].date()), "analysis_last_day": str(dates[i1].date()), "analysis_days": int(v.sum()),
                            "analysis_span_years": float((dates[i1] - dates[i0]).days / 365.25), "n_eff_M_mean": float(np.nanmean(pr.run.mr_m.n_eff[v])), "n_eff_R_mean": float(np.nanmean(pr.run.mr_r.n_eff[v]))})
                row["meets_min_years"] = bool(row["analysis_span_years"] >= min_years)
                row["warmup_days_lost"] = int(i0)
        panel_rows.append(row)
    return pd.DataFrame(prod_rows), pd.DataFrame(panel_rows)


def run_all(ds: Dataset, out: Path, scale: float = 1.0, seed: int = 5, min_years: float = 20.0) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ledger = Ledger()
    rng = np.random.default_rng(seed)
    summary: dict = {"source": ds.source, "notes": ds.notes}
    n_cal, n_null, n_pow = max(int(40 * scale), 6), max(int(200 * scale), 20), max(int(40 * scale), 6)

    # ---- overview and audits
    log("overview")
    ov = []
    for g, pan in ds.panels.items():
        r = pan.returns
        ov.append({"panel": g, "n_products": r.shape[1], "first_date": str(r.dropna(how="all").index[0].date()), "last_date": str(r.index[-1].date()), "n_days": len(r),
                   "mean_live_products": float(r.notna().sum(axis=1).mean()), "n_locked_proxy": int(pan.limit_locked.to_numpy().sum()), "n_one_price": int(pan.one_price.to_numpy().sum()),
                   "n_extreme_gt12pct": int(pan.extreme_ret.to_numpy().sum()), "n_stale": int(pan.stale.to_numpy().sum())})
        pan.diagnostics.to_csv(out / f"roll_quality_{g}.csv", index=False)
        ed = audit_mod.extreme_days(pan)
        ed.to_csv(out / f"audit_extreme_days_{g}.csv", index=False)
        ns = audit_mod.night_session_break(pan)
        ns.to_csv(out / f"audit_night_session_{g}.csv", index=False)
    pd.DataFrame(ov).to_csv(out / "panel_overview.csv", index=False)
    if ds.daily is not None:
        summary["calendar"] = audit_mod.calendar_checks(ds.daily)

    com = ds.panels["commodity"]
    ret_c = com.returns
    # ---- calibration
    log("calibration")
    cal = calibrate_panel(ret_c, n_sims=n_cal)
    cal["C_threshold"] = calibrate_c_null(n_sims=max(int(12 * scale), 4))
    (out / "calibration_commodity.json").write_text(json.dumps(cal, indent=2))
    cal1 = calibrate(ALL_SPECS, n_sims=n_cal, n_assets=1, min_assets=1, seed0=940_000)
    (out / "calibration_single_asset.json").write_text(json.dumps(cal1, indent=2))

    # ---- main panel
    log("commodity panel")
    pr = analyze_panel("commodity", ret_c, cal, ledger)
    results_by_panel = {"commodity": pr}
    battery = [state_battery(pr, ledger)]
    log("pipeline-level null for Theta")
    null_th = pipeline_null_theta(ret_c, cal, n_sims=n_null)
    p_pipe = float((1 + (null_th >= pr.combos["M-B|R-A"].theta_c).sum()) / (1 + np.isfinite(null_th).sum()))
    pd.DataFrame({"theta_c_null": null_th}).to_csv(out / "pipeline_null_theta_commodity.csv", index=False)
    log("power at real dimensions")
    pw = power_at_real_dims(ret_c, cal, n_sims=n_pow)
    pw.to_csv(out / "power_real_dims.csv", index=False)
    bench = float(pw[(pw.world == "doc-dwell") & (pw.effect == 0.10)].mean_theta_c.iloc[0])
    rate = float(pw[(pw.world == "doc-dwell") & (pw.effect == 0.10)].detect_rate.iloc[0])
    th = pr.combos["M-B|R-A"]
    summary["H0_commodity"] = {"theta_c": th.theta_c, "ci": [th.ci_lo, th.ci_hi], "p_shift": th.p_shift, "p_pipeline": p_pipe, "detect": bool(th.detect), "benchmark_theta_planted_0.10": bench,
                               "power_planted_0.10_doc_dwell": rate, "verdict": verdict(th.theta_c, th.ci_lo, th.ci_hi, th.detect, p_pipe, bench, rate)}
    ledger.add("commodity", "H0", "main", "p_pipeline", p_pipe)
    rows = []
    for k, t in pr.combos.items():
        rows.append({"panel": "commodity", "combo": k, "theta_raw": t.theta_raw, "theta_c": t.theta_c, "ci_lo": t.ci_lo, "ci_hi": t.ci_hi, "p_shift": t.p_shift, "detect": t.detect, "mean_s": t.mean_s, "mean_D": t.mean_D, "n": t.n})

    # ---- sector, index and bond panels
    for sector in COMMODITY_SECTORS:
        cols = [p for p in ret_c.columns if ds.sector_of.get(p) == sector]
        if len(cols) < 5:
            continue
        sub = ret_c[cols].dropna(how="all")
        log(f"sector {sector}")
        cs = calibrate_panel(sub, n_sims=max(n_cal // 2, 6))
        cs["C_threshold"] = cal["C_threshold"]
        prs = analyze_panel(f"sector:{sector}", sub, cs, ledger, combos=[(MOM_MAIN, REV_MAIN)])
        battery.append(state_battery(prs, ledger, seed=22))
        t = prs.combos["M-B|R-A"]
        rows.append({"panel": f"sector:{sector}", "combo": "M-B|R-A", "theta_raw": t.theta_raw, "theta_c": t.theta_c, "ci_lo": t.ci_lo, "ci_hi": t.ci_hi, "p_shift": t.p_shift, "detect": t.detect, "mean_s": t.mean_s, "mean_D": t.mean_D, "n": t.n})
    res_bond = None
    for g, min_a in (("index", 3), ("bond", 3)):
        if g not in ds.panels:
            continue
        sub = ds.panels[g].returns.dropna(how="all")
        if sub.shape[1] < min_a:
            continue
        log(f"{g} panel")
        cg = calibrate(ALL_SPECS, n_sims=max(n_cal // 2, 6), n_days=len(sub), n_assets=sub.shape[1], mask=~sub.isna().to_numpy(), min_assets=min_a, seed0=950_000)
        cg["C_threshold"] = cal["C_threshold"]
        prg = analyze_panel(f"panel:{g}", sub, cg, ledger, min_assets=min_a, combos=[(MOM_MAIN, REV_MAIN)])
        t = prg.combos["M-B|R-A"]
        rows.append({"panel": f"panel:{g}", "combo": "M-B|R-A", "theta_raw": t.theta_raw, "theta_c": t.theta_c, "ci_lo": t.ci_lo, "ci_hi": t.ci_hi, "p_shift": t.p_shift, "detect": t.detect, "mean_s": t.mean_s, "mean_D": t.mean_D, "n": t.n})
        if g == "bond":
            res_bond = prg
        results_by_panel[g] = prg
    pd.DataFrame(rows).to_csv(out / "theta_by_panel.csv", index=False)
    if res_bond is not None:
        h12 = h12_bond_vs_commodity(pr, res_bond)
        h12.to_csv(out / "h12_bond_vs_commodity.csv", index=False)

    # ---- per product
    log("per product")
    pp, pp_runs = per_product(ret_c, cal1, ledger)
    pp["sector"] = pp["product"].map(ds.sector_of)
    pp.to_csv(out / "per_product_theta.csv", index=False)
    summary["per_product_multiplicity"] = multiplicity_summary(pp) if len(pp) else {}

    # ---- non-defining signatures, H10, H11
    log("non-defining signatures")
    sig, b2, extra = signatures(ds, pr, IP, rng)
    sig.to_csv(out / "nondefining_signatures.csv", index=False)
    b2.to_csv(out / "llorente_b2.csv", index=False)
    summary.update(extra)
    h11 = None
    if pp_runs:
        if ds.settle_params is not None:
            ev_mask = margin_events_from_settle(ds.settle_params, ret_c.index, list(ret_c.columns))
            ev_kind = "margin increase (fut_settle)"
        else:
            ev_mask = (com.limit_locked | com.one_price)
            ev_kind = "PROXY: limit-locked / one-price days (fut_settle margins not available)"
        events = events_from_mask(ev_mask)
        oi = ds.activity["commodity"]["oi"].reindex(ret_c.index)
        g_oi = {p: oi_growth(oi[[p]].to_numpy(dtype=float))[:, 0] for p in pp_runs}
        res = []
        for outcome, series in (("tau_R", {p: r.tau_r for p, r in pp_runs.items()}), ("P(delta_R=1)", {p: r.delta_r for p, r in pp_runs.items()}), ("g_OI", g_oi)):
            r = event_study(events, series, ip=IP, rng=rng)
            res.append({"outcome": outcome, "event_kind": ev_kind, **r})
        h11 = pd.DataFrame(res)
        h11.to_csv(out / "h11_event_study.csv", index=False)
    stars, h10 = h10_judgement(sig, b2, h11)
    stars.to_csv(out / "h10_star_signatures.csv", index=False)
    h10.to_csv(out / "h10_mechanism_consistency.csv", index=False)

    # ---- alternative channels
    log("alternative channels")
    alt_rows = []
    alt_rows.append({"check": "settle", **alt.settle_channel(com, ret_c.to_numpy(dtype=float), cal, pr.run, IP, rng)})
    alt_rows.append({"check": "limit_locked", **alt.locked_channel(com, ret_c.to_numpy(dtype=float), cal, pr.run, IP, rng)})
    pd.DataFrame(alt_rows).to_csv(out / "alt_channels.csv", index=False)
    alt.roll_spread(ret_c).to_csv(out / "roll_spread.csv", index=False)
    carry = ds.carry.get("commodity")
    alt.risk_premium_channel(pr.run, carry, ret_c.index, IP, rng).to_csv(out / "risk_premium_control.csv", index=False)

    bat = pd.concat(battery, ignore_index=True)
    bat.to_csv(out / "hypotheses.csv", index=False)
    ledger.frame().to_csv(out / "trial_ledger.csv", index=False)
    # segments table
    seg_rows = []
    for k in ("I", "II", "III", "IV"):
        from .statemachine import segments

        segs = segments(pr.labels, k, 10)
        seg_rows.append({"state": k, "days": int((pr.labels == k).sum()), "segments_ge10d": len(segs), "mean_length": float(np.mean([b - a for a, b in segs])) if segs else np.nan})
    pd.DataFrame(seg_rows).to_csv(out / "state_segments.csv", index=False)
    cov_prod, cov_panel = coverage_tables(ds, results_by_panel, min_years)
    cov_prod.to_csv(out / "coverage_products.csv", index=False)
    cov_panel.to_csv(out / "coverage_panel.csv", index=False)
    cp = cov_panel[cov_panel.panel == "commodity"]
    if len(cp) and "analysis_span_years" in cp:
        span = float(cp.analysis_span_years.iloc[0])
        summary["commodity_analysis_span_years"] = span
        summary["meets_min_years"] = bool(span >= min_years)
        if span < min_years:
            summary["span_warning"] = f"commodity analysis window spans {span:.1f} years, below the required {min_years:.0f}: data availability, not a choice"
    summary["n_trials_in_ledger"] = len(ledger.rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    log("done")
    return summary
