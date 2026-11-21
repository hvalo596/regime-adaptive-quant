"""Inference tools: stationary block bootstrap, cyclic-shift null, the Theta test, state-conditional mean differences.

Doc section 8 preamble: every test = block-bootstrap interval + cyclic-shift null (+ pipeline-level null from the
synthetic controls, see experiments). Theta is tested in its CENTRED form (see `theta_test`): a nonzero E[s] times a
nonzero E[D] (e.g. a plain momentum premium) is allocation tilt, not state timing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from .config import TRADING_DAYS, InferenceParams


@njit(cache=True)
def _sb_idx(n, p, starts, new_block):
    nb = starts.shape[0]
    idx = np.empty((nb, n), dtype=np.int64)
    for b in range(nb):
        idx[b, 0] = starts[b, 0]
        for t in range(1, n):
            if new_block[b, t]:
                idx[b, t] = starts[b, t]
            else:
                nxt = idx[b, t - 1] + 1
                idx[b, t] = nxt if nxt < n else 0
    return idx


def stationary_bootstrap_indices(n: int, mean_block: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano stationary bootstrap index matrix of shape (n_boot, n)."""
    starts = rng.integers(0, n, size=(n_boot, n))
    new_block = rng.random((n_boot, n)) < 1.0 / mean_block
    new_block[:, 0] = True
    return _sb_idx(n, 1.0 / mean_block, starts, new_block)


def quantile_ci(draws: np.ndarray, level: float) -> tuple[float, float]:
    a = (1.0 - level) / 2.0
    return float(np.quantile(draws, a)), float(np.quantile(draws, 1.0 - a))


