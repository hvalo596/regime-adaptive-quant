"""Vectorised rolling helpers (NaN-aware, cumulative-sum based, no look-ahead: row t uses rows t-w+1..t only)."""

from __future__ import annotations

import numpy as np


def roll_sum(a: np.ndarray, w: int, lag: int = 0) -> np.ndarray:
    """Sum over the last `w` rows ending at row t-`lag`. NaN counts as 0 (pair with `roll_count`).
    Rows without a full window of history are NaN."""
    a = np.nan_to_num(np.asarray(a, dtype=float), nan=0.0)
    c = np.cumsum(a, axis=0)
    zero = np.zeros((1,) + a.shape[1:])
    c = np.concatenate([zero, c], axis=0)
    out = np.full(a.shape, np.nan)
    if w + lag <= a.shape[0]:
        # window rows [t-lag-w+1, t-lag]  ->  c[t-lag+1] - c[t-lag-w+1]
        t = np.arange(w + lag - 1, a.shape[0])
        out[t] = c[t - lag + 1] - c[t - lag - w + 1]
    return out


def roll_count(valid: np.ndarray, w: int, lag: int = 0) -> np.ndarray:
    return roll_sum(np.asarray(valid, dtype=float), w, lag)


def roll_mean(a: np.ndarray, w: int, lag: int = 0, min_count: int | None = None) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    s = roll_sum(a, w, lag)
    n = roll_count(~np.isnan(a), w, lag)
    need = w if min_count is None else min_count
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n >= need, s / n, np.nan)


def expanding_window_mean(a: np.ndarray, w: int, min_count: int, lag: int = 0) -> np.ndarray:
    """Mean over the last up-to-`w` valid rows ending at row t-lag; needs at least `min_count` valid rows."""
    a = np.asarray(a, dtype=float)
    T = a.shape[0]
    x = np.nan_to_num(a, nan=0.0)
    v = (~np.isnan(a)).astype(float)
    cx = np.concatenate([np.zeros((1,) + a.shape[1:]), np.cumsum(x, axis=0)])
    cv = np.concatenate([np.zeros((1,) + a.shape[1:]), np.cumsum(v, axis=0)])
    out = np.full(a.shape, np.nan)
    t = np.arange(lag, T)
    hi = t - lag + 1
    lo = np.maximum(hi - w, 0)
    n = cv[hi] - cv[lo]
    s = cx[hi] - cx[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        out[t] = np.where(n >= min_count, s / n, np.nan)
    return out


def ewma_sum(a: np.ndarray, halflife: float) -> np.ndarray:
    """Exponentially weighted mean with weights decaying at `halflife`; NaN rows carry the previous value forward only
    after the series has started."""
    a = np.asarray(a, dtype=float)
    alpha = 1.0 - 0.5 ** (1.0 / halflife)
    out = np.full(a.shape, np.nan)
    cur = np.full(a.shape[1:], np.nan)
    for t in range(a.shape[0]):
        x = a[t]
        new = np.where(np.isnan(cur), x, np.where(np.isnan(x), cur, (1 - alpha) * cur + alpha * x))
        cur = new
        out[t] = cur
    return out


def shift(a: np.ndarray, k: int) -> np.ndarray:
    """Row t gets row t-k (k > 0), NaN fill."""
    out = np.full(a.shape, np.nan)
    if k == 0:
        return a.copy()
    out[k:] = a[:-k]
    return out
