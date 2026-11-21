"""Checks of the state machinery against planted truth (synthetic worlds only): AUC, quadrant confusion, detection delay."""

from __future__ import annotations

import numpy as np

from .config import LegSpec, kappa_LH, pairs_in_window


def auc(score: np.ndarray, label: np.ndarray) -> float:
    """Mann-Whitney AUC of `score` for label==1 (ties averaged)."""
    ok = np.isfinite(score)
    s, y = score[ok], label[ok].astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = _rank(s)
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _rank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    xs = x[order]
    i = 0
    n = len(x)
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


QUAD_NAMES = ("I", "II", "III", "IV")


def recovery_summary(quad_true: np.ndarray, delta_m_true, delta_r_true, run) -> dict:
    v = run.valid
    out = {
        "auc_M": auc(run.tau_m[v], delta_m_true[v]),
        "auc_R": auc(run.tau_r[v], delta_r_true[v]),
    }
    est = np.array([-1 if q is None else QUAD_NAMES.index(q) for q in run.quad])
    for k, name in enumerate(QUAD_NAMES):
        m = v & (quad_true == k)
        out[f"P(dM=1|{name})"] = float(np.mean(run.delta_m[m])) if m.any() else float("nan")
        out[f"P(dR=1|{name})"] = float(np.mean(run.delta_r[m])) if m.any() else float("nan")
        out[f"tauM|{name}"] = float(np.nanmean(run.tau_m[m])) if m.any() else float("nan")
        out[f"tauR|{name}"] = float(np.nanmean(run.tau_r[m])) if m.any() else float("nan")
    out["quad_accuracy"] = float(np.mean(est[v] == quad_true[v]))
    return out


def crossing_delays(truth: np.ndarray, tau: np.ndarray, c_in: float, min_post: int, min_pre: int = 30) -> tuple[list[int], int]:
    """For every 0 -> 1 switch of the planted indicator that is followed by >= `min_post` days in state 1 (and preceded by
    >= `min_pre` days of 0 during which tau was below c_in on the day before the switch), the delay until tau first
    reaches c_in. Returns (delays of detected switches, number of eligible switches); undetected within the planted
    dwell counts as missed."""
    T = len(truth)
    delays, n = [], 0
    t = 1
    while t < T:
        if truth[t] == 1 and truth[t - 1] == 0:
            end = t
            while end < T and truth[end] == 1:
                end += 1
            pre_ok = t >= min_pre and truth[t - min_pre : t].sum() == 0
            if pre_ok and (end - t) >= min_post and np.isfinite(tau[t - 1]) and tau[t - 1] < c_in:
                n += 1
                hit = np.flatnonzero(tau[t:end] >= c_in)
                if len(hit):
                    delays.append(int(hit[0]))
            t = end
        else:
            t += 1
    return delays, n


def d_star(spec: LegSpec, c: float, n_eff: float, delta_rho: float) -> dict:
    """Doc 4.3: d*_min = (L+H-1) + c^2 kappa / (N_eff delta_rho^2), plus the window-specific prediction for the actual
    window W: first crossing of c*se by the linear ramp (d/T) delta_rho:  d_W = (L+H-1+gap) + c sqrt(kappa T / N_eff) / delta_rho."""
    kap = kappa_LH(spec.L, spec.H)
    T = pairs_in_window(spec)
    lead = spec.L + spec.H - 1 + spec.gap
    t_star = c**2 * kap / (n_eff * delta_rho**2)
    return {
        "d_star": lead + t_star,
        "T_star": t_star,
        "window_rule": lead + 2 * t_star,
        "d_window": lead + c * np.sqrt(kap * T / n_eff) / delta_rho,
        "kappa": kap,
        "T_pairs": T,
    }
