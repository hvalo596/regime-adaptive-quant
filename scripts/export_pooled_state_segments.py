#!/usr/bin/env python3
"""Export pooled commodity rule-state segments (>=10 valid days) with calendar dates.

Requires: pip install -e ., artifacts/step2/calibration_commodity.json, data/raw (or TUSHARE_TOKEN / TUSHARE to fetch).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from regime_quant.step2 import Ledger, analyze_panel, load_real  # noqa: E402
from regime_quant.statemachine import segments  # noqa: E402


def export_pooled_segments(raw_dir: Path, out_csv: Path, min_days: int = 10) -> int:
    if not raw_dir.is_dir():
        print("ERROR: missing data/raw — run scripts/fetch_tushare_futures.py (TUSHARE_TOKEN or TUSHARE)", file=sys.stderr)
        return 2
    cal_path = REPO / "artifacts/step2/calibration_commodity.json"
    cal = json.loads(cal_path.read_text())
    ret = load_real(raw_dir).panels["commodity"].returns
    pr = analyze_panel("commodity", ret, cal, Ledger())
    dates = ret.index
    valid = np.asarray(pr.run.valid, dtype=bool)
    lab = np.asarray(pr.labels, dtype=object)
    rows = []
    for state in ("I", "II", "III", "IV"):
        for a, b in segments(lab, state, min_days):
            if not valid[a:b].all():
                continue
            rows.append(
                {
                    "start_date": dates[a].strftime("%Y-%m-%d"),
                    "end_date": dates[b - 1].strftime("%Y-%m-%d"),
                    "state": state,
                    "length_days": b - a,
                }
            )
    import pandas as pd

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["start_date", "state"]).reset_index(drop=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(json.dumps({"rows": len(df), "out": str(out_csv)}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", type=Path, default=REPO / "data/raw")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-days", type=int, default=10)
    args = ap.parse_args()
    return export_pooled_segments(args.raw_dir, args.out, args.min_days)


if __name__ == "__main__":
    raise SystemExit(main())