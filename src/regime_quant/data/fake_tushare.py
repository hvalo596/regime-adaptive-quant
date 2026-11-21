"""Offline stand-in for Tushare: a multi-contract futures market served through the Tushare API shape, built from a
synthetic `World` (world.py) so that the planted crowd states are known.

Purpose: run the SAME ingest -> cache -> own roll adjustment -> flags -> panel -> state pipeline that real data uses when no
token is available (CI, and the "token missing" situation of step 2). It is a plumbing and correctness fixture, never
evidence about China futures.

Each product has a spot path (the world's observed close). Monthly contracts trade at
    F_k(t) = S_t * exp(carry * (T_k - t)/365 + basis_noise_k(t)),
so an unadjusted splice of front/main contracts has roll jumps of about carry * (gap between contracts), while the roll-adjusted
same-contract close-to-close return recovers the spot return up to a deterministic carry drift. Product-level volume and
open interest are the world's, split across the live contracts by a hump around ~70 days to expiry, so product sums equal the
world's totals. Largest-move days are made one-price (high = low) to exercise the limit flags. Products listed in
`index_products` get the "nearest month" official mapping (the measured IF behaviour); all others the max-OI mapping.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..world import World
from .tushare_client import ROW_CAPS
from .universe import EXCHANGE_SUFFIX, PRODUCTS


@dataclass
class SyntheticFutures:
    basic: pd.DataFrame
    daily: pd.DataFrame  # all contracts, Tushare columns, trade_date as 'YYYYMMDD' str
    mapping: pd.DataFrame  # ts_code (continuous), trade_date, mapping_ts_code
    spot_returns: pd.DataFrame  # truth: underlying daily returns per product (index = Timestamp)
    world: World
    products: list[str]
    carry: float


def _expiry(year: int, month: int) -> pd.Timestamp:
    return pd.Timestamp(year=year, month=month, day=15)


def make_synthetic_futures(world: World, products: list[str], seed: int = 0, carry: float = 0.06, index_products: tuple[str, ...] = ()) -> SyntheticFutures:
    assert world.ret.shape[1] == len(products)
    rng = np.random.default_rng(seed)
    dates = world.dates
    n_days = len(dates)
    spot_ret = pd.DataFrame(world.ret, index=dates, columns=products)
    spot = pd.DataFrame(world.close, index=dates, columns=products)
    vol_p = pd.DataFrame(world.volume * 1e3, index=dates, columns=products)
    oi_p = pd.DataFrame(world.oi * 1e3, index=dates, columns=products)

    basics, dailies, maps = [], [], []
    months = pd.period_range(dates[0].to_period("M") - 1, dates[-1].to_period("M") + 14, freq="M")
    for p in products:
        exch, _ = PRODUCTS[p]
        suffix = EXCHANGE_SUFFIX[exch]
        is_index = p in index_products
        live_tab = {}
        for m in months:
            T = _expiry(m.year, m.month)
            lst = T - pd.Timedelta(days=365)
            code = f"{p}{m.year % 100:02d}{m.month:02d}.{suffix}"
            live = dates[(dates >= lst) & (dates <= T)]
            if len(live) == 0:
                continue
            basics.append(
                {"ts_code": code, "symbol": code.split(".")[0], "exchange": exch, "name": code, "fut_code": p,
                 "multiplier": 10, "trade_unit": "", "per_unit": 1, "quote_unit": "", "quote_unit_desc": "",
                 "d_mode_desc": "", "list_date": lst.strftime("%Y%m%d"), "delist_date": T.strftime("%Y%m%d"),
                 "d_month": f"{m.year % 100:02d}{m.month:02d}", "last_ddate": T.strftime("%Y%m%d")}
            )
            tau = np.array([(T - d).days for d in live], dtype=float)
            noise = np.cumsum(rng.normal(0, 0.0004, len(live)))
            noise = noise - noise[0]
            noise = noise - np.linspace(0, noise[-1], len(live))
            price = spot.loc[live, p].to_numpy() * np.exp(carry * tau / 365.0 + noise)
            lead = 70.0 if not is_index else 20.0
            w = np.exp(-((tau - lead) ** 2) / (2 * 55.0**2)) * (1 + 0.03 * rng.random(len(live)))
            w = np.where(tau < 3, w * 0.05, w)
            live_tab[code] = pd.DataFrame({"trade_date": live, "close": price, "w": w, "ts_code": code})
        wide = pd.concat(live_tab.values())
        tot = wide.groupby("trade_date")["w"].transform("sum")
        wide["share"] = wide["w"] / tot
        wide["vol"] = wide["share"] * vol_p.loc[wide["trade_date"], p].to_numpy()
        wide["oi"] = wide["share"] * oi_p.loc[wide["trade_date"], p].to_numpy()
        for code, df in wide.groupby("ts_code"):
            close = df["close"].to_numpy()
            settle = close * (1 + rng.normal(0, 0.0005, len(df)))
            hi = close * (1 + np.abs(rng.normal(0, 0.003, len(df))))
            lo = close * (1 - np.abs(rng.normal(0, 0.003, len(df))))
            op = close * (1 + rng.normal(0, 0.001, len(df)))
            out = pd.DataFrame(
                {
                    "ts_code": code,
                    "trade_date": df["trade_date"].dt.strftime("%Y%m%d").to_numpy(),
                    "pre_close": np.r_[np.nan, close[:-1]],
                    "pre_settle": np.r_[np.nan, settle[:-1]],
                    "open": op, "high": np.maximum.reduce([hi, close, op]), "low": np.minimum.reduce([lo, close, op]),
                    "close": close, "settle": settle,
                    "change1": np.r_[np.nan, close[1:] - close[:-1]], "change2": np.nan,
                    "vol": df["vol"].to_numpy(), "amount": df["vol"].to_numpy() * close * 0.1,
                    "oi": df["oi"].to_numpy(), "oi_chg": np.r_[np.nan, np.diff(df["oi"].to_numpy())],
                }
            )
            dailies.append(out)

    daily = pd.concat(dailies, ignore_index=True)
    basic = pd.DataFrame(basics)
    for p in products:
        big = spot_ret[p].abs().nlargest(max(3, n_days // 400)).index.strftime("%Y%m%d")
        m = daily["ts_code"].str.match(rf"^{p}\d") & daily["trade_date"].isin(big)
        daily.loc[m, "high"] = daily.loc[m, "close"]
        daily.loc[m, "low"] = daily.loc[m, "close"]
        daily.loc[m, "open"] = daily.loc[m, "close"]
    for p in products:
        exch, _ = PRODUCTS[p]
        suffix = EXCHANGE_SUFFIX[exch]
        sub = daily[daily["ts_code"].str.match(rf"^{p}\d")]
        if p in index_products:
            sub = sub.merge(basic[["ts_code", "last_ddate"]], on="ts_code")
            sub = sub[sub["trade_date"] <= sub["last_ddate"]]
            pick = sub.sort_values(["trade_date", "last_ddate"]).groupby("trade_date").first()["ts_code"]
        else:
            pick = sub.sort_values(["trade_date", "oi"]).groupby("trade_date").last()["ts_code"]
        maps.append(pd.DataFrame({"ts_code": f"{p}.{suffix}", "trade_date": pick.index, "mapping_ts_code": pick.values}))
    daily = daily[daily["trade_date"].isin(dates.strftime("%Y%m%d"))].reset_index(drop=True)
    return SyntheticFutures(basic=basic, daily=daily, mapping=pd.concat(maps, ignore_index=True), spot_returns=spot_ret, world=world, products=products, carry=carry)


class FakeTushareTransport:
    """Serves a `SyntheticFutures` through the Tushare request shape, including row caps and desc ordering."""

    def __init__(self, data: SyntheticFutures, caps: dict[str, int] | None = None):
        self.data = data
        self.caps = {**ROW_CAPS, **(caps or {})}
        self.calls: list[tuple[str, dict]] = []
        self._daily_by_code = {k: v for k, v in data.daily.groupby("ts_code")}
        self._map_by_code = {k: v for k, v in data.mapping.groupby("ts_code")}

    def __call__(self, api: str, params: dict, fields: str = "") -> pd.DataFrame:
        self.calls.append((api, dict(params)))
        d = self.data
        if api == "fut_basic":
            b = d.basic[d.basic["exchange"] == params.get("exchange")] if "exchange" in params else d.basic
            return b.reset_index(drop=True)
        if api in ("fut_daily", "fut_mapping"):
            df = d.daily if api == "fut_daily" else d.mapping
            if "ts_code" in params:
                by = self._daily_by_code if api == "fut_daily" else self._map_by_code
                df = by.get(params["ts_code"], df.iloc[:0])
            if "trade_date" in params:
                df = df[df["trade_date"] == params["trade_date"]]
            if "start_date" in params:
                df = df[df["trade_date"] >= params["start_date"]]
            if "end_date" in params:
                df = df[df["trade_date"] <= params["end_date"]]
            df = df.sort_values("trade_date", ascending=False).head(self.caps[api])
            return df.reset_index(drop=True)
        if api == "fut_holding":
            rng = np.random.default_rng(int(params["trade_date"]) % 2**32)
            return pd.DataFrame(
                {"trade_date": params["trade_date"], "symbol": "X", "broker": [f"B{i}" for i in range(20)],
                 "vol": rng.integers(1, 1000, 20), "vol_chg": 0, "long_hld": rng.integers(1, 1000, 20),
                 "long_chg": 0, "short_hld": rng.integers(1, 1000, 20), "short_chg": 0}
            ).head(self.caps["fut_holding"])
        if api == "fut_settle":
            day = pd.Timestamp(params["trade_date"])
            b = d.basic[(d.basic["exchange"] == params.get("exchange"))]
            live = b[(pd.to_datetime(b["list_date"]) <= day) & (pd.to_datetime(b["delist_date"]) >= day)]
            rate = 0.08 + 0.02 * (day.month % 3 == 0)  # a step up in every third month, for the event code path
            return pd.DataFrame({"ts_code": live["ts_code"], "trade_date": params["trade_date"], "settle": 1.0, "long_margin_rate": rate, "short_margin_rate": rate}).head(self.caps["fut_settle"])
        if api == "trade_cal":
            days = pd.bdate_range(params["start_date"], params["end_date"])
            return pd.DataFrame({"exchange": params["exchange"], "cal_date": days.strftime("%Y%m%d"), "is_open": 1})
        raise ValueError(f"unsupported api {api}")
