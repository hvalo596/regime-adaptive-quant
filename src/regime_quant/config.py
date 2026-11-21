"""Locked parameters from docs/state-construction.md (approved by the user, 2026-11-18).

Everything here is fixed BEFORE any real-data result is looked at. Changing a value later must be recorded in
the trial ledger together with the reason.
"""

from __future__ import annotations

from dataclasses import dataclass

TRADING_DAYS = 252


@dataclass(frozen=True)
class LegSpec:
    """One strategy leg. `L`/`H` = look-back / holding period, `gap` = extra days skipped between signal and
    the first return that is traded or measured (0 = normal, 1 = skip-one-day version of reversal)."""

    name: str
    kind: str  # "mom" | "rev"
    L: int
    H: int
    gap: int = 0
    W: int = 200  # estimation window of the state variable (days)


# Strategy parameters (doc section 3.3, 3.4, 9 item 2)
MOM_MAIN = LegSpec("M-B", "mom", 20, 5, 0, 200)
MOM_SECOND = LegSpec("M-A", "mom", 60, 20, 0, 750)
REV_MAIN = LegSpec("R-A", "rev", 5, 3, 0, 50)
REV_SECOND = LegSpec("R-B", "rev", 1, 1, 0, 40)
REV_SECOND_GAP = LegSpec("R-B-gap", "rev", 1, 1, 1, 40)
MOM_UNCONDITIONAL = LegSpec("M-C", "mom", 250, 20, 0, 0)  # unconditional leg only, never a state variable


@dataclass(frozen=True)
class StateParams:
    # standardisation / panel (doc 3.1)
    vol_window: int = 60
    clip: float = 5.0
    factor_window: int = 60
    # hysteresis (doc 4.2)
    c_in: float = 1.28
    c_out: float = 0.5
    # concentration (doc 3.5)
    c_recent: int = 20
    c_base: int = 250
    u_cap: float = 25.0
    u_flag_min: float = 4.0
    flag_mass: float = 0.5
    c_level: float = 0.95  # quantile of the null distribution of C
    # environment (doc 3.6)
    v_halflife: int = 20
    v_base: int = 750
    v_min_base: int = 250
    z_window: int = 750
    z_min: int = 250
    # backtest mapping (doc 4.5)
    kappa0: float = 0.5
    leg_vol_window: int = 60
    target_ann_vol: float = 0.10
    max_leverage_per_asset: float = 4.0


@dataclass(frozen=True)
class CostParams:
    """One-way cost per unit notional = fee_bps/1e4 + slip_vol_frac * ex-ante daily vol of the asset."""

    fee_bps: float = 1.0
    slip_vol_frac: float = 0.05


@dataclass(frozen=True)
class InferenceParams:
    n_boot: int = 500
    mean_block: int = 40  # >= typical dwell of a state, so that serial dependence of s_t is kept
    ci_level: float = 0.95
    n_shift: int = 1000
    min_shift: int = 60
    alpha: float = 0.05
    min_segments: int = 5
    min_segment_len: int = 10


def min_dwell(spec: LegSpec) -> int:
    """Doc 4.2: d_min^M = H for momentum, d_min^R = max(h, 5) for reversal."""
    return spec.H if spec.kind == "mom" else max(spec.H, 5)


def kappa_LH(L: int, H: int) -> float:
    """Overlap inflation of the cross-product variance (doc 3.3)."""
    k = range(1, min(L, H))
    return 1.0 + 2.0 / (L * H) * sum((L - j) * (H - j) for j in k)


def pairs_in_window(spec: LegSpec) -> int:
    """Number of (X, Y) pairs completed inside the estimation window: T = W - L - H - gap + 1."""
    return spec.W - spec.L - spec.H - spec.gap + 1
