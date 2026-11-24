"""Steps 3 and 4 on the real China-futures panels, plus the synthetic validation (planted states, nulls, switch delays).

    python scripts/run_step34.py --raw-dir data/raw --out3 artifacts/step3 --out4 artifacts/step4 [--scale 1.0]
Needs the cache written by fetch_tushare_futures.py and the calibration from step 2 (artifacts/step2/calibration_commodity.json).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from regime_quant.config import MOM_MAIN, REV_MAIN  # noqa: E402
from regime_quant.data.panel import PanelParams  # noqa: E402
from regime_quant.data.universe import COMMODITY_SECTORS  # noqa: E402
from regime_quant.nondefining import margin_events_from_settle  # noqa: E402
from regime_quant.nullcal import ALL_SPECS, calibrate  # noqa: E402
from regime_quant.step2 import load_real  # noqa: E402
from regime_quant.step34_run import log, panel_report, planted_task, run_pool, switch_delay_task  # noqa: E402

LONG = (300.0,) * 4
DOC = (120.0, 20.0, 30.0, 120.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out3", default="artifacts/step3")
    ap.add_argument("--out4", default="artifacts/step4")
    ap.add_argument("--cal", default="artifacts/step2/calibration_commodity.json")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-synth", action="store_true")
    args = ap.parse_args()
    out3, out4 = Path(args.out3), Path(args.out4)
    out3.mkdir(parents=True, exist_ok=True)
    out4.mkdir(parents=True, exist_ok=True)
    sc = args.scale
    log("load real data")
    ds = load_real(args.raw_dir, panel_params=PanelParams())
    cal = json.loads(Path(args.cal).read_text())
    com = ds.panels["commodity"]
    ret_c = com.returns
    held = pd.DataFrame({q: c["held"] for q, c in com.continuous.items()}).reindex(ret_c.index)
    ev_mask = margin_events_from_settle(ds.settle_params, held) if ds.settle_params is not None else None
    summaries = {}
    summaries["commodity"] = panel_report("commodity", ret_c, cal, out3, out4, deep=True, ev_mask=ev_mask)
    for sector in COMMODITY_SECTORS:
        cols = [p for p in ret_c.columns if ds.sector_of.get(p) == sector]
        if len(cols) < 5:
            continue
        sub = ret_c[cols].dropna(how="all")
        cs = calibrate(ALL_SPECS, n_sims=max(int(20 * sc), 6), n_days=len(sub), n_assets=len(cols), mask=~sub.isna().to_numpy(), seed0=960_000)
        cs["C_threshold"] = cal["C_threshold"]
        summaries[f"sector_{sector}"] = panel_report(f"sector_{sector}", sub, cs, out3, out4)
    for g in ("index", "bond"):
        if g in ds.panels:
            sub = ds.panels[g].returns.dropna(how="all")
            cg = calibrate(ALL_SPECS, n_sims=max(int(20 * sc), 6), n_days=len(sub), n_assets=sub.shape[1], mask=~sub.isna().to_numpy(), min_assets=3, seed0=950_000)
            cg["C_threshold"] = cal["C_threshold"]
            try:
                summaries[f"panel_{g}"] = panel_report(f"panel_{g}", sub, cg, out3, out4, min_assets=3)
            except Exception as e:  # noqa: BLE001 - short panels may not support the 750-day training window
                summaries[f"panel_{g}"] = {"error": str(e)}
    (out3 / "panel_summaries.json").write_text(json.dumps(summaries, indent=2, default=float))
    if args.skip_synth:
        return
    mask = ~ret_c.isna().to_numpy()
    n_null, n_pl, n_sw = max(int(120 * sc), 8), max(int(60 * sc), 6), max(int(30 * sc), 4)
    log(f"pipeline null on the real mask ({n_null} sims)")
    tasks = [dict(kind=("N0z" if i % 2 == 0 else "N0"), seed=970_000 + i, mask=True, lr=True, tag="pipeline-null") for i in range(n_null)]
    pd.DataFrame(run_pool(planted_task, tasks, cal, mask, args.workers)).to_csv(out3 / "pipeline_null_filter.csv", index=False)
    log("null worlds, unmasked")
    tasks = []
    for kind in ("N0z", "N0", "N1", "N3", "N4"):
        tasks += [dict(kind=kind, seed=980_000 + 1000 * len(tasks) // n_pl + i, kw=dict(effect=0.10), tag=kind, lr=True) for i in range(n_pl)]
    pd.DataFrame(run_pool(planted_task, tasks, cal, None, args.workers)).to_csv(out3 / "null_worlds_filter.csv", index=False)
    log("planted worlds")
    tasks = []
    for label, dwell in (("doc-dwell", DOC), ("long-dwell", LONG)):
        for eff in (0.10, 0.15, 0.20):
            tasks += [dict(kind="regime", seed=990_000 + int(eff * 1000) * 13 + i + (50_000 if label == "long-dwell" else 0), kw=dict(effect=eff, mean_dwell=dwell), tag=f"{label}|{eff}", lr=True) for i in range(n_pl)]
    pd.DataFrame(run_pool(planted_task, tasks, cal, None, args.workers)).to_csv(out3 / "planted_filter.csv", index=False)
    log("switch delays")
    tasks = []
    for eff in (0.10, 0.15, 0.20):
        tasks += [dict(which="M", seed=1_000_000 + i + int(eff * 1e3), effect=eff, dwell=400.0) for i in range(n_sw)]
        tasks += [dict(which="R", seed=1_010_000 + i + int(eff * 1e3), effect=eff, dwell=150.0) for i in range(n_sw)]
    pd.DataFrame(run_pool(switch_delay_task, tasks, cal, None, args.workers)).to_csv(out3 / "switch_delays.csv", index=False)
    log("done")


if __name__ == "__main__":
    main()
