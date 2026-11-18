"""Raw-data cache (csv.gz, one file per contract) and the fetch orchestration.

Layout under `root`:
  fut_basic.csv.gz
  fut_daily/<ts_code>.csv.gz
  fut_mapping/<product>.csv.gz
  fut_holding/<exchange>_<yyyymmdd>.csv.gz
  fetch_log.json            (what was fetched, when, truncation warnings; never contains the token)
Fetching is resumable: a contract file that exists is skipped unless `refresh=True`. Contracts delisted
long before the data start are skipped to save API calls.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from .tushare_client import TushareClient
from .universe import PRODUCTS, continuous_code

STR_COLS = {"ts_code": str, "trade_date": str, "mapping_ts_code": str, "list_date": str, "delist_date": str,
            "last_ddate": str, "fut_code": str, "symbol": str, "exchange": str, "d_month": str}


class RawStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, *parts: str) -> Path:
        p = self.root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write(self, df: pd.DataFrame, *parts: str) -> None:
        df.to_csv(self._path(*parts), index=False, compression="gzip")

    def read(self, *parts: str) -> pd.DataFrame:
        p = self.root.joinpath(*parts)
        if not p.exists():
            return pd.DataFrame()
        header = pd.read_csv(p, nrows=0).columns
        return pd.read_csv(p, dtype={c: t for c, t in STR_COLS.items() if c in header})

    def exists(self, *parts: str) -> bool:
        return self.root.joinpath(*parts).exists()

    def basic(self) -> pd.DataFrame:
        return self.read("fut_basic.csv.gz")

    def contract_daily(self, ts_code: str) -> pd.DataFrame:
        return self.read("fut_daily", f"{ts_code}.csv.gz")

    def mapping(self, product: str) -> pd.DataFrame:
        return self.read("fut_mapping", f"{product}.csv.gz")

    def load_daily(self, ts_codes) -> pd.DataFrame:
        frames = [f for f in (self.contract_daily(c) for c in ts_codes) if not f.empty]
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d")
        return out


def fetch_universe(
    client: TushareClient,
    store: RawStore,
    products: list[str],
    start: str = "20100101",
    end: str | None = None,
    refresh: bool = False,
    progress=print,
) -> dict:
    """Pull fut_basic per exchange, then fut_daily per contract and fut_mapping per product."""
    log: dict = {"start": start, "end": end, "products": products, "contracts": 0, "skipped_cached": 0,
                 "empty_contracts": [], "api_calls": 0}
    exchanges = sorted({PRODUCTS[p][0] for p in products})
    basics = []
    for ex in exchanges:
        b = client.fut_basic(ex, fut_type="1")
        basics.append(b)
        progress(f"fut_basic {ex}: {len(b)} contracts")
    basic = pd.concat(basics, ignore_index=True)
    prev = store.basic()  # merge, so fetching a product subset never drops previously cached contracts
    if not prev.empty:
        basic = pd.concat([basic, prev], ignore_index=True).drop_duplicates("ts_code", keep="first")
    store.write(basic, "fut_basic.csv.gz")

    sel = basic[basic["fut_code"].isin(products)].copy()
    sel = sel[(sel["delist_date"].isna()) | (sel["delist_date"].astype(str) >= start)]
    log["contracts"] = len(sel)
    for i, ts_code in enumerate(sel["ts_code"], 1):
        if store.exists("fut_daily", f"{ts_code}.csv.gz") and not refresh:
            log["skipped_cached"] += 1
            continue
        df = client.fut_daily(ts_code, start=start, end=end)
        if df.empty:
            log["empty_contracts"].append(ts_code)
        store.write(df, "fut_daily", f"{ts_code}.csv.gz")
        if i % 50 == 0:
            progress(f"fut_daily {i}/{len(sel)} contracts (api calls so far: {client.n_calls})")
    for p in products:
        if store.exists("fut_mapping", f"{p}.csv.gz") and not refresh:
            continue
        store.write(client.fut_mapping(continuous_code(p), start=start, end=end), "fut_mapping", f"{p}.csv.gz")
    log["api_calls"] = client.n_calls
    log["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store._path("fetch_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False))
    return log


def fetch_holding(client: TushareClient, store: RawStore, trade_dates: list[str], exchanges: list[str]) -> list[str]:
    """Member holding rankings (validation tool for later steps, not used by step 2). Returns truncation warnings."""
    warnings = []
    for d in trade_dates:
        for ex in exchanges:
            if store.exists("fut_holding", f"{ex}_{d}.csv.gz"):
                continue
            df = client.fut_holding(d, ex)
            store.write(df, "fut_holding", f"{ex}_{d}.csv.gz")
            if df.attrs.get("truncated"):
                warnings.append(f"{ex} {d}: hit 4000-row cap, ranking truncated")
    return warnings