def sharpe(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    sd = np.std(x, ddof=1)
    return float(np.mean(x) / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")


def cov_rows(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Row-wise population covariance of (n_rows, n) arrays."""
    return (s * d).mean(axis=1) - s.mean(axis=1) * d.mean(axis=1)


def shift_indices(n: int, min_shift: int, n_shift: int, rng: np.random.Generator) -> np.ndarray:
    lags = rng.integers(min_shift, n - min_shift, size=n_shift)
    return (np.arange(n)[None, :] + lags[:, None]) % n


@dataclass
class ThetaResult:
    n: int
    theta_raw: float  # E[s D], doc definition
    theta_c: float  # Cov(s, D): centred form, used for decisions
    ci_lo: float  # two-sided ci_level interval of theta_c (block bootstrap)
    ci_hi: float
    lo_one_sided: float  # lower end of the one-sided (1-alpha) bound
    p_shift: float  # one-sided p of theta_c under cyclic shifts
    p_shift_raw: float
    detect: bool
    mean_s: float
    mean_D: float
    raw_lo_one_sided: float = float("nan")  # naive reading of the doc: bootstrap lower bound of E[sD] itself


def theta_test(s: np.ndarray, D: np.ndarray, ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None) -> ThetaResult:
    """Theta = E[s_t D_{t+1}] > 0 (doc 0.4). `D` is indexed by decision day (D_next).
    theta_c = Cov(s, D) is the decision statistic: it equals theta_raw - E[s] E[D], so a pure tilt toward the leg with the
    higher unconditional mean (E[s] != 0, E[D] != 0) is not counted as state timing. The cyclic-shift null (doc section 8)
    centres this automatically, and the bootstrap CI is made for the same centred statistic.
    detect = shift p < alpha AND the one-sided bootstrap lower bound > 0 (doc 8: either failing falsifies)."""
    rng = rng or np.random.default_rng(0)
    ok = np.isfinite(s) & np.isfinite(D)
    s, D = s[ok], D[ok]
    n = len(s)
    if n < 4 * ip.min_shift or np.std(s) == 0:
        return ThetaResult(n, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), 1.0, 1.0, False, float(np.mean(s)) if n else float("nan"), float(np.mean(D)) if n else float("nan"))
    raw = float(np.mean(s * D))
    tc = float(np.mean(s * D) - np.mean(s) * np.mean(D))
    idx = stationary_bootstrap_indices(n, ip.mean_block, ip.n_boot, rng)
    boots = cov_rows(s[idx], D[idx])
    ci = quantile_ci(boots, ip.ci_level)
    lo1 = float(np.quantile(boots, ip.alpha))
    raw_lo = float(np.quantile((s[idx] * D[idx]).mean(axis=1), ip.alpha))
    sh = shift_indices(n, ip.min_shift, ip.n_shift, rng)
    null_c = cov_rows(s[sh], np.broadcast_to(D, sh.shape))
    null_raw = (s[sh] * D[None, :]).mean(axis=1)
    p = float((1 + (null_c >= tc).sum()) / (1 + len(null_c)))
    p_raw = float((1 + (null_raw >= raw).sum()) / (1 + len(null_raw)))
    return ThetaResult(n, raw, tc, ci[0], ci[1], lo1, p, p_raw, bool(p < ip.alpha and lo1 > 0), float(s.mean()), float(D.mean()), raw_lo)


@dataclass
class DiffResult:
    n_a: int
    n_b: int
    diff: float
    ci_lo: float
    ci_hi: float
    p_shift: float  # two-sided
    segs_a: int
    segs_b: int


def count_runs(mask: np.ndarray, min_len: int) -> int:
    runs, cur = 0, 0
    for m in mask:
        if m:
            cur += 1
        else:
            if cur >= min_len:
                runs += 1
            cur = 0
    return runs + (1 if cur >= min_len else 0)


def mean_diff_test(x: np.ndarray, a: np.ndarray, b: np.ndarray, ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None) -> DiffResult:
    """mean(x | a) - mean(x | b) with a stationary-block-bootstrap CI (x and both labels resampled together) and a
    two-sided cyclic-shift p-value (labels shifted against x). `a`, `b` are boolean masks over the same days."""
    rng = rng or np.random.default_rng(0)
    ok = np.isfinite(x)
    x0, a0, b0 = x[ok], a[ok], b[ok]
    n = len(x0)
    nan = float("nan")
    if n < 4 * ip.min_shift or a0.sum() < 3 or b0.sum() < 3:
        return DiffResult(int(a0.sum()), int(b0.sum()), nan, nan, nan, 1.0, count_runs(a0, ip.min_segment_len), count_runs(b0, ip.min_segment_len))
    point = float(x0[a0].mean() - x0[b0].mean())
    idx = stationary_bootstrap_indices(n, ip.mean_block, ip.n_boot, rng)
    xb, ab, bb = x0[idx], a0[idx], b0[idx]
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (xb * ab).sum(1) / ab.sum(1) - (xb * bb).sum(1) / bb.sum(1)
    d = d[np.isfinite(d)]
    ci = quantile_ci(d, ip.ci_level) if len(d) > 20 else (nan, nan)
    sh = shift_indices(n, ip.min_shift, ip.n_shift, rng)
    asf, bsf = a0[sh], b0[sh]
    with np.errstate(invalid="ignore", divide="ignore"):
        dn = (x0[None, :] * asf).sum(1) / asf.sum(1) - (x0[None, :] * bsf).sum(1) / bsf.sum(1)
    dn = dn[np.isfinite(dn)]
    p = float((1 + (np.abs(dn) >= abs(point)).sum()) / (1 + len(dn)))
    return DiffResult(int(a0.sum()), int(b0.sum()), point, ci[0], ci[1], p, count_runs(a0, ip.min_segment_len), count_runs(b0, ip.min_segment_len))


def mean_ci(x: np.ndarray, ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None) -> tuple[float, float, float]:
    rng = rng or np.random.default_rng(0)
    x = x[np.isfinite(x)]
    if len(x) < 30:
        return float("nan"), float("nan"), float("nan")
    idx = stationary_bootstrap_indices(len(x), ip.mean_block, ip.n_boot, rng)
    m = x[idx].mean(axis=1)
    lo, hi = quantile_ci(m, ip.ci_level)
    return float(x.mean()), lo, hi
