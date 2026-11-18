"""Stationary block bootstrap and performance metrics. Every reported number carries an interval."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS


def stationary_bootstrap_indices(
    n: int, mean_block: int, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    """Politis-Romano stationary bootstrap index matrix of shape (n_boot, n)."""
    p = 1.0 / mean_block
    starts = rng.integers(0, n, size=(n_boot, n))
    new_block = rng.random((n_boot, n)) < p
    new_block[:, 0] = True
    idx = np.empty((n_boot, n), dtype=np.int64)
    idx[:, 0] = starts[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(new_block[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def _ci(draws: np.ndarray, level: float) -> tuple[float, float]:
    a = (1.0 - level) / 2.0
    return float(np.quantile(draws, a)), float(np.quantile(draws, 1.0 - a))


def sharpe(x: np.ndarray) -> float:
    sd = np.std(x, ddof=1)
    return float(np.mean(x) / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")


def max_drawdown(ret: pd.Series) -> float:
    cum = ret.cumsum()
    return float((cum - cum.cummax()).min())


def performance_summary(
    ret: pd.Series, rng: np.random.Generator, n_boot: int, mean_block: int, ci_level: float
) -> dict:
    r = ret.dropna().to_numpy()
    idx = stationary_bootstrap_indices(len(r), mean_block, n_boot, rng)
    boot = r[idx]
    sr = boot.mean(axis=1) / boot.std(axis=1, ddof=1) * np.sqrt(TRADING_DAYS)
    lo, hi = _ci(sr, ci_level)
    return {
        "ann_ret": float(r.mean() * TRADING_DAYS),
        "ann_vol": float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "sharpe": sharpe(r),
        "sharpe_lo": lo,
        "sharpe_hi": hi,
        "max_dd": max_drawdown(ret.dropna()),
    }


def group_mean_diff_ci(
    x: np.ndarray,
    hi_mask: np.ndarray,
    lo_mask: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
    mean_block: int,
    ci_level: float,
) -> dict:
    """mean(x | hi) - mean(x | lo) with a block-bootstrap CI. Time indices are resampled in blocks,
    carrying x and the group labels together so serial dependence in both is preserved."""
    n = len(x)
    idx = stationary_bootstrap_indices(n, mean_block, n_boot, rng)
    xb, hb, lb = x[idx], hi_mask[idx], lo_mask[idx]
    with np.errstate(invalid="ignore", divide="ignore"):
        mh = (xb * hb).sum(axis=1) / hb.sum(axis=1)
        ml = (xb * lb).sum(axis=1) / lb.sum(axis=1)
    diff = mh - ml
    diff = diff[np.isfinite(diff)]
    point = float(x[hi_mask].mean() - x[lo_mask].mean())
    lo, hi = _ci(diff, ci_level) if len(diff) > 10 else (float("nan"), float("nan"))
    return {"diff": point, "ci_lo": lo, "ci_hi": hi}
