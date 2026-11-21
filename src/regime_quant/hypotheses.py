"""Hypothesis tests of docs/state-construction.md section 8 that belong to steps 1-2 (H0..H8, H10..H13; H9 is a step-4 comparison).

Every test returns plain dicts so that synthetic (step 1) and real (step 2) reports use the same code.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import t as student_t

from .config import InferenceParams
from .inference import mean_diff_test, stationary_bootstrap_indices, theta_test


def event_runs(active: np.ndarray) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, a in enumerate(active):
        if a and start is None:
            start = i
        elif not a and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(active)))
    return runs


def h5_event_test(asset_pnl_rev: np.ndarray, excl: np.ndarray, ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None, min_events: int = 5) -> dict:
    """H5 (doc 2.5 / 8): on days when some asset is inside its exclusion window (flagged within the last K_I days),
    reversal pnl of flagged assets minus reversal pnl of the other assets. Prediction: < 0.
    `asset_pnl_rev[t, i]` = counterfactual per-asset reversal pnl of day t+1 in risk units (position * return / vol),
    NOT zeroed by the exclusion. Unit of resampling = event (maximal run of active days), since days inside an event
    are strongly dependent. One-sided p = share of bootstrap means >= 0."""
    rng = rng or np.random.default_rng(0)
    pnl = asset_pnl_rev
    active = excl.any(axis=1) & np.isfinite(np.nansum(pnl, axis=1))
    in_f = excl & np.isfinite(pnl)
    out_f = ~excl & np.isfinite(pnl)
    nf, nc = in_f.sum(axis=1), out_f.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mf = np.where(in_f, pnl, 0.0).sum(axis=1) / nf
        mc = np.where(out_f, pnl, 0.0).sum(axis=1) / nc
    d = mf - mc
    use = active & (nf > 0) & (nc > 0) & np.isfinite(d)
    runs = [r for r in event_runs(use)]
    res = {"n_events": len(runs), "n_days": int(use.sum()), "diff": float("nan"), "mean_F": float("nan"), "mean_Fc": float("nan"),
           "ci_lo": float("nan"), "ci_hi": float("nan"), "p_neg": 1.0, "reject": False, "underpowered": len(runs) < min_events}
    if len(runs) < 2:
        return res
    sums = np.array([d[a:b].sum() for a, b in runs])
    cnt = np.array([b - a for a, b in runs], dtype=float)
    idx = rng.integers(0, len(runs), size=(ip.n_boot, len(runs)))
    boot = sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    point = sums.sum() / cnt.sum()
    lo, hi = np.quantile(boot, [(1 - ip.ci_level) / 2, 1 - (1 - ip.ci_level) / 2])
    p_boot = float((1 + (boot >= 0).sum()) / (1 + len(boot)))
    # decision p: one-sample t-test on event-level means (df = events - 1). With a handful of heavy-tailed events the
    # percentile bootstrap is anti-conservative (about 9-10% false rejections at ~14 events in world N2b).
    ev_means = sums / cnt
    se = ev_means.std(ddof=1) / np.sqrt(len(ev_means))
    p_neg = float(student_t.cdf(ev_means.mean() / se, df=len(ev_means) - 1)) if se > 0 else 1.0
    res.update(p_boot=p_boot, ev_mean=float(ev_means.mean()), diff=float(point), mean_F=float(np.nanmean(mf[use])), mean_Fc=float(np.nanmean(mc[use])), ci_lo=float(lo), ci_hi=float(hi),
               p_neg=p_neg, reject=bool(ev_means.mean() < 0 and p_neg < ip.alpha and len(runs) >= min_events))
    return res


def delta_association(delta: np.ndarray, z: np.ndarray, valid: np.ndarray, ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None) -> dict:
    """Association of a state indicator with an environment variable: mean(z | delta=1) - mean(z | delta=0), cyclic-shift p.
    `std_diff` is the difference in units of the sd of z over the valid days (comparable across variables and worlds)."""
    ok = valid & np.isfinite(z)
    d = delta[ok] == 1
    res = mean_diff_test(z[ok], d, ~d, ip, rng)
    sd = float(np.std(z[ok])) if ok.any() else float("nan")
    return {"diff": res.diff, "std_diff": res.diff / sd if sd > 0 else float("nan"), "p": res.p_shift, "reject": bool(res.p_shift < ip.alpha), "n1": res.n_a, "n0": res.n_b}
