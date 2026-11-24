"""Step 4 extras on the real commodity panel: Sharpe levels with block-bootstrap intervals, sub-period table, the break-even check of doc 4.5, EWA sensitivity grid.
Uses the cached real returns (a pickle with `ret`) so it does not reload the Tushare cache."""

from __future__ import annotations

import json
import os
import pickle
import sys
import warnings
from pathlib import Path

for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[k] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from regime_quant.config import InferenceParams, StateParams, TRADING_DAYS  # noqa: E402
from regime_quant.inference import quantile_ci, sharpe, stationary_bootstrap_indices  # noqa: E402
from regime_quant.step34 import build_states, evaluate_all, signals  # noqa: E402
from regime_quant.step4 import Strategy, evaluate, ewa_signal  # noqa: E402

pkl, cal_path, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
d = pickle.load(open(pkl, "rb"))
cal = json.load(open(cal_path))
ret_df = d["ret"]
ret = ret_df.to_numpy(float)
st = build_states(ret, cal)
sig = signals(st)
ev, common = evaluate_all(st, sig, ret)
ip = InferenceParams(n_boot=1000)
rng = np.random.default_rng(1)
dates = ret_df.index
rows = []
for k in ("EW50+VT", "MOM+VT", "REV+VT", "TP60+VT", "EWA+VT", "RULE+VT", "FILT-PEN+VT", "FILT-PEN-G+VT", "LEARNED+VT", "EW50", "MOM"):
    for c in (0.0, 1.0):
        x = ev[k].net[c][common]
        x = x[np.isfinite(x)]
        idx = stationary_bootstrap_indices(len(x), ip.mean_block, ip.n_boot, rng)
        b = x[idx]
        sr = b.mean(1) / b.std(1, ddof=1) * np.sqrt(TRADING_DAYS)
        lo, hi = quantile_ci(sr, 0.95)
        rows.append({"strategy": k, "cost_mult": c, "sharpe": sharpe(x), "ci_lo": lo, "ci_hi": hi, "ann_mean": x.mean() * TRADING_DAYS, "ann_vol": x.std(ddof=1) * np.sqrt(TRADING_DAYS), "years": len(x) / TRADING_DAYS})
pd.DataFrame(rows).to_csv(out / "sharpe_levels_commodity.csv", index=False)

# sub-periods (equal halves of the evaluation window and two named blocks)
first = np.flatnonzero(common)[0]
mid = (first + np.flatnonzero(common)[-1]) // 2
rows = []
for name, lo_i, hi_i in (("first half", first, mid), ("second half", mid, len(common))):
    m = np.zeros(len(common), bool)
    m[lo_i:hi_i] = True
    m &= common
    for k in ("EW50+VT", "MOM+VT", "EWA+VT", "RULE+VT", "FILT-PEN+VT", "FILT-PEN-G+VT", "LEARNED+VT"):
        rows.append({"period": name, "start": str(dates[np.flatnonzero(m)[0]].date()), "end": str(dates[np.flatnonzero(m)[-1]].date()), "strategy": k, "sharpe_c0": sharpe(ev[k].net[0.0][m]), "sharpe_c1": sharpe(ev[k].net[1.0][m])})
pd.DataFrame(rows).to_csv(out / "subperiods_commodity.csv", index=False)

# EWA grid (logged as additional trials)
target = StateParams().target_ann_vol / np.sqrt(TRADING_DAYS)
legs = st.run.legs
rows = []
for lam in (0.98, 0.99, 0.995):
    for eta in (0.25, 0.5, 1.0, 2.0):
        s = ewa_signal(legs.mom.x_next, legs.rev.x_next, target, lam, eta)
        e = evaluate(legs, ret, Strategy("EWA", s, True), cost_mults=(0.0, 1.0))
        m = common & np.isfinite(e.gross) & np.isfinite(s)
        rows.append({"lambda": lam, "eta": eta, "sharpe_c0": sharpe(e.net[0.0][m]), "sharpe_c1": sharpe(e.net[1.0][m]), "mean_s": float(np.nanmean(s[m]))})
pd.DataFrame(rows).to_csv(out / "ewa_grid_commodity.csv", index=False)

# break-even check (doc 4.5): reversal leg gross edge per unit of turnover vs the one-way cost
rev = ev["REV"]
tot_cost_ann = (ev["REV"].gross[common] - ev["REV"].net[1.0][common]).mean() * TRADING_DAYS
gross_ann = ev["REV"].gross[common].mean() * TRADING_DAYS
mom_cost = (ev["MOM"].gross[common] - ev["MOM"].net[1.0][common]).mean() * TRADING_DAYS
mom_gross = ev["MOM"].gross[common].mean() * TRADING_DAYS
pd.DataFrame([{"leg": "REV", "gross_ann": gross_ann, "cost_ann_1x": tot_cost_ann, "net_ann_1x": gross_ann - tot_cost_ann, "turnover_per_day": float(np.nanmean(rev.turnover[common]))},
              {"leg": "MOM", "gross_ann": mom_gross, "cost_ann_1x": mom_cost, "net_ann_1x": mom_gross - mom_cost, "turnover_per_day": float(np.nanmean(ev["MOM"].turnover[common]))}]).to_csv(out / "leg_breakeven_commodity.csv", index=False)
print("done")
