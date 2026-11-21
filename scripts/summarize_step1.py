"""Read artifacts/step1/*.csv, run the engine checks, grade the pre-registered acceptance criteria (step1.py docstring),
write acceptance.json and summary.md."""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.backtest import run_weights, state_weights  # noqa: E402
from regime_quant.config import CostParams, MOM_MAIN, REV_MAIN  # noqa: E402
from regime_quant.eventengine import reconcile  # noqa: E402
from regime_quant.nullcal import load  # noqa: E402
from regime_quant.pipeline import run_state_pipeline  # noqa: E402
from regime_quant.world import WorldSpec, generate  # noqa: E402

warnings.filterwarnings("ignore")
out = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/step1")
cal = load(out / "calibration.json")


def grade(rate: float, lo: float, hi: float, limit: float = 0.05) -> str:
    if rate <= limit:
        return "PASS"
    return "PASS*" if lo <= limit else "FAIL"


acc: dict = {}

# ------------------------------------------------------------------ A1 engine
w = generate(WorldSpec(kind="regime", effect=0.15, seed=123))
ret = w.ret.copy()
ret[:400, 30:] = np.nan
run = run_state_pipeline(ret, cal)
rec = reconcile(ret, MOM_MAIN, REV_MAIN, run.s, run.kappa, run.excl)
run0 = run_state_pipeline(ret, cal, use_exclusion=False, use_kappa=False, with_portfolio=False)
W0 = state_weights(run0.legs, run0.s, None, None)
pf0 = run_weights(ret, W0, run0.legs.vol, CostParams(0.0, 0.0))
lhs = pf0.gross_next - 0.5 * (run0.legs.mom.x_next + run0.legs.rev.x_next)
rhs = 0.5 * run0.s * run0.legs.D_next
ok = np.isfinite(lhs) & np.isfinite(rhs)
ident = float(np.max(np.abs(lhs[ok] - rhs[ok])))
t0 = 1500
tam = ret.copy()
tam[t0 + 1 :] = np.random.default_rng(0).standard_normal(tam[t0 + 1 :].shape) * 0.05
alt = run_state_pipeline(tam, cal)
la = {}
for name, a, b in (("tau_m", run.tau_m, alt.tau_m), ("tau_r", run.tau_r, alt.tau_r), ("s", run.s, alt.s), ("C", run.conc.C, alt.conc.C), ("V", run.env.V, alt.env.V),
                   ("Phi_perp", run.env.Phi_perp, alt.env.Phi_perp), ("weights", run.portfolio.weights, alt.portfolio.weights)):
    la[name] = float(np.nanmax(np.abs(np.asarray(a, float)[: t0 + 1] - np.asarray(b, float)[: t0 + 1])))
acc["A1"] = {"reconcile": rec, "identity_max_abs": ident, "lookahead_max_abs_diff": la, "n_days_compared": int(ok.sum()),
             "pass": bool(rec["gross_max_abs_diff"] < 1e-10 and rec["weights_max_abs_diff"] < 1e-10 and rec["cost_max_abs_diff"] < 1e-10 and ident < 1e-12 and max(la.values()) < 1e-12)}
(out / "engine_checks.json").write_text(json.dumps(acc["A1"], indent=2))

# ------------------------------------------------------------------ A2 variables
cc = pd.read_csv(out / "calibration_check.csv")
cf = pd.read_csv(out / "closed_form_vs_sample.csv")
big = cf[cf.closed_form.abs() >= 0.03]
sign_ok = bool((np.sign(big["sample"]) == np.sign(big["closed_form"])).all())
ratio_ok = bool(big["ratio"].between(0.5, 1.5).all())
tau_ok = bool(((cc.tau_mean.abs() < 0.2) & cc.tau_sd.between(0.85, 1.15) & cc["P(tau>=1.28)"].between(0.05, 0.15)).all())
acc["A2"] = {"tau_null_ok": tau_ok, "closed_form_sign_ok": sign_ok, "closed_form_ratio_ok": ratio_ok, "ratio_min": float(big["ratio"].min()), "ratio_max": float(big["ratio"].max()), "pass": tau_ok and sign_ok and ratio_ok}

# ------------------------------------------------------------------ A3 recovery
ps = pd.read_csv(out / "power_summary.csv")
r = ps[(ps.world == "long-dwell") & (ps.effect == 0.15)].iloc[0]
acc["A3"] = {"auc_M_long_dwell_0.15": float(r["rec:auc_M"]), "auc_R_long_dwell_0.15": float(r["rec:auc_R"]), "pass": bool(r["rec:auc_M"] >= 0.75 and r["rec:auc_R"] >= 0.80)}

