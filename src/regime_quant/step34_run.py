"""Orchestration of steps 3 and 4 (real panels and synthetic validation)."""

from __future__ import annotations

import json
import time
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from .config import MOM_MAIN, REV_MAIN, InferenceParams, StateParams, TRADING_DAYS
from .inference import theta_test
from .recovery import auc, crossing_delays
from .statemachine import segments
from .step3 import ChainSpec, bocpd, build_system, fit_chain, fit_null, forward_filter, _pi0, rolling_filter
from .step34 import (States, build_states, comparison_table, evaluate_all, holm, perf_table, signals, theta_rows)
from .step4 import selection_decomposition
from .world import WorldSpec, generate

warnings.filterwarnings("ignore")
IP = InferenceParams()
IP_FAST = InferenceParams(n_boot=300, n_shift=500)
_CAL: dict = {}
_MASK = None


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _init(cal, mask):
    global _CAL, _MASK
    _CAL, _MASK = cal, mask
    warnings.filterwarnings("ignore")


def run_lengths(mask: np.ndarray) -> list[int]:
    out, cur = [], 0
    for m in mask:
        if m:
            cur += 1
        elif cur:
            out.append(cur)
            cur = 0
    if cur:
        out.append(cur)
    return out


def spell_row(name: str, mask: np.ndarray, valid: np.ndarray) -> dict:
    m = mask & valid
    runs = run_lengths(np.where(valid, mask, False))
    n_valid = int(valid.sum())
    r = np.array(runs) if runs else np.array([0])
    return {"series": name, "days_on": int(m.sum()), "share_on": float(m.sum() / max(n_valid, 1)), "spells": len(runs), "spells_ge10d": int((r >= 10).sum()), "mean_spell": float(r.mean()) if runs else np.nan,
            "median_spell": float(np.median(r)) if runs else np.nan, "p90_spell": float(np.quantile(r, 0.9)) if runs else np.nan, "switches_per_year": float(2 * len(runs) / max(n_valid / TRADING_DAYS, 1e-9))}


def fit_table(st: States) -> pd.DataFrame:
    rows = []
    for chain, rf in (("M", st.rfM), ("R", st.rfR)):
        for t, f in rf.fits:
            rows.append({"chain": chain, "refit_day_index": t, "n_train": f.n, "mu0": f.mu0, "mu1": f.mu1, "gap": f.mu1 - f.mu0, "mean_sojourn0": f.mean_sojourn0, "mean_sojourn1": f.mean_sojourn1, "scale_c": f.c, "degenerate": f.degenerate, "loglik": f.ll})
    return pd.DataFrame(rows)


def model_comparison(inc, label: str) -> pd.DataFrame:
    ok = np.isfinite(inc.z) & np.isfinite(inc.sig)
    n = int(ok.sum())
    rows = []
    ms = float(inc.spec.L + inc.spec.H)
    for cs in (ChainSpec("hmm", "gauss"), ChainSpec("hmm", "t"), ChainSpec("hmm", "gauss", min_sojourn=ms), ChainSpec("hmm", "t", min_sojourn=ms), ChainSpec("hsmm", "t", min_sojourn=ms)):
        f = fit_chain(inc.z, inc.sig, cs)
        ll0 = fit_null(inc.z, inc.sig, cs)
        rows.append({"chain": label, "model": f"{cs.kind}-{cs.dist}" + (f"-sticky{int(cs.min_sojourn)}" if cs.min_sojourn > 1 else ""), "n": n, "loglik": f.ll, "k": 5, "BIC": -2 * f.ll + 5 * np.log(n), "loglik_1state": ll0, "k_1state": 2, "BIC_1state": -2 * ll0 + 2 * np.log(n), "LR": 2 * (f.ll - ll0),
                     "mu0": f.mu0, "mu1": f.mu1, "mean_sojourn0": f.mean_sojourn0, "mean_sojourn1": f.mean_sojourn1, "scale_c": f.c, "degenerate": f.degenerate})
    return pd.DataFrame(rows)


