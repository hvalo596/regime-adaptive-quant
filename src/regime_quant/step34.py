"""Glue for steps 3 and 4: filtered states from the step-1/2 pipeline, the strategy menu of step 4, and the summary tables."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from .config import MOM_MAIN, REV_MAIN, InferenceParams, StateParams, TRADING_DAYS
from .inference import theta_test
from .pipeline import StateRun, run_state_pipeline
from .step3 import ChainSpec, Increments, RollingFilter, bocpd, increments, rolling_filter, soft_signal
from .step4 import (Evaluated, Strategy, band_signal, evaluate, ewa_signal, learned_tilt, paired_sharpe_diff, perf, selection_decomposition, tp_signal)


@dataclass
class States:
    run: StateRun
    incM: Increments
    incR: Increments
    rfM: RollingFilter
    rfR: RollingFilter
    cache: dict

    @property
    def pm(self) -> np.ndarray:
        return self.rfM.p

    @property
    def pr(self) -> np.ndarray:
        return self.rfR.p

    @property
    def pm_g(self) -> np.ndarray:
        return self.rfM.p_guard

    @property
    def pr_g(self) -> np.ndarray:
        return self.rfR.p_guard


def build_states(ret: np.ndarray, cal: dict, cs: ChainSpec = ChainSpec(), refit_every: int = 250, min_train: int = 750, min_assets: int = 5, cache: dict | None = None, sticky: bool = True,
                 xR: np.ndarray | None = None) -> States:
    cache = cache if cache is not None else {}
    run = run_state_pipeline(ret, cal, with_portfolio=False, min_assets=min_assets, cache=cache)
    rt = run.legs.rt
    rM = cache.get(("r2bar", max(MOM_MAIN.W, 40)), (None, None))[0]
    rR = cache.get(("r2bar", max(REV_MAIN.W, 40)), (None, None))[0]
    incM = increments(rt, MOM_MAIN, rM, min_assets)
    incR = increments(rt, REV_MAIN, rR, min_assets)
    csM = replace(cs, min_sojourn=float(MOM_MAIN.L + MOM_MAIN.H)) if sticky else cs
    csR = replace(cs, min_sojourn=float(REV_MAIN.L + REV_MAIN.H)) if sticky else cs
    rfM = rolling_filter(incM, csM, refit_every, min_train)
    rfR = rolling_filter(incR, replace(csR, covariate=cs.covariate), refit_every, min_train, x=xR)
    return States(run, incM, incR, rfM, rfR, cache)


def signals(st: States, truth: tuple | None = None, sp: StateParams = StateParams()) -> dict[str, np.ndarray]:
    pm, pr = st.pm, st.pr
    D = st.run.D_next
    legs = st.run.legs
    target = sp.target_ann_vol / np.sqrt(TRADING_DAYS)
    hard = (pm > 0.5).astype(float) - (pr > 0.5).astype(float)
    hard[np.isnan(pm) | np.isnan(pr)] = np.nan
    pen = soft_signal(pm, pr, True)
    out = {
        "EW50": np.zeros(len(D)),
        "MOM": np.ones(len(D)),
        "REV": -np.ones(len(D)),
        "TP60": tp_signal(D),
        "EWA": ewa_signal(legs.mom.x_next, legs.rev.x_next, target),
        "RULE": st.run.s.copy(),
        "FILT-HARD": hard,
        "FILT-SOFT": soft_signal(pm, pr, False),
        "FILT-PEN": pen,
        "FILT-BAND": band_signal(pen),
        "FILT-PEN-G": soft_signal(st.pm_g, st.pr_g, True),
        "FILT-HARD-G": np.where(np.isnan(st.pm_g) | np.isnan(st.pr_g), np.nan, (st.pm_g > 0.5).astype(float) - (st.pr_g > 0.5).astype(float)),
        "LEARNED": learned_tilt(D, pm, pr),
    }
    if truth is not None:
        dm, dr = truth
        out["ORACLE"] = np.where(np.isfinite(pm), dm - dr, np.nan)
    return out


def evaluate_all(st: States, sig: dict[str, np.ndarray], ret: np.ndarray, sp: StateParams = StateParams(), cost_mults=(0.0, 0.5, 1.0, 2.0), with_vt: bool = True) -> tuple[dict[str, Evaluated], np.ndarray]:
    ev: dict[str, Evaluated] = {}
    for k, s in sig.items():
        ev[k] = evaluate(st.run.legs, ret, Strategy(k, s, False), sp, cost_mults)
        if with_vt:
            ev[k + "+VT"] = evaluate(st.run.legs, ret, Strategy(k, s, True), sp, cost_mults)
    common = np.isfinite(st.run.D_next)
    for k, s in sig.items():
        common &= np.isfinite(s)
    for e in ev.values():
        common &= np.isfinite(e.gross)
        if e.scale is not None:
            common &= np.isfinite(e.scale)
    first = np.flatnonzero(common)[0] if common.any() else 0
    common[:first] = False
    return ev, common


def perf_table(ev: dict[str, Evaluated], common: np.ndarray, costs=(0.0, 0.5, 1.0, 2.0)) -> pd.DataFrame:
    rows = []
    for k, e in ev.items():
        row = {"strategy": k, "n_days": int(common.sum()), "turnover_per_day": float(np.nanmean(e.turnover[common]))}
        for m in costs:
            p = perf(e.net[m][common])
            row.update({f"ann_mean_c{m}": p["ann_mean"], f"ann_vol_c{m}": p["ann_vol"], f"sharpe_c{m}": p["sharpe"], f"max_dd_c{m}": p["max_dd"]})
        rows.append(row)
    return pd.DataFrame(rows)


def comparison_table(ev: dict[str, Evaluated], common: np.ndarray, pairs: list[tuple[str, str]], ip: InferenceParams, rng: np.random.Generator, cost: float = 1.0) -> pd.DataFrame:
    rows = []
    for a, b in pairs:
        if a not in ev or b not in ev:
            continue
        for c in (0.0, cost):
            r = paired_sharpe_diff(np.where(common, ev[a].net[c], np.nan), np.where(common, ev[b].net[c], np.nan), ip, rng)
            rows.append({"a": a, "b": b, "cost_mult": c, **r})
    return pd.DataFrame(rows)


def holm(p: np.ndarray) -> np.ndarray:
    n = len(p)
    order = np.argsort(p)
    adj = np.empty(n)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (n - rank) * p[i])
        adj[i] = min(run, 1.0)
    return adj


def theta_rows(st: States, sig: dict[str, np.ndarray], common: np.ndarray, ip: InferenceParams, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    D = np.where(common, st.run.D_next, np.nan)
    for k in ("RULE", "FILT-HARD", "FILT-SOFT", "FILT-PEN", "FILT-BAND", "FILT-PEN-G", "FILT-HARD-G", "LEARNED", "TP60", "EWA", "ORACLE"):
        if k not in sig:
            continue
        th = theta_test(np.where(common, sig[k], np.nan), D, ip, rng)
        rows.append({"signal": k, "n": th.n, "theta_raw": th.theta_raw, "theta_c": th.theta_c, "ci_lo": th.ci_lo, "ci_hi": th.ci_hi, "p_shift": th.p_shift, "detect": th.detect, "mean_s": th.mean_s})
    return pd.DataFrame(rows)
