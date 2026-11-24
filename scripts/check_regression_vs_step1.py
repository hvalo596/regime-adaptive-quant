"""Bit-for-bit regression check of the shared pipeline against the step-1 branch: pass the path of a checkout of the step-1 branch.

    git worktree add /tmp/wt_step1 origin/cursor/step1-state-construction-2dd4
    python scripts/check_regression_vs_step1.py /tmp/wt_step1
Runs the same synthetic worlds through the old and the new `run_state_pipeline` (the step-1 calibration file is used for both) and
compares tau, s, D, C, V and the gross portfolio return; prints 'identical' per field."""

from __future__ import annotations

import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

CHILD = r"""
import sys, pickle, warnings
warnings.filterwarnings("ignore")
src, cal_path, out = sys.argv[1:4]
sys.path.insert(0, src)
from regime_quant.world import WorldSpec, generate
from regime_quant.pipeline import run_state_pipeline
from regime_quant.nullcal import load
cal = load(cal_path)
res = {}
for seed, eff in ((3, 0.15), (8, 0.0)):
    w = generate(WorldSpec(kind="regime", effect=eff, seed=seed, mean_dwell=(300.0,) * 4))
    r = run_state_pipeline(w.ret, cal)
    res[seed] = dict(tau_m=r.tau_m, tau_r=r.tau_r, s=r.s, D=r.D_next, C=r.conc.C, gross=r.portfolio.gross_next, V=r.env.V)
pickle.dump(res, open(out, "wb"))
"""


def main() -> int:
    old = Path(sys.argv[1])
    new = Path(__file__).resolve().parents[1]
    cal = old / "artifacts" / "step1" / "calibration.json"
    outs = {}
    for tag, root in (("old", old), ("new", new)):
        out = Path(tempfile.gettempdir()) / f"regress_{tag}.pkl"
        subprocess.run([sys.executable, "-c", CHILD, str(root / "src"), str(cal), str(out)], check=True)
        outs[tag] = pickle.load(open(out, "rb"))
    ok = True
    for seed in outs["old"]:
        for f in outs["old"][seed]:
            x, y = np.asarray(outs["old"][seed][f], float), np.asarray(outs["new"][seed][f], float)
            same = np.array_equal(np.isnan(x), np.isnan(y)) and (not np.isfinite(x).any() or np.nanmax(np.abs(x - y)) == 0)
            ok &= bool(same)
            print(seed, f, "identical" if same else "DIFFERENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