def best_case_delay(fr, sig_path: np.ndarray, inc_spec, n_rep: int = 150, T: int = 1500, seed: int = 0) -> dict:
    """Delay of the filter when the fitted model is TRUE and its parameters are known (an upper bound on what can be achieved):
    simulate the fitted two-state chain with the real scale path and measure the days from a true entry until P(state 1) > 0.5."""
    rng = np.random.default_rng(seed)
    cs = fr.spec
    th = fr.theta
    stay0, stay1 = 1 - 1 / fr.mean_sojourn0, 1 - 1 / fr.mean_sojourn1
    sig = sig_path[np.isfinite(sig_path)]
    delays, n_sw, durs = [], 0, []
    for _ in range(n_rep):
        st = np.zeros(T, dtype=int)
        s = int(rng.random() < 0.3)
        for t in range(T):
            st[t] = s
            if rng.random() > (stay1 if s else stay0):
                s = 1 - s
        i0 = int(rng.integers(0, max(len(sig) - T, 1)))
        sg = sig[i0 : i0 + T]
        if len(sg) < T:
            sg = np.resize(sg, T)
        mu = np.where(st == 1, fr.mu1, fr.mu0)
        eps = rng.standard_t(cs.nu, T) * np.sqrt((cs.nu - 2) / cs.nu) if cs.dist == "t" else rng.standard_normal(T)
        z = mu + fr.c * sg * eps
        kk = inc_spec.L + inc_spec.H + inc_spec.gap
        z = np.where((np.arange(T) % kk) != 0, np.nan, z)
        logB, A, tv, macro = build_system(th, z, sg, cs)
        filt, _ = forward_filter(logB, A, tv, _pi0(th, A, logB.shape[1], tv))
        p = filt[:, macro == 1].sum(axis=1)
        d, n = crossing_delays(st.astype(float), p, 0.5, min_post=10, min_pre=10)
        delays += d
        n_sw += n
        durs += run_lengths(st == 1)
    med = float(np.median(delays)) if delays else np.nan
    return {"n_switches": n_sw, "detect_rate": len(delays) / max(n_sw, 1), "median_delay": med, "q25": float(np.quantile(delays, .25)) if delays else np.nan, "q75": float(np.quantile(delays, .75)) if delays else np.nan,
            "mean_dwell_model": float(fr.mean_sojourn1), "dwell_over_delay": float(fr.mean_sojourn1 / med) if med and np.isfinite(med) else np.nan}


def margin_covariate(ev_mask: pd.DataFrame, live: pd.DataFrame, k: int = 10) -> np.ndarray:
    """x_t: z-score of the share of live products whose held contract had a margin hike in the last k days."""
    cnt = ev_mask.astype(float).rolling(k, min_periods=1).sum().sum(axis=1)
    share = (cnt / live.sum(axis=1).replace(0, np.nan)).to_numpy()
    ok = np.isfinite(share)
    m, s = np.nanmean(share[ok]), np.nanstd(share[ok])
    return (share - m) / s


def covariate_test(incR, x: np.ndarray, start_idx: int, n_shift: int = 40, seed: int = 0) -> dict:
    """Does an exogenous margin-hike intensity speed up entry into the rushed state? R chain (HMM-t, daily transitions, block observations),
    entry probability logistic(alpha + beta x_t). LR against beta = 0 (same parametrisation); null from circular shifts of x (>= 60 days)."""
    cs = ChainSpec("hmm", "t", covariate=True, min_sojourn=float(REV_MAIN.L + REV_MAIN.H))
    z, sg, xx = incR.z[start_idx:], incR.sig[start_idx:], x[start_idx:]
    xx = np.nan_to_num(xx)
    f0 = fit_chain(z, sg, cs, np.zeros_like(xx))
    f1 = fit_chain(z, sg, cs, xx, theta_init=np.r_[f0.theta[:5], 0.0] if len(f0.theta) == 6 else f0.theta)  # nested: start from the beta = 0 solution
    lr = max(2 * (f1.ll - f0.ll), 0.0)
    rng = np.random.default_rng(seed)
    n = len(xx)
    nulls = []
    for _ in range(n_shift):
        sh = int(rng.integers(60, n - 60))
        fs = fit_chain(z, sg, cs, np.roll(xx, sh), theta_init=np.r_[f0.theta[:5], 0.0] if len(f0.theta) == 6 else f0.theta)
        nulls.append(max(2 * (fs.ll - f0.ll), 0.0))
    p = float((1 + (np.array(nulls) >= lr).sum()) / (1 + len(nulls)))
    return {"n_days": int(n), "n_obs": int(np.isfinite(z).sum()), "beta": f1.beta, "LR": lr, "p_shift": p, "ll_cov": f1.ll, "ll_nocov": f0.ll, "null_LR_q95": float(np.quantile(nulls, 0.95))}


