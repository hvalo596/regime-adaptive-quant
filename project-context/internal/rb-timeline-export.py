#!/usr/bin/env python3
"""Export RB-era dated step2 segments and step3 HMM p>0.5 up-edges (commodity panel).

Requires: pip install -e /agent/repos/regime-adaptive-quant, data/raw, TUSHARE_TOKEN only for fetch.
Run from repo root:
  python /cursor/stores/bc-d8a1a980-0799-49a7-8a92-335d96978291/internal/rb-timeline-export.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/agent/repos/regime-adaptive-quant")
sys.path.insert(0, str(REPO / "src"))

from regime_quant.step2 import Ledger, analyze_panel, load_real  # noqa: E402
from regime_quant.step34 import build_states, signals  # noqa: E402
from regime_quant.step34_run import evaluate_all  # noqa: E402
from regime_quant.statemachine import segments  # noqa: E402

RB_ERA_START = pd.Timestamp("2009-06-26")
MIN_SEG_DAYS = 10
OUT_DIR = Path(__file__).resolve().parent


def pooled_segments_table(dates: pd.DatetimeIndex, labels: np.ndarray, valid: np.ndarray, rb: np.ndarray) -> pd.DataFrame:
    rows = []
    for state in ("I", "II", "III", "IV"):
        for a, b in segments(labels, state, MIN_SEG_DAYS):
            if not valid[a:b].all():
                continue
            mask = rb[a:b]
            rows.append(
                {
                    "start_date": dates[a].strftime("%Y-%m-%d"),
                    "end_date": dates[b - 1].strftime("%Y-%m-%d"),
                    "state": state,
                    "length_days": b - a,
                    "rb_active_days_inside": int(mask.sum()),
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["start_date", "state"]).reset_index(drop=True)
    return df


def up_edges(dates: pd.DatetimeIndex, p: np.ndarray, mask: np.ndarray) -> list[str]:
    cur = (p > 0.5) & mask
    trans = cur & ~np.r_[False, cur[:-1]]
    return [str(dates[i].date()) for i in np.flatnonzero(trans)]


def fmt_edge_list(name: str, edges: list[str], head: int = 15, tail: int = 15) -> str:
    lines = [f"**{name}** up-edges (p>0.5): **{len(edges)}** total"]
    if len(edges) <= head + tail:
        lines.append(", ".join(edges))
    else:
        lines.append("first " + str(head) + ": " + ", ".join(edges[:head]))
        lines.append("last " + str(tail) + ": " + ", ".join(edges[-tail:]))
    return "\n".join(lines)


def main() -> int:
    cal_path = REPO / "artifacts/step2/calibration_commodity.json"
    raw_dir = REPO / "data/raw"
    if not raw_dir.is_dir():
        print("ERROR: missing data/raw — run scripts/fetch_tushare_futures.py with TUSHARE_TOKEN set", file=sys.stderr)
        return 2

    cal = json.loads(cal_path.read_text())
    ret = load_real(raw_dir).panels["commodity"].returns
    pr = analyze_panel("commodity", ret, cal, Ledger())
    dates = ret.index
    valid = np.asarray(pr.run.valid, dtype=bool)
    lab = np.asarray(pr.labels, dtype=object)
    rb = ret["RB"].notna().to_numpy() & valid

    rb_idx = np.flatnonzero(rb)
    rb_first = dates[rb_idx[0]].strftime("%Y-%m-%d")
    rb_last = dates[rb_idx[-1]].strftime("%Y-%m-%d")
    rb_days = int(rb.sum())
    quad = {k: int((lab[rb] == k).sum()) for k in ("I", "II", "III", "IV")}

    seg_df = pooled_segments_table(dates, lab, valid, rb)
    st = build_states(ret.to_numpy(float), cal)
    common = evaluate_all(st, signals(st), ret.to_numpy(float))[1]
    era = (dates >= RB_ERA_START) & common & np.isfinite(st.pm) & np.isfinite(st.pr)
    pm_edges = up_edges(dates, st.pm, era)
    pr_edges = up_edges(dates, st.pr, era)

    seg_csv = OUT_DIR / "rb-pooled-segments-ge10-2026-11-26.csv"
    pm_txt = OUT_DIR / "rb-hmm-pM-upedges-from-2009-06-26.txt"
    pr_txt = OUT_DIR / "rb-hmm-pR-upedges-from-2009-06-26.txt"
    meta_json = OUT_DIR / "rb-timeline-meta-2026-11-26.json"

    seg_df.to_csv(seg_csv, index=False)
    pm_txt.write_text("\n".join(pm_edges) + ("\n" if pm_edges else ""))
    pr_txt.write_text("\n".join(pr_edges) + ("\n" if pr_edges else ""))
    meta = {
        "rb_valid_first": rb_first,
        "rb_valid_last": rb_last,
        "rb_valid_days": rb_days,
        "quadrant_counts_rb_and_valid": quad,
        "pooled_segments_ge10_rows": len(seg_df),
        "pM_upedges_from_2009_06_26": len(pm_edges),
        "pR_upedges_from_2009_06_26": len(pr_edges),
    }
    meta_json.write_text(json.dumps(meta, indent=2) + "\n")

    print(json.dumps(meta, indent=2))
    print(fmt_edge_list("p^M", pm_edges))
    print(fmt_edge_list("p^R", pr_edges))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())