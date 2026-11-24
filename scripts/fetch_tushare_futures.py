"""Fetch China futures raw data from Tushare into a local cache (resumable).

Token: read from the environment variable TUSHARE_TOKEN only. Never pass it on the command line and never put it
in a file. Without a token this script stops with a clear message and does nothing.

    export TUSHARE_TOKEN=...            # via your secret manager / Cursor secret
    python scripts/fetch_tushare_futures.py --group all            # default window: 20 analysis years + warm-up
    python scripts/fetch_tushare_futures.py --products IF,IH,IC,IM,TS,TF,T,TL --start-date 20050101

Budget: one fut_daily call per contract (+ paging when a contract has > 2000 rows, never for a single contract),
a few hundred contracts per product-decade; 150 calls/min by default (measured cap 200/min). Interrupt and re-run
freely: cached contracts are skipped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.data.store import RawStore, fetch_holding, fetch_settle, fetch_settle_contracts, fetch_universe  # noqa: E402
from regime_quant.data.tushare_client import MissingTokenError, TushareClient, TushareConfig  # noqa: E402
from regime_quant.data.universe import PRODUCTS, commodity_products  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--group", choices=["commodity", "index", "bond", "all"], default="commodity")
    ap.add_argument("--products", default=None, help="comma-separated Tushare fut_code list (overrides --group)")
    ap.add_argument("--start", "--start-date", dest="start", default=None, help="YYYYMMDD; default = today minus (--years + 2) years so that 20 analysis years survive the 60-day vol / 250-day eligibility / 750-day z-score warm-ups")
    ap.add_argument("--years", type=int, default=20, help="analysis years wanted (default 20)")
    ap.add_argument("--end", default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--calls-per-min", type=int, default=150)
    ap.add_argument("--holding-dates", default=None, help="comma-separated YYYYMMDD list; fetches fut_holding rankings")
    ap.add_argument("--all-days-extras", action="store_true", help="fetch fut_holding and fut_settle for every trade day of the fetched products (about 5 calls per day: slow, 1-2 hours)")
    ap.add_argument("--margin-contracts", action="store_true", help="fetch fut_settle (margin rates) for every contract that was the official main contract since 2021-01-01 (API history starts 2021-01-04); ~1 call per contract")
    ap.add_argument("--settle-dates", default=None, help="comma-separated YYYYMMDD list; fetches fut_settle margin parameters")
    args = ap.parse_args()
    if args.start is None:
        import datetime as _dt

        args.start = (_dt.date.today().replace(month=1, day=1) - _dt.timedelta(days=int(365.25 * (args.years + 2)))).strftime("%Y%m%d")
    print(f"fetch window starts {args.start} (years wanted: {args.years})")

    if args.products:
        products = [p.strip().upper() for p in args.products.split(",")]
    elif args.group == "commodity":
        products = commodity_products()
    elif args.group == "all":
        products = list(PRODUCTS)
    else:
        products = [p for p, (_, s) in PRODUCTS.items() if s == args.group]
    unknown = [p for p in products if p not in PRODUCTS]
    if unknown:
        print(f"unknown products (add to data/universe.py): {unknown}", file=sys.stderr)
        return 2

    cfg = TushareConfig.from_env(max_calls_per_min=args.calls_per_min)
    try:
        cfg.require_token()
    except MissingTokenError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    client = TushareClient(cfg)
    store = RawStore(args.raw_dir)
    log = fetch_universe(client, store, products, start=args.start, end=args.end, refresh=args.refresh)
    print({k: v for k, v in log.items() if k != "products"})
    exs = sorted({PRODUCTS[p][0] for p in products})
    hold_dates = args.holding_dates.split(",") if args.holding_dates else None
    settle_dates = args.settle_dates.split(",") if args.settle_dates else None
    if args.all_days_extras:
        cal = client.trade_cal("SHFE", args.start, args.end or __import__("time").strftime("%Y%m%d"))
        days = sorted(cal[cal["is_open"] == 1]["cal_date"].astype(str).tolist())
        hold_dates = settle_dates = days
    if args.margin_contracts:
        import pandas as _pd

        codes = set()
        for p in products:
            m = store.mapping(p)
            if not m.empty:
                codes |= set(m[m["trade_date"].astype(str) >= "20210101"]["mapping_ts_code"].dropna().unique())
        print(f"margin parameters for {len(codes)} contracts")
        for w in fetch_settle_contracts(client, store, sorted(codes)):
            print("WARNING:", w)
    if hold_dates:
        for w in fetch_holding(client, store, hold_dates, exs):
            print("WARNING:", w)
    if settle_dates:
        for w in fetch_settle(client, store, settle_dates, exs):
            print("WARNING:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