def bocpd_summary(inc, name: str, p_filt: np.ndarray) -> dict:
    b = bocpd(inc.z, inc.sig)
    cp = b["cp_mass"]
    alarm = np.zeros(len(cp), dtype=bool)
    armed = True
    for t, c in enumerate(cp):
        if not np.isfinite(c):
            continue
        if armed and c > 0.5:
            alarm[t] = True
            armed = False
        elif c < 0.2:
            armed = True
    idx = np.flatnonzero(alarm)
    gaps = np.diff(idx) if len(idx) > 1 else np.array([])
    ok = np.isfinite(b["level"]) & np.isfinite(p_filt)
    corr = float(np.corrcoef(b["level"][ok], p_filt[ok])[0, 1]) if ok.sum() > 50 else np.nan
    yrs = np.isfinite(cp).sum() / TRADING_DAYS
    return {"chain": name, "alarms": int(alarm.sum()), "alarms_per_year": float(alarm.sum() / max(yrs, 1e-9)), "mean_gap_days": float(gaps.mean()) if len(gaps) else np.nan, "median_gap_days": float(np.median(gaps)) if len(gaps) else np.nan,
            "corr_level_vs_hmm_prob": corr}


def panel_report(name: str, ret_df: pd.DataFrame, cal: dict, out: Path, out4: Path | None = None, min_assets: int = 5, deep: bool = False, ev_mask: pd.DataFrame | None = None, seed: int = 3) -> dict:
    """Steps 3 and 4 on one real panel."""
    out.mkdir(parents=True, exist_ok=True)
    out4 = out4 or out
    out4.mkdir(parents=True, exist_ok=True)
    ret = ret_df.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    log(f"{name}: filtered states")
    st = build_states(ret, cal, min_assets=min_assets)
    sig = signals(st)
    ev, common = evaluate_all(st, sig, ret)
    dates = ret_df.index
    first = int(np.flatnonzero(common)[0])
    res: dict = {"panel": name, "eval_first_day": str(dates[first].date()), "eval_last_day": str(dates[np.flatnonzero(common)[-1]].date()), "eval_days": int(common.sum()),
                 "eval_span_years": float((dates[np.flatnonzero(common)[-1]] - dates[first]).days / 365.25)}
    fit_table(st).to_csv(out / f"filter_fits_{name}.csv", index=False)
    valid = common
    spells = [spell_row("rule delta^M (step 2)", st.run.delta_m == 1, valid), spell_row("rule delta^R (step 2)", st.run.delta_r == 1, valid),
              spell_row("HMM-t P^M>0.5", st.pm > 0.5, valid), spell_row("HMM-t P^R>0.5", st.pr > 0.5, valid)]
    pd.DataFrame(spells).to_csv(out / f"spells_{name}.csv", index=False)
    res["degenerate_share_M"], res["degenerate_share_R"] = st.rfM.degenerate_share, st.rfR.degenerate_share
    log(f"{name}: theta tests")
    th = theta_rows(st, sig, common, IP, rng)
    th.to_csv(out / f"theta_signals_{name}.csv", index=False)
    pt = perf_table(ev, common)
    pt.to_csv(out4 / f"perf_{name}.csv", index=False)
    pairs = []
    for s_ in ("FILT-PEN", "FILT-SOFT", "FILT-HARD", "FILT-BAND", "LEARNED", "RULE"):
        for b_ in ("EW50", "MOM", "TP60", "EWA"):
            pairs.append((s_ + "+VT", b_ + "+VT"))
            pairs.append((s_, b_))
    log(f"{name}: strategy comparisons")
    comp = comparison_table(ev, common, pairs, IP, rng)
    prim = comp[(comp.a == "FILT-PEN+VT") & (comp.cost_mult == 1.0)]
    comp["holm_p_primary"] = np.nan
    prim_idx = comp[(comp.a == "FILT-PEN+VT") & (comp.cost_mult == 1.0) & comp.b.isin(["EW50+VT", "MOM+VT", "TP60+VT", "EWA+VT"])].index
    if len(prim_idx):
        comp.loc[prim_idx, "holm_p_primary"] = holm(comp.loc[prim_idx, "p_gt"].to_numpy())
    comp.to_csv(out4 / f"comparisons_{name}.csv", index=False)
    dec = []
    D = np.where(common, st.run.D_next, np.nan)
    for k in ("RULE", "FILT-HARD", "FILT-SOFT", "FILT-PEN", "FILT-BAND", "LEARNED", "TP60", "EWA"):
        d = selection_decomposition(np.where(common, sig[k], np.nan), D)
        dec.append({"signal": k, **d})
    pd.DataFrame(dec).to_csv(out4 / f"selection_decomposition_{name}.csv", index=False)
    # H9: s_t beyond the recent performance of the legs (doc H9; step-4 control)
    from .step2 import ols_boot
    tp = sig["TP60"]
    for k in ("RULE", "FILT-PEN"):
        X = np.column_stack([np.ones(len(D)), np.where(common, sig[k], np.nan), np.where(common, tp, np.nan)])
        b, lo, hi = ols_boot(D, X, IP, rng)
        res[f"H9_{k}_coef_s"] = [float(b[1]), float(lo[1]), float(hi[1])]
        res[f"H9_{k}_coef_TP60"] = [float(b[2]), float(lo[2]), float(hi[2])]
    res["agreement_rule_vs_filter"] = {}
    ok = common & np.isfinite(st.pm)
    res["agreement_rule_vs_filter"]["corr_deltaM_pM"] = float(np.corrcoef(st.run.delta_m[ok], st.pm[ok])[0, 1])
    res["agreement_rule_vs_filter"]["corr_deltaR_pR"] = float(np.corrcoef(st.run.delta_r[ok], st.pr[ok])[0, 1])
    if deep:
        log(f"{name}: model comparison, delays, change points")
        mc = pd.concat([model_comparison(st.incM, "M (20,5)"), model_comparison(st.incR, "R (5,3)")], ignore_index=True)
        mc.to_csv(out / f"model_comparison_{name}.csv", index=False)
        dl = []
        for lab, rf, inc in (("M", st.rfM, st.incM), ("R", st.rfR, st.incR)):
            fr = rf.fits[-1][1]
            if fr.spec.kind == "hmm":
                dl.append({"chain": lab, **best_case_delay(fr, inc.sig, inc.spec)})
        pd.DataFrame(dl).to_csv(out / f"best_case_delay_{name}.csv", index=False)
        bc = [bocpd_summary(st.incM, "M", st.pm), bocpd_summary(st.incR, "R", st.pr)]
        pd.DataFrame(bc).to_csv(out / f"bocpd_{name}.csv", index=False)
        if ev_mask is not None:
            start = int(np.searchsorted(dates, pd.Timestamp("2021-01-04")))
            live = ret_df.notna()
            x = margin_covariate(ev_mask.reindex(dates).fillna(False), live)
            cov = covariate_test(st.incR, x, start)
            res["margin_covariate_R_chain"] = cov
    (out / f"summary_{name}.json").write_text(json.dumps(res, indent=2, default=float))
    (out4 / f"summary_{name}.json").write_text(json.dumps(res, indent=2, default=float))
    return res


