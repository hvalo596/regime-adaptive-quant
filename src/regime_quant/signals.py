"""Point-in-time signals. Every value at row t uses returns up to and including day t only
(known at the close of t). Positions built from them start earning on day t+1 (see backtest.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS, StrategyParams


def ex_ante_vol(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    return returns.rolling(window, min_periods=window).std()


def trailing_sum(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return returns.rolling(lookback, min_periods=lookback).sum()


def tsmom_signal(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Time-series momentum: follow the sign of the trailing cumulative return."""
    return np.sign(trailing_sum(returns, lookback))


def reversal_signal(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Short-term reversal: fade the sign of the trailing cumulative return."""
    return -np.sign(trailing_sum(returns, lookback))


def tranche_average(signal: pd.DataFrame, hold: int) -> pd.DataFrame:
    """Holding period h via overlapping tranches: position = mean of the last h daily signals
    (Jegadeesh-Titman style). Cuts turnover without any look-ahead."""
    return signal.rolling(hold, min_periods=hold).mean()


def vol_scaled_weights(
    signal: pd.DataFrame, vol: pd.DataFrame, params: StrategyParams
) -> pd.DataFrame:
    """Per-asset inverse-vol sizing to a common annual vol target; equal risk across assets."""
    n_assets = signal.shape[1]
    daily_target = params.target_ann_vol / np.sqrt(TRADING_DAYS)
    w = signal * (daily_target / vol) / n_assets
    cap = params.max_leverage_per_asset / n_assets
    return w.clip(-cap, cap)


def momentum_weights(returns: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    sig = tranche_average(tsmom_signal(returns, params.mom_lookback), params.mom_hold)
    return vol_scaled_weights(sig, ex_ante_vol(returns, params.vol_window), params)


def reversal_weights(returns: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    sig = tranche_average(reversal_signal(returns, params.rev_lookback), params.rev_hold)
    return vol_scaled_weights(sig, ex_ante_vol(returns, params.vol_window), params)
