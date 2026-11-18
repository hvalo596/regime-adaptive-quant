"""Draft parameters. Everything marked TO_LOCK is a placeholder pending the user's decision
(research doc step 2: strategy parameters are locked once, then never tuned)."""

from __future__ import annotations

from dataclasses import dataclass

TRADING_DAYS = 252


@dataclass(frozen=True)
class StrategyParams:
    # TO_LOCK: momentum / reversal lookback and holding periods (days)
    mom_lookback: int = 60
    mom_hold: int = 20
    rev_lookback: int = 5
    rev_hold: int = 3
    # Ex-ante vol estimation window used for position sizing and leg risk-standardisation
    vol_window: int = 60
    target_ann_vol: float = 0.10
    max_leverage_per_asset: float = 4.0


@dataclass(frozen=True)
class CostParams:
    """TO_LOCK: simple proportional cost. One-way cost per unit notional traded
    = fee_bps/1e4 + slip_vol_frac * ex-ante daily vol (slippage tied to volatility)."""

    fee_bps: float = 1.0
    slip_vol_frac: float = 0.05


@dataclass(frozen=True)
class ProxyParams:
    """TO_LOCK: observable state proxies (variance ratio VR(q) over a rolling window).
    short scale pairs with reversal (VR<1 -> impatient traders); long scale pairs with momentum (VR>1 -> slow traders)."""

    vr_short_q: int = 5
    vr_short_window: int = 60
    vr_long_q: int = 20
    vr_long_window: int = 120
    bin_min_obs: int = 250  # expanding-quantile warm-up before a bin label is issued


@dataclass(frozen=True)
class InferenceParams:
    n_boot: int = 300
    mean_block: int = 20  # stationary-bootstrap mean block length (days); TO_LOCK
    ci_level: float = 0.95
    min_segments_per_bin: int = 5  # draft stop rule from regime-identification-why.md (to confirm)
    min_segment_len: int = 10  # a run shorter than this is not counted as an independent segment
