"""Assemble the asset-by-day return panel and flag panels from per-product continuous series."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .flags import add_flags
from .roll import RollParams, build_continuous


@dataclass(frozen=True)
class PanelParams:
    liq_window: int = 60
    min_median_amount_wan: float = 10_000.0  # 1e8 CNY/day (fut_daily `amount` is in 10k CNY); DRAFT, TO_LOCK
    min_history_days: int = 250


@dataclass
class Panel:
    returns: pd.DataFrame
    roll: pd.DataFrame
    limit_locked: pd.DataFrame
    one_price: pd.DataFrame
    stale: pd.DataFrame
    night_draft: pd.DataFrame
    extreme_ret: pd.DataFrame
    diagnostics: pd.DataFrame
    continuous: dict[str, pd.DataFrame] = field(default_factory=dict)


def build_panel(
    products: list[str],
    basic: pd.DataFrame,
    daily: pd.DataFrame,
    mappings: dict[str, pd.DataFrame] | None = None,
    roll_params: RollParams = RollParams(),
    panel_params: PanelParams = PanelParams(),
) -> Panel:
    """Point-in-time liquidity latch: a product enters the panel on the first day its trailing median turnover
    clears the threshold (and it has `min_history_days` of data) and then stays in. Returns before the latch are NaN.
    This avoids selecting the universe by full-sample liquidity (survivorship / look-ahead)."""
    conts, diags = {}, []
    for p in products:
        cont, diag = build_continuous(p, basic, daily, (mappings or {}).get(p), roll_params)
        if cont.empty or diag["n_days"] < panel_params.min_history_days:
            diags.append({**diag, "included": False, "reason": "no data / too short"})
            continue
        cont = add_flags(cont, p)
        amount = cont["h_amount"] if "h_amount" in cont else cont["h_vol"]
        med = amount.rolling(panel_params.liq_window, min_periods=panel_params.liq_window).median()
        ok = (med >= panel_params.min_median_amount_wan).fillna(False).to_numpy()
        if not ok.any():
            diags.append({**diag, "included": False, "reason": "never liquid enough"})
            continue
        latch = np.argmax(ok)
        cont["eligible"] = np.arange(len(cont)) > latch
        conts[p] = cont
        diags.append({**diag, "included": True, "reason": "", "liquid_from": str(cont.index[latch].date())})

    if not conts:
        raise ValueError("no product passed the data/liquidity filters")
    dates = sorted(set().union(*[set(c.index) for c in conts.values()]))
    idx = pd.DatetimeIndex(dates)

    def wide(col, fill=None, bool_=False):
        cols = {}
        for p, c in conts.items():
            s = c[col].astype(float if not bool_ else bool)
            s = s.reindex(idx)
            cols[p] = s
        return pd.DataFrame(cols)

    ret = wide("ret")
    for p, c in conts.items():
        first, last = c.index[0], c.index[-1]
        inside = (idx >= first) & (idx <= last)
        gap = ret[p].isna() & inside
        ret.loc[gap, p] = 0.0  # missing calendar day inside the life span: flat, not a hole that kills rolling windows
        ret.loc[~c["eligible"].reindex(idx).fillna(False).astype(bool).to_numpy(), p] = np.nan

    def bool_panel(col):
        out = pd.DataFrame({p: c[col].reindex(idx).fillna(False).astype(bool) for p, c in conts.items()})
        return out

    return Panel(
        returns=ret,
        roll=bool_panel("roll_day"),
        limit_locked=bool_panel("limit_locked_proxy"),
        one_price=bool_panel("one_price"),
        stale=bool_panel("stale"),
        night_draft=bool_panel("night_draft"),
        extreme_ret=bool_panel("extreme_ret"),
        diagnostics=pd.DataFrame(diags),
        continuous=conts,
    )


def subset_panel(panel: Panel, products: list[str]) -> Panel:
    """Column subset of an assembled panel (same dates, same flags). Dates before a subset's first valid return are
    trimmed so that sector panels do not carry an all-NaN head."""
    cols = [p for p in products if p in panel.returns.columns]
    if not cols:
        raise ValueError("none of the requested products are in the panel")
    first = panel.returns[cols].dropna(how="all").index[0]
    cut = lambda df: df.loc[first:, cols]  # noqa: E731
    return Panel(
        returns=cut(panel.returns), roll=cut(panel.roll), limit_locked=cut(panel.limit_locked),
        one_price=cut(panel.one_price), stale=cut(panel.stale), night_draft=cut(panel.night_draft),
        extreme_ret=cut(panel.extreme_ret),
        diagnostics=panel.diagnostics[panel.diagnostics["product"].isin(cols)].reset_index(drop=True),
        continuous={p: panel.continuous[p] for p in cols},
    )
