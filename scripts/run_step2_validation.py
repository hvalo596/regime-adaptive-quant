"""Validate the step-2 code path on synthetic fallbacks (planted states / stateless / informed events). NOT evidence about markets:
it only shows that the same code finds what is planted and does not find what is not."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.step2 import synthetic_dataset  # noqa: E402
from regime_quant.step2_run import run_all  # noqa: E402

scale = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
base = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("artifacts/step2_synthetic")
for name, kw in (("planted_effect015_longdwell", dict(kind="regime", effect=0.15, mean_dwell=(300.0,) * 4)),
                 ("planted_effect010_docdwell", dict(kind="regime", effect=0.10)),
                 ("null_N0z", dict(kind="N0z", effect=0.0)),
                 ("informed_z4", dict(kind="informed", effect=0.0, informed_per_year=6.0, informed_z=4.0))):
    print("=== ", name, flush=True)
    ds = synthetic_dataset(seed=17, n_days=2500, n_commodity=40, with_carry=True, **kw)
    run_all(ds, base / name, scale=scale)
