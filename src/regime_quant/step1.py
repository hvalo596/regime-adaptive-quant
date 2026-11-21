"""Step 1 experiments: acceptance checks of the state machinery on synthetic worlds (doc section 7.5 and 8 / H13).

Pre-registered acceptance criteria (fixed before the final runs, see docs/step1-result-report.md):
  A1 engine          vectorised vs streaming engine max abs daily diff < 1e-10; no-look-ahead test; exact identity of doc 4.5
  A2 variables       null calibration: tau ~ N(0, 1) on stateless worlds; sample rho_hat matches the closed forms of doc 7.3
  A3 recovery        slow-switching world, effect 0.15: AUC(tau_M, true M-crowd) >= 0.80 and AUC(tau_R, true R-crowd) >= 0.75;
                     doc-default dwell: reported, expected to be low for the rushed crowd (doc 4.3)
  A4 null controls   N0z, N0, N1, N2, N2b, N3, N4: false-positive rate of the Theta decision rule <= 5% (main spec)
  A5 H5 controls     H5 reject rate <= 5% in every null world, in particular N2b (concentrated but public)
  A6 N2 association  delta^M, delta^R not associated with z(V), z(Phi-perp), C: reject rate <= 5% for each of the 6 pairs
  A7 delay           median first-crossing delay within [0.67, 1.5] x the window-specific d* prediction and >= the d* lower bound
  A8 power           detection rate and AUC by effect level 0, .05, .10, .15, .20 are reported (no pass level)
"""

from __future__ import annotations

import json
import time
import warnings
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist

from .config import InferenceParams, LegSpec, MOM_MAIN, MOM_SECOND, REV_MAIN, REV_SECOND, REV_SECOND_GAP, StateParams
from .hypotheses import delta_association, h5_event_test
from .inference import theta_test
from .nullcal import ALL_SPECS, calibrate
from .pipeline import run_state_pipeline
from .recovery import crossing_delays, d_star, recovery_summary
from .world import STATES, WorldSpec, generate, solve_states

warnings.filterwarnings("ignore")

SPECS = {s.name: s for s in ALL_SPECS}
COMBOS = [("M-B", "R-A"), ("M-A", "R-A"), ("M-B", "R-B-gap"), ("M-B", "R-B"), ("M-A", "R-B-gap")]
IP = InferenceParams()
_CAL: dict = {}


def _init(cal: dict) -> None:
    global _CAL
    _CAL = cal
    warnings.filterwarnings("ignore")


