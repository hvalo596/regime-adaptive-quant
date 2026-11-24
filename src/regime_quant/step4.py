"""Step 4: does recognising the state pay, net of cost, against the simple alternatives? (experiment doc step 4; state-construction 4.5)

Everything is expressed as a selection signal s_t in [-1, 1] on the two risk-scaled legs: W_t = scale_t * [ (1+s_t)/2 * W^MOM_t + (1-s_t)/2 * W^REV_t ].
  no-state       EW50 (s=0), MOM only, REV only, EW50 with volatility targeting (the 'one line of code' benchmark)
  recent-perf    TP60 (tanh of the 60-day t-statistic of D) and EWA/Hedge (exponentially weighted cumulative leg returns): states bypassed
  state-based    RULE (step-2 hysteresis), FILT-HARD, FILT-SOFT (p^M - p^R), FILT-PEN (x (1 - H/ln 4), the doc 4.6 weight),
                 FILT-BAND (no-trade band), LEARNED (tilt from shrunk state-conditional means of D)
  oracle         ORACLE (planted truth; synthetic only): upper bound of the information value
Every strategy also exists in a volatility-matched version (+VT: scaled to the same ex-ante vol with a one-day lag), because state
timing that is just 'hold less when it is loud' must not be credited to the state.
Accounting identity (gross, kappa = 1, no band): P - (x_MOM + x_REV)/2 = s D / 2, split into a constant tilt (mean s times mean D) and timing
(covariance of s and D); only timing is information about the crowd.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .backtest import Legs, next_value, run_weights
from .config import TRADING_DAYS, CostParams, InferenceParams, StateParams

# Step-4 cost model, fixed BEFORE any step-4 result was looked at: one-way cost per unit traded = 0.5 bp fee + 0.02 x ex-ante daily vol
# (about 3 bp of slippage at 1.5% daily vol, i.e. one to two ticks in liquid contracts) = about 3.5 bp. The grid 0 / 0.5 / 1 / 2 x brackets the
# draft of step 1 (1 bp + 0.05 sigma, about 8.5 bp, which falls between the 1x and 2x columns).
STEP4_COST = CostParams(fee_bps=0.5, slip_vol_frac=0.02)
from .inference import quantile_ci, sharpe, stationary_bootstrap_indices
from .rolling import roll_mean, shift


def _w(legs: Legs, s: np.ndarray, scale: np.ndarray | None = None) -> np.ndarray:
    s0 = np.nan_to_num(s, nan=0.0)
    W = ((1 + s0) / 2)[:, None] * legs.mom.weights + ((1 - s0) / 2)[:, None] * legs.rev.weights
    if scale is not None:
        W = W * np.nan_to_num(scale, nan=0.0)[:, None]
    W[np.isnan(s)] = 0.0
    return W


def band_signal(s_target: np.ndarray, band: float = 0.3) -> np.ndarray:
    """Hold the previous signal until the target moves by more than `band`."""
    out = np.full_like(s_target, np.nan)
    cur = np.nan
    for t, x in enumerate(s_target):
        if np.isnan(x):
            continue
        if np.isnan(cur) or abs(x - cur) > band:
            cur = x
        out[t] = cur
    return out


def tp_signal(D_next: np.ndarray, window: int = 60) -> np.ndarray:
    """tanh(t / 2) of the trailing `window`-day mean of D realised up to t (D_here[t] = D_next[t-1])."""
    d = shift(D_next, 1)
    m = roll_mean(d, window, min_count=window)
    m2 = roll_mean(d * d, window, min_count=window)
    sd = np.sqrt(np.maximum(m2 - m**2, 1e-18))
    return np.tanh(np.sqrt(window) * m / sd / 2.0)


def ewa_signal(x_mom_next: np.ndarray, x_rev_next: np.ndarray, target_daily: float, lam: float = 0.99, eta: float = 0.5) -> np.ndarray:
    """Hedge over the two legs with exponentially discounted cumulative scaled returns; s = 2 w_MOM - 1 = tanh(eta (S_M - S_R) / 2)."""
    xm, xr = shift(x_mom_next, 1) / target_daily, shift(x_rev_next, 1) / target_daily
    T = len(xm)
    SM = np.zeros(T)
    SR = np.zeros(T)
    sm = sr = 0.0
    out = np.full(T, np.nan)
    started = False
    for t in range(T):
        if np.isfinite(xm[t]) and np.isfinite(xr[t]):
            sm = lam * sm + xm[t]
            sr = lam * sr + xr[t]
            started = True
        if started:
            out[t] = np.tanh(eta * (sm - sr) / 2.0)
    first = np.flatnonzero(np.isfinite(shift(x_mom_next, 1)))
    if len(first):
        out[: first[0] + 60] = np.nan
    return out


def learned_tilt(D_next: np.ndarray, pm: np.ndarray, pr: np.ndarray, n0: float = 250.0) -> np.ndarray:
    """Tilt estimated from data: expected state-conditional mean of D, with each of the four quadrant means shrunk to the pooled mean
    (weight n_k / (n_k + n0), n_k the posterior mass of quadrant k seen so far), then s = tanh(m_hat / (sd(D) / sqrt(n0))). Uses D realised
    up to t only (D_here) and probabilities up to t - 1 for the estimates; the current probabilities weight the estimates."""
    T = len(D_next)
    d = shift(D_next, 1)
    quads = [(pm * pr), (pm * (1 - pr)), ((1 - pm) * pr), ((1 - pm) * (1 - pr))]  # (slow & rushed, slow only, rushed only, none)
    qprev = [shift(q, 1) for q in quads]
    out = np.full(T, np.nan)
    sw = np.zeros(4)
    sd_ = np.zeros(4)
    tot_w = 0.0
    tot_d = 0.0
    tot_d2 = 0.0
    for t in range(T):
        if np.isfinite(d[t]) and all(np.isfinite(q[t]) for q in qprev):
            for k in range(4):
                w = qprev[k][t]
                sw[k] += w
                sd_[k] += w * d[t]
            tot_w += 1.0
            tot_d += d[t]
            tot_d2 += d[t] ** 2
        if tot_w > 100 and all(np.isfinite(q[t]) for q in quads):
            pooled = tot_d / tot_w
            sdD = np.sqrt(max(tot_d2 / tot_w - pooled**2, 1e-18))
            mk = np.where(sw > 0, sd_ / np.maximum(sw, 1e-9), pooled)
            lam = sw / (sw + n0)
            mk = pooled + lam * (mk - pooled)
            m_hat = sum(quads[k][t] * mk[k] for k in range(4))
            out[t] = np.tanh(m_hat / (sdD / np.sqrt(n0)))
    return out


# ------------------------------------------------------------------------------------------------ evaluation


@dataclass
class Strategy:
    name: str
    s: np.ndarray
    vt: bool = False


@dataclass
class Evaluated:
    name: str
    gross: np.ndarray  # return realised on day t+1 of the position decided at t (decision-day indexing)
    net: dict  # cost multiplier -> net series
    turnover: np.ndarray
    s: np.ndarray
    scale: np.ndarray | None = None


def vt_scale(legs: Legs, s: np.ndarray, ret: np.ndarray, sp: StateParams, cap: float = 3.0) -> np.ndarray:
    """Ex-ante vol scaling of a strategy: scale_t = min(target / sigma_hat_t, cap), sigma_hat_t = std of the strategy's own unscaled
    returns realised up to t (60 days)."""
    W = _w(legs, s)
    r_next = np.nan_to_num(next_value(ret), nan=0.0)
    g_next = (W * r_next).sum(axis=1)
    g_next[np.isnan(s)] = np.nan
    g_here = shift(g_next, 1)
    m = roll_mean(g_here, 60, min_count=40)
    m2 = roll_mean(g_here**2, 60, min_count=40)
    sd = np.sqrt(np.maximum(m2 - m**2, 1e-18))
    target = sp.target_ann_vol / np.sqrt(TRADING_DAYS)
    return np.minimum(target / sd, cap)


def evaluate(legs: Legs, ret: np.ndarray, strat: Strategy, sp: StateParams = StateParams(), cost_mults=(0.0, 0.5, 1.0, 2.0), base_cost: CostParams = STEP4_COST) -> Evaluated:
    scale = vt_scale(legs, strat.s, ret, sp) if strat.vt else None
    W = _w(legs, strat.s, scale)
    net = {}
    gross = None
    turn = None
    for m in cost_mults:
        pf = run_weights(ret, W, legs.vol, CostParams(base_cost.fee_bps * m, base_cost.slip_vol_frac * m))
        if gross is None:
            gross, turn = pf.gross_next.copy(), pf.turnover
        net[m] = pf.net_next
    return Evaluated(strat.name + ("+VT" if strat.vt else ""), gross, net, turn, strat.s, scale)


def perf(x: np.ndarray) -> dict:
    x = x[np.isfinite(x)]
    if len(x) < 50:
        return {"n": len(x), "ann_mean": np.nan, "ann_vol": np.nan, "sharpe": np.nan, "max_dd": np.nan}
    cum = np.cumsum(x)
    return {"n": len(x), "ann_mean": float(x.mean() * TRADING_DAYS), "ann_vol": float(x.std(ddof=1) * np.sqrt(TRADING_DAYS)), "sharpe": sharpe(x), "max_dd": float((cum - np.maximum.accumulate(cum)).min())}


def paired_sharpe_diff(a: np.ndarray, b: np.ndarray, ip: InferenceParams, rng: np.random.Generator) -> dict:
    """Sharpe(a) - Sharpe(b) with a paired stationary-block-bootstrap interval and a one-sided p (a > b)."""
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = len(a)
    if n < 250:
        return {"diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "p_gt": 1.0, "n": n}
    idx = stationary_bootstrap_indices(n, ip.mean_block, ip.n_boot, rng)
    ab, bb = a[idx], b[idx]
    sa = ab.mean(1) / ab.std(1, ddof=1) * np.sqrt(TRADING_DAYS)
    sb = bb.mean(1) / bb.std(1, ddof=1) * np.sqrt(TRADING_DAYS)
    d = sa - sb
    lo, hi = quantile_ci(d, ip.ci_level)
    point = sharpe(a) - sharpe(b)
    p_gt = float((1 + (d <= 0).sum()) / (1 + len(d)))
    return {"diff": float(point), "ci_lo": lo, "ci_hi": hi, "p_gt": p_gt, "n": n}


def selection_decomposition(s: np.ndarray, D_next: np.ndarray) -> dict:
    """Gross selection account  mean(s D / 2)  =  tilt (mean s * mean D / 2) + timing (cov(s, D) / 2); annualised."""
    ok = np.isfinite(s) & np.isfinite(D_next)
    if ok.sum() < 100:
        return {}
    s, d = s[ok], D_next[ok]
    tot = float(np.mean(s * d) / 2)
    tilt = float(s.mean() * d.mean() / 2)
    timing = float((np.mean(s * d) - s.mean() * d.mean()) / 2)
    return {"selection_ann": tot * TRADING_DAYS, "tilt_ann": tilt * TRADING_DAYS, "timing_ann": timing * TRADING_DAYS, "mean_s": float(s.mean()), "mean_abs_s": float(np.abs(s).mean())}
