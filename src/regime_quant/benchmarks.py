"""State-free benchmarks (research doc step 4: no-state baselines) and the risk-standardised spread D.

D = momentum return / its ex-ante vol  -  reversal return / its ex-ante vol.
Both legs are scaled to unit ex-ante risk first, so "de-lever when vol is high" is excluded by
construction: any state dependence left in D must come from WHICH strategy pays, not from HOW MUCH risk.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import LegResult
from .synthetic import SyntheticMarket
from .config import TRADING_DAYS, StrategyParams


def risk_standardise(ret: pd.Series, window: int) -> pd.Series:
    """ret_t / ex-ante vol, where vol uses days up to t-1 only."""
    vol = ret.rolling(window, min_periods=window).std().shift(1)
    return ret / vol.where(vol > 1e-12)


def spread_d(legs: dict[str, LegResult], params: StrategyParams, net: bool = True) -> pd.Series:
    pick = (lambda r: r.net) if net else (lambda r: r.gross)
    mom = risk_standardise(pick(legs["mom"]), params.vol_window)
    rev = risk_standardise(pick(legs["rev"]), params.vol_window)
    return (mom - rev).rename("D")


def vol_target(ret: pd.Series, window: int, target_ann_vol: float, max_lev: float = 3.0) -> pd.Series:
    vol = ret.rolling(window, min_periods=window).std().shift(1) * np.sqrt(TRADING_DAYS)
    scale = (target_ann_vol / vol).clip(upper=max_lev)
    return (ret * scale).rename("vol_target_blend")


def benchmark_returns(
    returns: pd.DataFrame, legs: dict[str, LegResult], params: StrategyParams
) -> pd.DataFrame:
    """Daily net returns of the state-free allocations over {momentum, reversal}.

    ew_assets_long    : buy-and-hold-style equal-weight long basket (market reference, zero cost)
    ew_blend          : static 50/50 dollar split of the two (already asset-level vol-targeted) legs
    inv_vol_blend     : legs weighted by 1 / ex-ante leg vol (risk parity over the two legs)
    vol_target_blend  : ew_blend scaled to a constant ex-ante vol -- the "one line of code" that
                        many apparent regime benefits reduce to
    """
    mom, rev = legs["mom"].net, legs["rev"].net
    w = params.vol_window
    ew_blend = 0.5 * mom + 0.5 * rev
    vm = mom.rolling(w, min_periods=w).std().shift(1)
    vr = rev.rolling(w, min_periods=w).std().shift(1)
    wm = ((1 / vm.where(vm > 1e-12)) / (1 / vm.where(vm > 1e-12) + 1 / vr.where(vr > 1e-12))).fillna(0.5)
    inv_vol = wm * mom + (1 - wm) * rev
    out = pd.DataFrame(
        {
            "mom_leg": mom,
            "rev_leg": rev,
            "ew_assets_long": returns.mean(axis=1),
            "ew_blend": ew_blend,
            "inv_vol_blend": inv_vol,
            "vol_target_blend": vol_target(ew_blend, w, params.target_ann_vol),
        }
    )
    return out


ORACLE_MAP = {"slow": (1.0, 0.0), "rushed": (0.0, 1.0), "calm": (0.0, 0.0)}


def oracle_allocation(legs: dict[str, LegResult], market: SyntheticMarket) -> pd.Series:
    """God-view upper bound (research doc step 4, tier 3): hand-set mapping from the KNOWN design
    (slow -> momentum, rushed -> reversal, calm -> flat), using the true state known at the close of t-1.
    Not fitted to returns; only valid on the 3-regime synthetic scenario. Leg-switching costs are ignored."""
    names = market.state_names
    prev = market.states.shift(1)
    w_mom = prev.map(lambda k: ORACLE_MAP[names[int(k)]][0] if pd.notna(k) else 0.0)
    w_rev = prev.map(lambda k: ORACLE_MAP[names[int(k)]][1] if pd.notna(k) else 0.0)
    return (w_mom * legs["mom"].net + w_rev * legs["rev"].net).rename("oracle_true_state")
