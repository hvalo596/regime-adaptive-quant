"""Data-quality / microstructure flags for the continuous series (research doc section 1.5 alternative channels).

Flags are labels for robustness splits and exclusions. They never alter returns.
  one_price            high == low on a traded day: no intraday range, the signature of a locked limit day (or a
                       very thin day). Needs no limit-schedule table.
  limit_locked_proxy   one_price AND |close / pre_settle - 1| >= `min_move`. Exchange limit tables vary by product
                       and period and are NOT in fut_daily, so this is a proxy, to be replaced once a schedule exists.
  stale                held contract had no print; return set to 0 (see roll.py).
  roll_day             first day of holding a new contract.
  near_expiry          held contract within 30 days of its last trading day (delivery-month dynamics).
  extreme_ret          |return| > 12%: far outside any daily limit schedule; a data error candidate (reported, not removed).
  night_draft          date >= draft night-session start for the product (UNVERIFIED dates, universe.py).
  index_period         stock-index products only: pre / restricted / loosened_1 / loosened_2 (UNVERIFIED dates).

Night-session caveat: Tushare assigns the night session to the next trade date, so close-to-close is consistent, but
for night-session products the daily bar spans ~ evening-to-afternoon; settlement/close timing differs from
products without a night session, and cross-product alignment (e.g. SC vs index futures) has an overnight skew.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .universe import INDEX_RESTRICTION_DRAFT, NIGHT_SESSION_START_DRAFT, PRODUCTS


def add_flags(cont: pd.DataFrame, product: str, min_move: float = 0.015) -> pd.DataFrame:
    out = cont.copy()
    hi, lo = out.get("h_high"), out.get("h_low")
    if hi is not None and lo is not None:
        out["one_price"] = (hi == lo) & (out["h_vol"] > 0)
        move = (out["h_close"] / out["h_pre_settle"] - 1.0).abs() if "h_pre_settle" in out else np.nan
        out["limit_locked_proxy"] = out["one_price"] & (move >= min_move)
    else:
        out["one_price"] = False
        out["limit_locked_proxy"] = False
    out["roll_day"] = out["roll_flag"]
    out["near_expiry"] = out["days_to_expiry"] < 30
    start = NIGHT_SESSION_START_DRAFT.get(product)
    out["extreme_ret"] = out["ret"].abs() > 0.12
    out["night_draft"] = (out.index >= pd.Timestamp(start)) if start else False
    if PRODUCTS.get(product, ("", ""))[1] == "index":
        r = INDEX_RESTRICTION_DRAFT
        ts = lambda k: pd.Timestamp(r[k])  # noqa: E731
        period = np.select(
            [out.index < ts("restricted_from"), out.index < ts("loosened_1"), out.index < ts("loosened_2")],
            ["pre", "restricted", "loosened_1"],
            default="loosened_2",
        )
        out["index_period"] = period
    return out
