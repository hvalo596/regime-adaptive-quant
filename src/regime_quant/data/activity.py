"""Product-level activity (doc 3.1: volume and open interest are SUMS over all contracts of a product, so a roll day does not
create a fake jump) and the carry proxy used in the risk-premium control (doc section 6)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def product_activity(daily: pd.DataFrame, basic: pd.DataFrame, products: list[str]) -> dict[str, pd.DataFrame]:
    """Wide (date x product) frames: oi, vol, amount (10k CNY), each summed over all contracts of the product on the date."""
    code_to_prod = basic.drop_duplicates("ts_code").set_index("ts_code")["fut_code"]
    d = daily[daily["ts_code"].isin(code_to_prod.index)].copy()
    d["product"] = d["ts_code"].map(code_to_prod)
    d = d[d["product"].isin(products)]
    out = {}
    for col in ("oi", "vol", "amount"):
        if col not in d.columns:
            continue
        out[col] = d.pivot_table(index="trade_date", columns="product", values=col, aggfunc="sum").sort_index().reindex(columns=products)
    return out


def carry_proxy(daily: pd.DataFrame, basic: pd.DataFrame, held: pd.DataFrame, products: list[str]) -> pd.DataFrame:
    """Annualised log roll yield between the HELD contract and the next contract by expiry that traded that day:
        carry = ln(P_held / P_next) / (days between expiries) * 365   (positive = backwardation).
    `held` is the (date x product) frame of held contract codes (panel.continuous[p]['held'])."""
    exp = basic.drop_duplicates("ts_code").set_index("ts_code")["last_ddate"]
    exp = pd.to_datetime(exp.astype(str), format="%Y%m%d", errors="coerce")
    d = daily[["ts_code", "trade_date", "close"]].copy()
    if not pd.api.types.is_datetime64_any_dtype(d["trade_date"]):
        d["trade_date"] = pd.to_datetime(d["trade_date"].astype(str), format="%Y%m%d")
    d["exp"] = d["ts_code"].map(exp)
    out = {}
    by_date = {k: v for k, v in d.dropna(subset=["close", "exp"]).groupby("trade_date")}
    for p in products:
        if p not in held.columns:
            continue
        vals = {}
        for dt, code in held[p].dropna().items():
            g = by_date.get(dt)
            if g is None:
                continue
            g = g[g["ts_code"].str.startswith(p) & (g["ts_code"].str[len(p) : len(p) + 1].str.isdigit())]
            cur = g[g["ts_code"] == code]
            nxt = g[g["exp"] > (cur["exp"].iloc[0] if len(cur) else pd.Timestamp.max)].sort_values("exp")
            if len(cur) and len(nxt):
                days = (nxt["exp"].iloc[0] - cur["exp"].iloc[0]).days
                if days > 0:
                    vals[dt] = np.log(cur["close"].iloc[0] / nxt["close"].iloc[0]) / days * 365.0
        out[p] = pd.Series(vals, dtype=float)
    return pd.DataFrame(out).reindex(columns=products)
