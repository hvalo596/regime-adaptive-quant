"""Vectorised point-in-time backtest engine and the state-selected portfolio (doc 4.5).

Timeline contract (anti-look-ahead): every array is indexed by DECISION day t. Weights in row t are computed from data
through the close of t and earn the return of day t+1. `*_next[t]` therefore holds the value realised on day t+1.

Legs: per-asset sign signal on vol-standardised returns (doc 3.3), tranche-averaged over H days (= holding period H),
sized by the inverse of ex-ante asset vol, equal risk across live assets, then scaled at LEG level to a common target
vol (rolling std of the unscaled leg's own return, through t). The leg-level scaling is what makes the exact identity of
doc 4.5 hold:  P - (x_mom + x_rev)/2 = s * D / 2  with D = x_mom - x_rev, when kappa = 1, no exclusion, zero cost.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import TRADING_DAYS, CostParams, LegSpec, StateParams
from .rolling import roll_count, roll_mean, roll_sum, shift
from .statevars import standardise, vol_exante


@dataclass
class Leg:
    spec: LegSpec
    weights: np.ndarray  # (T, N) scaled weights decided at close t (0 where flat)
    unit_weights: np.ndarray  # unscaled
    scale: np.ndarray  # (T,) leg-level scale
    x_next: np.ndarray  # (T,) scaled leg return realised on t+1
    g_next: np.ndarray  # (T,) unscaled leg return realised on t+1
    asset_pnl_next: np.ndarray  # (T, N) per-asset risk-standardised pnl: pos_i,t * r_i,t+1 / vol_i,t (position in [-1, 1])
    position: np.ndarray  # (T, N) tranche-averaged signal in [-1, 1]


def sign_signal(rt: np.ndarray, L: int) -> np.ndarray:
    valid = ~np.isnan(rt)
    X = np.where(roll_count(valid, L) >= L, roll_sum(rt, L), np.nan)
    return np.sign(X)


def leg_position(rt: np.ndarray, spec: LegSpec) -> np.ndarray:
    """Tranche-averaged signal, in [-1, 1]: mean over the last H daily signals, the newest `gap` days old."""
    s = sign_signal(rt, spec.L)
    if spec.kind == "rev":
        s = -s
    s = shift(s, spec.gap)
    return roll_mean(s, spec.H, min_count=spec.H)


def next_value(a: np.ndarray) -> np.ndarray:
    """Row t gets the value of row t+1 (last row NaN)."""
    out = np.full(a.shape, np.nan)
    out[:-1] = a[1:]
    return out


def build_leg(ret: np.ndarray, rt: np.ndarray, vol: np.ndarray, spec: LegSpec, sp: StateParams, scale_cap: float = 10.0) -> Leg:
    pos = leg_position(rt, spec)
    with np.errstate(invalid="ignore", divide="ignore"):
        unit = pos / vol
    live = ~np.isnan(unit)
    n = live.sum(axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        wu = np.where(live, unit / n[:, None], 0.0)
    wu[n == 0] = 0.0
    r_next = next_value(ret)
    r_nn = np.nan_to_num(r_next, nan=0.0)
    g_next = (wu * r_nn).sum(axis=1)
    g_next[n == 0] = np.nan
    g_next[-1] = np.nan
    g_here = shift(g_next, 1)  # g realised on day t (from the position decided at t-1)
    sig_leg = np.sqrt(roll_mean(g_here**2, sp.leg_vol_window, min_count=sp.leg_vol_window))
    target = sp.target_ann_vol / np.sqrt(TRADING_DAYS)
    with np.errstate(invalid="ignore", divide="ignore"):
        scale = np.minimum(target / sig_leg, scale_cap)
    w = wu * np.nan_to_num(scale, nan=0.0)[:, None]
    x_next = g_next * scale
    with np.errstate(invalid="ignore", divide="ignore"):
        asset_pnl = pos * r_next / vol
    return Leg(spec, w, wu, scale, x_next, g_next, asset_pnl, pos)


@dataclass
class Legs:
    mom: Leg
    rev: Leg
    vol: np.ndarray
    rt: np.ndarray
    sig_prev: np.ndarray

    @property
    def D_next(self) -> np.ndarray:
        return self.mom.x_next - self.rev.x_next


def build_legs(ret: np.ndarray, mom: LegSpec, rev: LegSpec, sp: StateParams = StateParams()) -> Legs:
    rt, sig_prev = standardise(ret, sp.vol_window, sp.clip)
    vol = vol_exante(ret, sp.vol_window)
    return Legs(build_leg(ret, rt, vol, mom, sp), build_leg(ret, rt, vol, rev, sp), vol, rt, sig_prev)


@dataclass
class Portfolio:
    weights: np.ndarray
    gross_next: np.ndarray
    cost_next: np.ndarray
    turnover: np.ndarray

    @property
    def net_next(self) -> np.ndarray:
        return self.gross_next - self.cost_next


def run_weights(
    ret: np.ndarray,
    weights: np.ndarray,
    vol: np.ndarray,
    cost: CostParams = CostParams(),
    roll_next: np.ndarray | None = None,
) -> Portfolio:
    """Gross/net daily return of a weight path. Cost on day t+1 = cost of trading from W_{t-1} to W_t at the close of t:
    fee*|dW| + slip*vol_t*|dW|, plus two extra fee legs on rolled positions (roll_next[t, i] = day t+1 is the first day
    of holding a new contract)."""
    W = np.nan_to_num(weights, nan=0.0)
    r_next = np.nan_to_num(next_value(ret), nan=0.0)
    gross = (W * r_next).sum(axis=1)
    prev = np.vstack([np.zeros((1, W.shape[1])), W[:-1]])
    dW = np.abs(W - prev)
    unit = cost.fee_bps / 1e4 + cost.slip_vol_frac * np.nan_to_num(vol, nan=0.0)
    c = (dW * unit).sum(axis=1)
    if roll_next is not None:
        c = c + (np.abs(W) * np.nan_to_num(roll_next.astype(float)) * 2.0 * cost.fee_bps / 1e4).sum(axis=1)
    gross[-1] = np.nan
    return Portfolio(W, gross, c, dW.sum(axis=1))


def state_weights(
    legs: Legs,
    s: np.ndarray,
    kappa: np.ndarray | None = None,
    excl: np.ndarray | None = None,
) -> np.ndarray:
    """W_t = kappa_t * [ (1+s_t)/2 * W_mom_t + (1-s_t)/2 * W_rev_t(excl) ]  (doc 4.5). Days without a defined s get 0."""
    s0 = np.nan_to_num(s, nan=0.0)
    wm = ((1.0 + s0) / 2.0)[:, None]
    wr = ((1.0 - s0) / 2.0)[:, None]
    rev_w = legs.rev.weights
    if excl is not None:
        rev_w = np.where(excl, 0.0, rev_w)
    W = wm * legs.mom.weights + wr * rev_w
    if kappa is not None:
        W = W * kappa[:, None]
    ok = ~np.isnan(s)
    W[~ok] = 0.0
    return W


def static_blend_weights(legs: Legs, w_mom: float = 0.5) -> np.ndarray:
    return w_mom * legs.mom.weights + (1.0 - w_mom) * legs.rev.weights