# ------------------------------------------------------------------ A4-A6 null controls
ns = pd.read_csv(out / "null_summary.csv")
d4 = ns[(ns.combo == "M-B|R-A") & ns.rule.str.startswith("decision")]
acc["A4"] = {row.world: {"fpr": row.fpr, "ci": [row.ci_lo, row.ci_hi], "grade": grade(row.fpr, row.ci_lo, row.ci_hi)} for row in d4.itertuples()}
acc["A4"]["pass"] = all(v["grade"] != "FAIL" for k, v in acc["A4"].items())
d5 = ns[ns.combo == "H5"]
acc["A5"] = {row.world: {"fpr": row.fpr, "ci": [row.ci_lo, row.ci_hi], "grade": grade(row.fpr, row.ci_lo, row.ci_hi)} for row in d5.itertuples()}
acc["A5"]["pass"] = all(v["grade"] != "FAIL" for k, v in acc["A5"].items())
# Association (A6): mean over simulated worlds of the standardised difference mean(z|delta=1) - mean(z|delta=0). Under "no
# systematic association" this mean is 0; a one-sample t-test over the sims gives the p-value and the pass line is |mean| < 0.10 sd.
from scipy import stats  # noqa: E402

raw = pd.read_csv(out / "null_controls_raw.csv")
pairs = [(d_, z_) for d_ in ("dM", "dR") for z_ in ("zV", "zPhiP", "C")]
rows = []
for world in raw.tag.unique():
    d = raw[raw.tag == world]
    if f"assoc:dM:zV:std_diff" not in d or d["assoc:dM:zV:std_diff"].isna().all():
        continue
    for d_, z_ in pairs:
        x = d[f"assoc:{d_}:{z_}:std_diff"].dropna()
        t = stats.ttest_1samp(x, 0.0)
        rows.append({"world": world, "pair": f"{d_}~{z_}", "n_sims": len(x), "mean_std_diff": float(x.mean()), "sd_across_sims": float(x.std()), "t": float(t.statistic), "p": float(t.pvalue),
                     "shift_test_reject_rate": float(d[f"assoc:{d_}:{z_}:reject"].mean()), "grade": "PASS" if abs(x.mean()) < 0.10 else "FAIL"})
assoc = pd.DataFrame(rows)
assoc.to_csv(out / "association_systematic.csv", index=False)
d6 = assoc[assoc.world == "N2"]
acc["A6"] = {row.pair: {"mean_std_diff": row.mean_std_diff, "t": row.t, "grade": row.grade} for row in d6.itertuples()}
acc["A6"]["pass"] = all(v["grade"] == "PASS" for k, v in acc["A6"].items())
d6c = assoc[assoc.world == "N2c"]
acc["A6"]["N2c_reported"] = {row.pair: {"mean_std_diff": row.mean_std_diff, "t": row.t, "grade": row.grade} for row in d6c.itertuples()}

# ------------------------------------------------------------------ A7 delay
dl = pd.read_csv(out / "delay_summary.csv")
main = dl[dl.spec.isin(["M-B", "R-A"])]
acc["A7"] = {"ratios_main": {f"{r.crowd}|{r.effect}": float(r.ratio_median_over_window_pred) for r in main.itertuples()}, "pass": bool(main.ratio_median_over_window_pred.between(0.6, 1.5).all())}

acc["A8"] = {"reported": True}
(out / "acceptance.json").write_text(json.dumps(acc, indent=2, default=float))

# ------------------------------------------------------------------ markdown
lines = ["# Step 1 acceptance summary (auto-generated)", ""]
for k in ("A1", "A2", "A3", "A4", "A5", "A6", "A7"):
    lines.append(f"- {k}: {'PASS' if acc[k]['pass'] else 'FAIL'}")
lines += ["", "## Null controls: false-positive rate of the Theta decision rule (main spec M-B/R-A)", "", ns[(ns.combo == "M-B|R-A") & ns.rule.str.startswith("decision")].round(4).to_markdown(index=False)]
lines += ["", "## All combos x rules", "", ns[ns.combo.str.contains(r"\|")].pivot_table(index=["world", "rule"], columns="combo", values="fpr").round(3).to_markdown()]
lines += ["", "## H5 and associations (shift-test reject rates)", "", ns[ns.combo.isin(["H5"]) | ns.combo.str.startswith("assoc")].pivot_table(index="world", columns="combo", values="fpr").round(3).to_markdown()]
lines += ["", "## Systematic association: mean standardised difference (A6, pass < 0.10)", "", assoc.pivot_table(index="world", columns="pair", values="mean_std_diff").round(3).to_markdown()]
lines += ["", "## Power and recovery", "", ps[["world", "effect", "n", "M-B|R-A:detect", "M-A|R-A:detect", "M-B|R-B-gap:detect", "rec:auc_M", "rec:auc_R", "rec:quad_accuracy"]].round(3).to_markdown(index=False)]
lines += ["", "## Delay", "", dl.round(2).to_markdown(index=False)]
(out / "summary.md").write_text("\n".join(lines))
print(json.dumps({k: (v["pass"] if isinstance(v, dict) and "pass" in v else v) for k, v in acc.items()}, indent=2))
