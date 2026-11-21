"""Hysteresis state machine with minimum dwell (doc 4.2) and the quadrant / selection-signal mapping (doc 0.3, 0.4)."""

from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def _hyst(tau, c_in, c_out, d_min):
    T = tau.shape[0]
    out = np.zeros(T, dtype=np.int8)
    started = np.zeros(T, dtype=np.bool_)
    cur = 0
    last_switch = -10**9
    for t in range(T):
        x = tau[t]
        if np.isnan(x):
            out[t] = cur
            continue
        started[t] = True
        want = cur
        if x >= c_in:
            want = 1
        elif x <= c_out:
            want = 0
        if want != cur and (t - last_switch) >= d_min:
            cur = want
            last_switch = t
        out[t] = cur
    return out, started


def hysteresis(tau: np.ndarray, c_in: float = 1.28, c_out: float = 0.5, d_min: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """delta_t = 1 when tau >= c_in, 0 when tau <= c_out, previous value in between. After a switch at t0 no further
    switch is allowed on [t0, t0 + d_min). Returns (delta in {0,1}, valid) where valid marks days with a defined tau."""
    d, v = _hyst(np.asarray(tau, dtype=float), c_in, c_out, int(d_min))
    return d.astype(float), v


def selection_signal(delta_m: np.ndarray, delta_r: np.ndarray) -> np.ndarray:
    """s_t = delta^M - delta^R in {-1, 0, +1}."""
    return delta_m - delta_r


QUADRANT = {(1, 0): "I", (0, 1): "II", (1, 1): "III", (0, 0): "IV"}


def quadrant_labels(delta_m: np.ndarray, delta_r: np.ndarray) -> np.ndarray:
    lab = np.empty(len(delta_m), dtype=object)
    for i, (a, b) in enumerate(zip(delta_m, delta_r)):
        lab[i] = QUADRANT[(int(a), int(b))]
    return lab


def segments(labels: np.ndarray, state: str, min_len: int = 1) -> list[tuple[int, int]]:
    """Contiguous runs [start, end) of `state` with length >= min_len."""
    mask = labels == state
    runs, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if i - start >= min_len:
                runs.append((start, i))
            start = None
    if start is not None and len(mask) - start >= min_len:
        runs.append((start, len(mask)))
    return runs
