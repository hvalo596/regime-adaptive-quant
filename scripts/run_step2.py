"""Step 2: state existence on China futures (Tushare) or, without data, a synthetic fallback through the same code path.

    export TUSHARE_TOKEN=...                       # secret, never written anywhere
    python scripts/fetch_tushare_futures.py --group all                       # 20-year default window
    python scripts/run_step2.py --raw-dir data/raw --out artifacts/step2
    python scripts/run_step2.py --synthetic --kind regime --out artifacts/step2_synthetic     # plumbing check, NOT evidence
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.step2 import load_real, synthetic_dataset  # noqa: E402
from regime_quant.step2_run import run_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out", default="artifacts/step2")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--kind", default="regime", help="synthetic world kind (regime, N0z, ...)")
    ap.add_argument("--effect", type=float, default=0.15)
    ap.add_argument("--n-days", type=int, default=2500)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--min-years", type=float, default=20.0, help="required calendar span of the commodity analysis window; the run still completes but flags a shortfall in summary.json and coverage_panel.csv")
    args = ap.parse_args()
    out = Path(args.out)
    if args.synthetic:
        ds = synthetic_dataset(args.kind, args.effect, args.n_days)
    else:
        try:
            ds = load_real(args.raw_dir)
        except FileNotFoundError as e:
            out.mkdir(parents=True, exist_ok=True)
            (out / "BLOCKED.md").write_text(f"# Step 2 blocked\n\n{e}\n\nSet TUSHARE_TOKEN (secret) and run scripts/fetch_tushare_futures.py, then re-run.\n")
            print(f"BLOCKED: {e}", file=sys.stderr)
            return 3
    run_all(ds, out, scale=args.scale, min_years=args.min_years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