# ------------------------------------------------------------------------------------------------ synthetic tasks


def _stats_for_world(ret: np.ndarray, truth: tuple | None, cal: dict, with_lr: bool, tag: str, seed: int, min_assets: int = 5) -> dict:
    st = build_states(ret, cal, min_assets=min_assets)
    sig = signals(st, truth)
    ev, common = evaluate_all(st, sig, ret)
    rng = np.random.default_rng(seed)
    out = {"tag": tag, "seed": seed, "eval_days": int(common.sum())}
    if common.sum() < 500:
        return out
    D = np.where(common, st.run.D_next, np.nan)
    for k in ("RULE", "FILT-HARD", "FILT-PEN", "TP60", "EWA") + (("ORACLE",) if truth is not None else ()):
        th = theta_test(np.where(common, sig[k], np.nan), D, IP_FAST, rng)
        out[f"theta_c:{k}"], out[f"detect:{k}"], out[f"p_shift:{k}"] = th.theta_c, bool(th.detect), th.p_shift
    if truth is not None:
        dm, dr = truth
        ok = common & np.isfinite(st.pm)
        out["auc:pM"], out["auc:pR"] = auc(st.pm[ok], dm[ok]), auc(st.pr[ok], dr[ok])
        out["auc:tauM"], out["auc:tauR"] = auc(st.run.tau_m[ok], dm[ok]), auc(st.run.tau_r[ok], dr[ok])
        out["degenerate:M"], out["degenerate:R"] = st.rfM.degenerate_share, st.rfR.degenerate_share
        for k in ("FILT-PEN", "RULE", "ORACLE", "TP60", "EWA"):
            d = selection_decomposition(np.where(common, sig[k], np.nan), D)
            out[f"timing_ann:{k}"], out[f"tilt_ann:{k}"], out[f"selection_ann:{k}"] = d.get("timing_ann"), d.get("tilt_ann"), d.get("selection_ann")
    pt = perf_table(ev, common).set_index("strategy")
    for k in ("EW50", "EW50+VT", "MOM+VT", "RULE+VT", "FILT-PEN+VT", "FILT-BAND+VT", "TP60+VT", "EWA+VT") + (("ORACLE+VT",) if truth is not None else ()):
        for c in (0.0, 0.5, 1.0):
            out[f"sharpe:{k}:c{c}"] = pt.loc[k, f"sharpe_c{c}"]
    comp = comparison_table(ev, common, [("FILT-PEN+VT", "EW50+VT"), ("RULE+VT", "EW50+VT"), ("FILT-PEN+VT", "EWA+VT"), ("FILT-PEN+VT", "TP60+VT")] + ([("ORACLE+VT", "EW50+VT")] if truth is not None else []), IP_FAST, rng, cost=1.0)
    for r in comp.itertuples():
        out[f"dsharpe:{r.a}-{r.b}:c{r.cost_mult}"], out[f"p_gt:{r.a}-{r.b}:c{r.cost_mult}"] = r.diff, r.p_gt
    if with_lr:
        for lab, inc in (("M", st.incM), ("R", st.incR)):
            cs = ChainSpec("hmm", "t", min_sojourn=float(inc.spec.L + inc.spec.H))
            f = fit_chain(inc.z, inc.sig, cs)
            out[f"LR:{lab}"] = 2 * (f.ll - fit_null(inc.z, inc.sig, cs))
    return out


