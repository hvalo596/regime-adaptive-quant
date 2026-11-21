"""End-to-end state pipeline: returns panel -> variables -> state machine -> selection signal -> backtest legs/portfolio.

`run_state_pipeline` is the single entry point used by the synthetic experiments (step 1) and the real-data run (step 2),
so what is validated on synthetic data is exactly what runs on real data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .backtest import Legs, Portfolio, build_legs, run_weights, state_weights
from .config import (CostParams, LegSpec, MOM_MAIN, REV_MAIN, StateParams, min_dwell)
from .rolling import shift
from .statevars import (Concentration, Environment, FactorFit, MRStat, concentration, environment, exclusion_mask,
                        informed_indicator, loo_factor_regress, mean_sq_corr, mr_stat, standardise, tau_stat)
from .statemachine import hysteresis, quadrant_labels, selection_signal


@dataclass
class StateRun:
    mom_spec: LegSpec
    rev_spec: LegSpec
    legs: Legs
    mr_m: MRStat
    mr_r: MRStat
    tau_m: np.ndarray
    tau_r: np.ndarray
    delta_m: np.ndarray
    delta_r: np.ndarray
    valid: np.ndarray  # both taus defined
    s: np.ndarray  # selection signal, NaN where undefined
    quad: np.ndarray
    fit: FactorFit
    conc: Concentration
    I: np.ndarray
    F: np.ndarray
    excl: np.ndarray
    env: Environment
    kappa: np.ndarray
    ret: np.ndarray
    portfolio: Portfolio | None = None

    @property
    def D_next(self) -> np.ndarray:
        return self.legs.D_next


def run_state_pipeline(
    ret: np.ndarray,
    cal: dict,
    mom: LegSpec = MOM_MAIN,
    rev: LegSpec = REV_MAIN,
    sp: StateParams = StateParams(),
    cost: CostParams = CostParams(),
    with_portfolio: bool = True,
    use_exclusion: bool = True,
    use_kappa: bool = True,
    cache: dict | None = None,
) -> StateRun:
    """`cal` maps spec name -> {"bias", "se_mult"} (nullcal.calibrate). `cache` (optional dict) memoises the pieces that do
    not depend on the leg specs (standardisation, factor fit, correlation, concentration, environment) across calls."""
    cache = cache if cache is not None else {}
    if "rt" not in cache:
        rt, sig = standardise(ret, sp.vol_window, sp.clip)
        cache["rt"] = rt
        cache["fit"] = loo_factor_regress(rt, sp.factor_window)
        cache["r2bar"] = mean_sq_corr(rt)
    rt, fit = cache["rt"], cache["fit"]
    r2bar, nfull = cache["r2bar"]
    for sp_ in (mom, rev):
        if ("mr", sp_) not in cache:
            cache[("mr", sp_)] = mr_stat(rt, sp_, r2bar, nfull)
    mr_m, mr_r = cache[("mr", mom)], cache[("mr", rev)]
    tau_m = tau_stat(mr_m, "mom", cal[mom.name]["bias"], cal[mom.name]["se_mult"])
    tau_r = tau_stat(mr_r, "rev", cal[rev.name]["bias"], cal[rev.name]["se_mult"])
    dm, vm = hysteresis(tau_m, sp.c_in, sp.c_out, min_dwell(mom))
    dr, vr = hysteresis(tau_r, sp.c_in, sp.c_out, min_dwell(rev))
    valid = vm & vr
    s = selection_signal(dm, dr)
    s = np.where(valid, s, np.nan)
    quad = np.where(valid, quadrant_labels(dm, dr), None)

    if "conc" not in cache:
        conc = concentration(fit.resid, sp)
        I, F = informed_indicator(conc, sp)
        cache["conc"], cache["I"], cache["F"] = conc, I, F
        cache["env"] = environment(ret, fit.r2, sp)
    conc, I, F, env = cache["conc"], cache["I"], cache["F"], cache["env"]
    k_i = rev.L + rev.H + 2
    excl = exclusion_mask(F, k_i) if use_exclusion else np.zeros_like(F)
    state4 = np.array([(q == "IV") if q is not None else False for q in quad])
    kappa = np.where(state4 & use_kappa, sp.kappa0, 1.0)

    if "legs" not in cache:
        cache["legs"] = {}
    key = (mom, rev)
    if key not in cache["legs"]:
        cache["legs"][key] = build_legs(ret, mom, rev, sp)
    legs = cache["legs"][key]
    pf = None
    if with_portfolio:
        W = state_weights(legs, s, kappa, excl)
        pf = run_weights(ret, W, legs.vol, cost)
    return StateRun(mom, rev, legs, mr_m, mr_r, tau_m, tau_r, dm, dr, valid, s, quad, fit, conc, I, F, excl, env, kappa, ret, pf)
