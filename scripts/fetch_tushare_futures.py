"""Fetch China futures raw data from Tushare into a local cache (resumable).

Token: read from the environment variable TUSHARE_TOKEN only. Never pass it on the command line and never put it
in a file. Without a token this script stops with a clear message and does nothing.

    export TUSHARE_TOKEN=...            # via your secret manager / Cursor secret
    python scripts/fetch_tushare_futures.py --group commodity --start 20100101
    python scripts/fetch_tushare_futures.py --products IF,IH,IC,IM,TS,TF,T,TL --start 20100101

Budget: one fut_daily call per contract (+ paging when a contract has > 2000 rows, never for a single contract),
a few hundred contracts per product-decade; 150 calls/min by default (measured cap 200/min). Interrupt and re-run
freely: cached contracts are skipped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.data.store import RawStore, fetch_holding, fetch_universe  # noqa: E402
from regime_quant.data.tushare_client import MissingTokenError, TushareClient, TushareConfig  # noqa: E402
from regime_quant.data.universe import PRODUCTS, commodity_products  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--group", choices=["commodity", "index", "bond", "all"], default="commodity")
    ap.add_argument("--products", default=None, help="comma-separated Tushare fut_code list (overrides --group)")
    ap.add_argument("--start", default="20100101")
    ap.add_argument("--end", default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--calls-per-min", type=int, default=150)
    ap.add_argument("--holding-dates", default=None, help="comma-separated YYYYMMDD list; fetches fut_holding rankings")
    args = ap.parse_args()

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
    if args.holding_dates:
        exs = sorted({PRODUCTS[p][0] for p in products})
        for w in fetch_holding(client, store, args.holding_dates.split(","), exs):
            print("WARNING:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
