"""Aggregate the synthetic parts of the step 3 / 4 run into tables (CSV + markdown) and print the pipeline-level p-values for the real result."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from regime_quant.step1 import cp_interval  # noqa: E402

o3 = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/step3")
o4 = Path(sys.argv[2] if len(sys.argv) > 2 else "artifacts/step4")


def rate(df, col):
    k, n = int(df[col].sum()), int(df[col].notna().sum())
    lo, hi = cp_interval(k, n)
    return k / max(n, 1), lo, hi, n


lines = []

# ---------------------------------------------------------------- pipeline null on the real mask: p-values of the real statistics
pn = pd.read_csv(o3 / "pipeline_null_filter.csv")
real = {}
th = pd.read_csv(o3 / "theta_signals_commodity.csv").set_index("signal")
mc = pd.read_csv(o3 / "model_comparison_commodity.csv")
rows = []
for sig in ("RULE", "FILT-HARD", "FILT-PEN", "FILT-PEN-G"):
    if f"theta_c:{sig}" not in pn:
        continue
    null = pn[f"theta_c:{sig}"].dropna()
    obs = float(th.loc[sig, "theta_c"]) if sig in th.index else np.nan
    rows.append({"statistic": f"theta_c {sig}", "observed": obs, "null_mean": null.mean(), "null_sd": null.std(), "null_q95": null.quantile(0.95), "p_pipeline_one_sided": float((1 + (null >= obs).sum()) / (1 + len(null))), "n_null": len(null)})
for lab, chain in (("M", "M (20,5)"), ("R", "R (5,3)")):
    obs = float(mc[(mc.chain == chain) & mc.model.str.startswith("hmm-t-sticky")]["LR"].iloc[0])
    null = pn[f"LR:{lab}"].dropna()
    rows.append({"statistic": f"LR 2-state vs 1-state, chain {lab} (HMM-t, sticky)", "observed": obs, "null_mean": null.mean(), "null_sd": null.std(), "null_q95": null.quantile(0.95), "p_pipeline_one_sided": float((1 + (null >= obs).sum()) / (1 + len(null))), "n_null": len(null)})
pd.DataFrame(rows).to_csv(o3 / "pipeline_null_pvalues.csv", index=False)
lines += ["## pipeline-level null (real availability mask)", pd.DataFrame(rows).round(6).to_markdown(index=False)]

# ---------------------------------------------------------------- null worlds
nw = pd.read_csv(o3 / "null_worlds_filter.csv")
rows = []
for tag, d in nw.groupby("tag"):
    for sig in ("RULE", "FILT-HARD", "FILT-PEN", "FILT-PEN-G"):
        if f"detect:{sig}" in d:
            r, lo, hi, n = rate(d, f"detect:{sig}")
            rows.append({"world": tag, "test": f"theta_c decision {sig}", "rate": r, "ci_lo": lo, "ci_hi": hi, "n": n})
    for c in ("c0.0", "c1.0"):
        for a in ("FILT-PEN+VT", "FILT-PEN-G+VT", "RULE+VT"):
            col = f"p_gt:{a}-EW50+VT:{c}"
            if col in d:
                d2 = d.assign(rej=d[col] < 0.05)
                r, lo, hi, n = rate(d2, "rej")
                rows.append({"world": tag, "test": f"Sharpe({a}) > Sharpe(EW50+VT) p<.05 [{c}]", "rate": r, "ci_lo": lo, "ci_hi": hi, "n": n})
tab = pd.DataFrame(rows)
tab.to_csv(o3 / "null_worlds_rates.csv", index=False)
lines += ["## null worlds: false-positive rates", tab.pivot_table(index="test", columns="world", values="rate").round(3).to_markdown()]

# ---------------------------------------------------------------- planted worlds
pl = pd.read_csv(o3 / "planted_filter.csv")
rows = []
for tag, d in pl.groupby("tag"):
    row = {"world": tag, "n": len(d)}
    for k in ("auc:pM", "auc:pR", "auc:tauM", "auc:tauR", "degenerate:M", "degenerate:R"):
        row[k] = d[k].mean()
    for sig in ("RULE", "FILT-HARD", "FILT-PEN", "FILT-PEN-G", "TP60", "EWA", "ORACLE"):
        if f"detect:{sig}" in d:
            row[f"detect:{sig}"] = d[f"detect:{sig}"].mean()
    for sig in ("RULE", "FILT-PEN", "FILT-PEN-G", "ORACLE", "TP60", "EWA"):
        if f"timing_ann:{sig}" in d:
            row[f"timing_ann:{sig}"] = d[f"timing_ann:{sig}"].mean()
    for k in ("EW50+VT", "MOM+VT", "RULE+VT", "FILT-PEN+VT", "FILT-PEN-G+VT", "TP60+VT", "EWA+VT", "ORACLE+VT"):
        for c in ("c0.0", "c1.0"):
            col = f"sharpe:{k}:{c}"
            if col in d:
                row[col] = d[col].mean()
    for a in ("FILT-PEN+VT", "FILT-PEN-G+VT", "RULE+VT", "ORACLE+VT"):
        for c in ("c0.0", "c1.0"):
            col = f"p_gt:{a}-EW50+VT:{c}"
            if col in d:
                row[f"beats_EW50VT:{a}:{c}"] = float((d[col] < 0.05).mean())
    ot, ft = row.get("timing_ann:ORACLE"), row.get("timing_ann:FILT-PEN")
    row["efficiency_timing_FILT-PEN"] = ft / ot if ot else np.nan
    ftg = row.get("timing_ann:FILT-PEN-G")
    row["efficiency_timing_FILT-PEN-G"] = ftg / ot if ot else np.nan
    rows.append(row)
pt = pd.DataFrame(rows)
pt.to_csv(o4 / "planted_info_value.csv", index=False)
pt.to_csv(o3 / "planted_summary.csv", index=False)
lines += ["## planted worlds", pt.round(3).T.to_markdown()]

# ---------------------------------------------------------------- switch delays
sd = pd.read_csv(o3 / "switch_delays.csv")
sd["hmm_delays"] = sd["hmm_delays"].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
sd["rule_delays"] = sd["rule_delays"].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
rows = []
for (w, e), d in sd.groupby(["which", "effect"]):
    h = np.concatenate([np.array(x, float) for x in d.hmm_delays]) if len(d) else np.array([])
    r = np.concatenate([np.array(x, float) for x in d.rule_delays]) if len(d) else np.array([])
    rows.append({"crowd": w, "effect": e, "sims": len(d), "hmm_switches": int(d.hmm_n.sum()), "hmm_detect": len(h) / max(int(d.hmm_n.sum()), 1), "hmm_median_delay": np.median(h) if len(h) else np.nan,
                 "rule_switches": int(d.rule_n.sum()), "rule_detect": len(r) / max(int(d.rule_n.sum()), 1), "rule_median_delay": np.median(r) if len(r) else np.nan, "auc_hmm": d.auc_hmm.mean(), "auc_rule": d.auc_rule.mean()})
st = pd.DataFrame(rows)
st.to_csv(o3 / "switch_delay_summary.csv", index=False)
lines += ["## switch worlds", st.round(3).to_markdown(index=False)]
(o3 / "summary_synthetic.md").write_text("\n\n".join(lines))
print("\n\n".join(lines))