def cp_interval(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    a = (1 - level) / 2
    lo = 0.0 if k == 0 else beta_dist.ppf(a, k, n - k + 1)
    hi = 1.0 if k == n else beta_dist.ppf(1 - a, k + 1, n - k)
    return float(lo), float(hi)


def informed_event_stats(world, run, k_i: int) -> dict:
    """Event-level view of C / F: share of planted informed events with the right asset flagged, and the delay."""
    inf = world.informed
    T, N = inf.shape
    hits, delays, n_ev = 0, [], 0
    in_window = np.zeros((T, N), dtype=bool)
    for i in range(N):
        t = 0
        while t < T:
            if inf[t, i] and (t == 0 or not inf[t - 1, i]):
                end = t
                while end < T and inf[end, i]:
                    end += 1
                n_ev += 1
                hi = min(T, end + k_i)
                in_window[t:hi, i] = True
                fl = np.flatnonzero(run.F[t:hi, i])
                if len(fl):
                    hits += 1
                    delays.append(int(fl[0]))
                t = end
            else:
                t += 1
    flagged = run.F.sum()
    precise = (run.F & in_window).sum()
    return {"inf_events": n_ev, "inf_hits": hits, "inf_delay_med": float(np.median(delays)) if delays else float("nan"),
            "flag_asset_days": int(flagged), "flag_precision": float(precise / flagged) if flagged else float("nan")}


def sim_task(task: dict) -> dict:
    kind, seed, kw, tag = task["kind"], task["seed"], task.get("kw", {}), task.get("tag", task["kind"])
    spec = WorldSpec(kind=kind, seed=seed, **kw)
    w = generate(spec)
    rng = np.random.default_rng(seed + 17)
    out = {"tag": tag, "kind": kind, "seed": seed}
    cache: dict = {}
    for mn, rn in COMBOS if task.get("combos", True) else COMBOS[:1]:
        main = (mn, rn) == COMBOS[0]
        run = run_state_pipeline(w.ret, _CAL, SPECS[mn], SPECS[rn], cache=cache, with_portfolio=False)
        th = theta_test(run.s, run.D_next, IP, rng)
        key = f"{mn}|{rn}"
        out.update({f"{key}:detect": th.detect, f"{key}:p_shift": th.p_shift, f"{key}:boot_lo": th.lo_one_sided,
                    f"{key}:theta_c": th.theta_c, f"{key}:theta_raw": th.theta_raw, f"{key}:p_raw": th.p_shift_raw,
                    f"{key}:detect_naive_raw": bool(th.raw_lo_one_sided > 0), f"{key}:mean_s": th.mean_s, f"{key}:mean_D": th.mean_D})
        if not main:
            continue
        v = run.valid
        out.update({"I_rate": float(run.I.mean()), "F_day_rate": float(run.F.any(axis=1).mean()), "dM_frac": float(np.mean(run.delta_m[v])),
                    "dR_frac": float(np.mean(run.delta_r[v])), "n_valid": int(v.sum())})
        h5 = h5_event_test(run.legs.rev.asset_pnl_next, run.excl, IP, rng)
        out.update({f"h5_{k}": val for k, val in h5.items()})
        if kind in ("N2", "N0", "N1") or task.get("assoc", False):
            for dn, dv in (("dM", run.delta_m), ("dR", run.delta_r)):
                for zn, zv in (("zV", run.env.zV), ("zPhiP", run.env.zPhi_perp), ("C", run.conc.C)):
                    a = delta_association(dv, zv, v, IP, rng)
                    out[f"assoc:{dn}:{zn}:reject"] = a["reject"]
                    out[f"assoc:{dn}:{zn}:diff"] = a["diff"]
        if kind in ("regime", "informed"):
            out.update({f"rec:{k}": val for k, val in recovery_summary(w.quadrant, w.delta_m, w.delta_r, run).items()})
        if kind == "informed" or spec.informed_per_year > 0:
            out.update(informed_event_stats(w, run, SPECS[rn].L + SPECS[rn].H + 2))
    return out


def delay_task(task: dict) -> dict:
    """Detection delay in a switching world with only two crowds (planted M-crowd: I<->IV; R-crowd: II<->IV)."""
    which, seed, effect, dwell = task["which"], task["seed"], task["effect"], task["dwell"]
    used = (0, 3) if which == "M" else (1, 3)
    md = (dwell, dwell, dwell, dwell)
    spec = WorldSpec(kind="regime", seed=seed, effect=effect, states_used=used, mean_dwell=md, dwell_disp=6.0)
    w = generate(spec)
    mom, rev = task.get("mom_spec", MOM_MAIN), task.get("rev_spec", REV_MAIN)
    run = run_state_pipeline(w.ret, _CAL, mom, rev, with_portfolio=False)
    sp = StateParams()
    if which == "M":
        truth, tau, spec_used = w.delta_m, run.tau_m, mom
        mr = run.mr_m
    else:
        truth, tau, spec_used = w.delta_r, run.tau_r, rev
        mr = run.mr_r
    delays, n = crossing_delays(truth, tau, sp.c_in, min_post=int(dwell * 0.5), min_pre=30)
    return {"which": which, "seed": seed, "effect": effect, "dwell": dwell, "spec": spec_used.name, "delays": delays, "n_switch": n,
            "n_eff": float(np.nanmean(mr.n_eff[200:])), "auc": float(recovery_summary(w.quadrant, w.delta_m, w.delta_r, run)["auc_M" if which == "M" else "auc_R"])}


def run_pool(fn, tasks: list, cal: dict, workers: int = 4) -> list:
    with Pool(workers, initializer=_init, initargs=(cal,)) as pool:
        return pool.map(fn, tasks, chunksize=2)


def rate_table(df: pd.DataFrame, group: str, col: str) -> pd.DataFrame:
    rows = []
    for g, d in df.groupby(group):
        k, n = int(d[col].sum()), int(len(d))
        lo, hi = cp_interval(k, n)
        rows.append({group: g, "n": n, "k": k, "rate": k / n, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def working_bias_check(cal: dict, n_sims: int = 20, seed0: int = 500_000) -> dict:
    """N4 world: observed close = true price +- half spread, settlement = intraday average. Lag-1 autocorrelation of the
    standardised returns and the strategy-matched rho of R-B / R-A / M-B computed from CLOSE and from SETTLE prices.
    Theory: settle averaging gives ac1 close to +0.25 (Working 1960); close prices carry Roll's negative bounce."""
    from .statevars import mean_sq_corr, mr_stat, standardise

    res = {k: [] for k in ("ac1_close", "ac1_settle", "rhoRB_close", "rhoRB_settle", "rhoRBgap_close", "rhoRBgap_settle", "rhoRA_close", "rhoRA_settle", "rhoMB_close", "rhoMB_settle")}
    for k in range(n_sims):
        w = generate(WorldSpec(kind="N4", seed=seed0 + k, n_days=1500, n_assets=30))
        close_ret = w.ret
        settle_ret = np.diff(np.log(w.settle), axis=0, prepend=np.nan)
        for name, r in (("close", close_ret), ("settle", settle_ret)):
            rt, _ = standardise(r)
            a, b = rt[1:], rt[:-1]
            ok = np.isfinite(a) & np.isfinite(b)
            res[f"ac1_{name}"].append(float(np.sum(a[ok] * b[ok]) / np.sqrt(np.sum(a[ok] ** 2) * np.sum(b[ok] ** 2))))
            r2, nf = mean_sq_corr(rt)
            for sp_name, key in (("R-B", "rhoRB"), ("R-B-gap", "rhoRBgap"), ("R-A", "rhoRA"), ("M-B", "rhoMB")):
                st = mr_stat(rt, SPECS[sp_name], r2, nf)
                sign = -1 if sp_name.startswith("R") else 1
                res[f"{key}_{name}"].append(float(np.nanmean(sign * (st.rho - cal[sp_name]["bias"]))))
    return {k: float(np.mean(v)) for k, v in res.items()}
