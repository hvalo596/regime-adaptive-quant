"""Phase 2: roll-adjusted China futures panel + step-2 existence tests (VR + draft Kai dims on the commodity panel).

Real data (after scripts/fetch_tushare_futures.py):
    python scripts/run_phase2_existence.py --raw-dir data/raw --out artifacts/phase2_real
No token / offline: synthetic fallback through the same ingest path (a plumbing check, not evidence):
    python scripts/run_phase2_existence.py --synthetic --out artifacts/phase2_synthetic
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.data.fake_tushare import FakeTushareTransport, make_synthetic_futures  # noqa: E402
from regime_quant.data.panel import PanelParams  # noqa: E402
from regime_quant.data.roll import RollParams  # noqa: E402
from regime_quant.data.store import RawStore, fetch_universe  # noqa: E402
from regime_quant.data.tushare_client import TushareClient, TushareConfig  # noqa: E402
from regime_quant.data.universe import commodity_products  # noqa: E402
from regime_quant.existence import ExistenceParams  # noqa: E402
from regime_quant.phase2 import run_phase2, write_artifacts  # noqa: E402

SYNTH_PRODUCTS = ["RB", "HC", "I", "CU", "AL", "ZN", "AU", "AG", "SC", "TA", "M", "Y", "P", "SR", "CF", "C"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out", default="artifacts/phase2")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--synthetic-scenario", default="regime", choices=["regime", "null_const", "null_volonly"])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n-days", type=int, default=2500)
    ap.add_argument("--n-null", type=int, default=100)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--roll-rule", choices=["auto", "oi", "official"], default="auto")
    ap.add_argument("--products", default=None)
    ap.add_argument("--min-amount-wan", type=float, default=None, help="liquidity latch (10k CNY/day median); default 10000")
    args = ap.parse_args()

    ep = ExistenceParams(n_boot=args.n_boot, n_panel_null=args.n_null, seed=args.seed)
    roll = RollParams(rule=args.roll_rule)
    products = [p.strip().upper() for p in args.products.split(",")] if args.products else None
    pparams = PanelParams() if args.min_amount_wan is None else PanelParams(min_median_amount_wan=args.min_amount_wan)

    if args.synthetic:
        products = products or SYNTH_PRODUCTS
        data = make_synthetic_futures(products + ["IF"], scenario=args.synthetic_scenario, n_days=args.n_days, seed=args.seed)
        tmp = tempfile.mkdtemp(prefix="synthetic_raw_")
        store = RawStore(tmp)
        cfg = TushareConfig(token="synthetic", max_calls_per_min=10**6)
        client = TushareClient(cfg, transport=FakeTushareTransport(data), sleep=lambda s: None)
        fetch_universe(client, store, products + ["IF"], start="20100101")
        source = "synthetic-fallback"
    else:
        store = RawStore(args.raw_dir)
        source = "tushare"
    res = run_phase2(store, products=products, source=source, ep=ep, roll=roll, panel_params=pparams)
    write_artifacts(res, args.out)
    print(f"wrote {args.out}/summary.md")
    print(res.primary[["proxy", "expected_sign", "diff", "ci_lo", "ci_hi", "verdict"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
