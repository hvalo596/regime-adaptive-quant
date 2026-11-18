"""Vectorised point-in-time backtest of one strategy leg.

Timing convention (the anti-look-ahead contract):
  * target weights in row t are computed from data through the close of day t and traded at that close;
  * they earn the return of day t+1  ->  pnl_t = sum_i w_{i,t-1} * r_{i,t};
  * trading cost is charged on the day the new position starts earning, on |w_t_held - w_{t-1}_held|.

Returns are close-to-close (never settlement prices: docs/regime-identification-why.md section 1.5).
An event-driven second implementation for cross-checking is planned (research doc step 1); tests already
cross-check this vectorised engine against a naive per-day loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import CostParams, StrategyParams
from .signals import ex_ante_vol, momentum_weights, reversal_weights


@dataclass
class LegResult:
    gross: pd.Series
    cost: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame  # target weights decided at close t (before the 1-day shift)

    @property
    def net(self) -> pd.Series:
        return self.gross - self.cost


def run_leg(
    returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    vol_hat: pd.DataFrame,
    cost: CostParams,
) -> LegResult:
    w = target_weights.fillna(0.0)
    held = w.shift(1).fillna(0.0)
    gross = (held * returns).sum(axis=1)
    dw = held.diff().fillna(held).abs()
    unit_cost = cost.fee_bps / 1e4 + cost.slip_vol_frac * vol_hat.shift(1).fillna(0.0)
    cost_series = (dw * unit_cost).sum(axis=1)
    return LegResult(
        gross=gross.rename("gross"),
        cost=cost_series.rename("cost"),
        turnover=dw.sum(axis=1).rename("turnover"),
        weights=w,
    )


def build_legs(
    returns: pd.DataFrame, params: StrategyParams, cost: CostParams
) -> dict[str, LegResult]:
    vol = ex_ante_vol(returns, params.vol_window)
    return {
        "mom": run_leg(returns, momentum_weights(returns, params), vol, cost),
        "rev": run_leg(returns, reversal_weights(returns, params), vol, cost),
    }