def planted_task(task: dict) -> dict:
    kind, seed, kw = task["kind"], task["seed"], task.get("kw", {})
    spec = WorldSpec(kind=kind, seed=seed, **kw)
    w = generate(spec)
    ret = w.ret.copy()
    if task.get("mask", False) and _MASK is not None:
        T, N = _MASK.shape
        spec = WorldSpec(kind=kind, seed=seed, n_days=T, n_assets=N, **kw)
        w = generate(spec)
        ret = np.where(_MASK, w.ret[:T], np.nan)
    truth = (w.delta_m, w.delta_r) if kind in ("regime", "informed") else None
    return _stats_for_world(ret, truth, _CAL, task.get("lr", False), task.get("tag", kind), seed)


def switch_delay_task(task: dict) -> dict:
    which, seed, effect, dwell = task["which"], task["seed"], task["effect"], task["dwell"]
    used = (0, 3) if which == "M" else (1, 3)
    spec = WorldSpec(kind="regime", seed=seed, effect=effect, states_used=used, mean_dwell=(dwell,) * 4, dwell_disp=6.0)
    w = generate(spec)
    st = build_states(w.ret, _CAL)
    truth, p, tau = (w.delta_m, st.pm, st.run.tau_m) if which == "M" else (w.delta_r, st.pr, st.run.tau_r)
    dh, nh = crossing_delays(truth, p, 0.5, min_post=int(dwell * 0.5), min_pre=30)
    dr_, nr = crossing_delays(truth, tau, 1.28, min_post=int(dwell * 0.5), min_pre=30)
    ok = np.isfinite(p)
    return {"which": which, "effect": effect, "dwell": dwell, "seed": seed, "hmm_delays": dh, "hmm_n": nh, "rule_delays": dr_, "rule_n": nr, "auc_hmm": auc(p[ok], truth[ok]), "auc_rule": auc(tau[ok & np.isfinite(tau)], truth[ok & np.isfinite(tau)])}


def run_pool(fn, tasks, cal, mask=None, workers: int = 4):
    with Pool(workers, initializer=_init, initargs=(cal, mask)) as pool:
        return pool.map(fn, tasks, chunksize=1)
