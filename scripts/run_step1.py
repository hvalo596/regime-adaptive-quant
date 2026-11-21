"""Run all step-1 acceptance experiments and write artifacts/step1/*.csv, acceptance.json and summary.md.

    python scripts/run_step1.py --out artifacts/step1 --scale 1.0      # full run (~25 min on 4 cores)
    python scripts/run_step1.py --out /tmp/s1 --scale 0.05             # smoke run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.config import MOM_MAIN, REV_MAIN, StateParams, kappa_LH  # noqa: E402
from regime_quant.nullcal import ALL_SPECS, calibrate, calibrate_c_null, save  # noqa: E402
from regime_quant.recovery import d_star  # noqa: E402
from regime_quant.statevars import mean_sq_corr, mr_stat, standardise  # noqa: E402
from regime_quant.step1 import COMBOS, SPECS, cp_interval, delay_task, rate_table, run_pool, sim_task, working_bias_check  # noqa: E402
from regime_quant.world import STATES, WorldSpec, generate, solve_states  # noqa: E402

warnings.filterwarnings("ignore")
NULL_KINDS = ["N0z", "N0", "N1", "N2", "N2c", "N2b", "N3", "N4"]
EFFECTS = [0.0, 0.05, 0.10, 0.15, 0.20]
LONG = (300.0,) * 4
DOC = (120.0, 20.0, 30.0, 120.0)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/step1")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sc = args.scale
    n_null, n_pow, n_delay, n_inf = max(int(400 * sc), 8), max(int(150 * sc), 8), max(int(80 * sc), 6), max(int(100 * sc), 8)
    acc: dict = {}

    # ---------------------------------------------------------------------------------- calibration
    log("calibration")
    rule_specs = [replace(MOM_MAIN, name="M-B-W70", W=70), replace(REV_MAIN, name="R-A-W30", W=30)]
    cal = calibrate(ALL_SPECS + tuple(rule_specs), n_sims=max(int(60 * sc), 8))
    cal["C_threshold"] = calibrate_c_null(n_sims=max(int(24 * sc), 4))
    save(cal, out / "calibration.json")
    for sp in rule_specs:
        SPECS[sp.name] = sp

    # null check of tau on fresh seeds
    rows = []
    taus = {sp.name: [] for sp in ALL_SPECS}
    for k in range(max(int(40 * sc), 6)):
        w = generate(WorldSpec(kind="N0z", seed=700_000 + k))
        rt, _ = standardise(w.ret)
        for sp in ALL_SPECS:
            st = mr_stat(rt, sp)
            sign = 1 if sp.kind == "mom" else -1
            tau = sign * (st.rho - cal[sp.name]["bias"]) / (cal[sp.name]["se_mult"] * st.se_formula)
            taus[sp.name].append(tau[np.isfinite(tau)])
    for sp in ALL_SPECS:
        t = np.concatenate(taus[sp.name])
        rows.append({"spec": sp.name, "L": sp.L, "H": sp.H, "gap": sp.gap, "W": sp.W, "T_pairs": sp.W - sp.L - sp.H - sp.gap + 1, "kappa": kappa_LH(sp.L, sp.H),
                     "bias_b": cal[sp.name]["bias"], "se_mult": cal[sp.name]["se_mult"], "tau_mean": t.mean(), "tau_sd": t.std(),
                     "P(tau>=1.28)": (t >= 1.28).mean(), "P(tau<=-1.28)": (t <= -1.28).mean()})
    pd.DataFrame(rows).to_csv(out / "calibration_check.csv", index=False)
    acc["tau_null_check"] = rows

    # sample vs closed form, one planted state at a time
    rows = []
    for eff in (0.10, 0.15):
        th = solve_states(eff)
        for k, name in enumerate(STATES):
            est = {sp.name: [] for sp in ALL_SPECS}
            for seed in range(max(int(8 * sc), 3)):
                w = generate(WorldSpec(kind="regime", effect=eff, states_used=(k,), mean_dwell=(1e6,) * 4, seed=800_000 + seed))
                rt, _ = standardise(w.ret)
                for sp in ALL_SPECS:
                    st = mr_stat(rt, sp)
                    sign = 1 if sp.kind == "mom" else -1
                    est[sp.name].append(np.nanmean(sign * (st.rho[1500:] - cal[sp.name]["bias"])))
            for sp in ALL_SPECS:
                rows.append({"effect": eff, "state": name, "spec": sp.name, "closed_form": th[name].nets()[sp.name], "sample": float(np.mean(est[sp.name]))})
    cf = pd.DataFrame(rows)
    cf["ratio"] = cf["sample"] / cf["closed_form"].where(cf["closed_form"].abs() > 0.03)
    cf.to_csv(out / "closed_form_vs_sample.csv", index=False)

    # ---------------------------------------------------------------------------------- null controls
    log(f"null controls ({n_null} reps x {len(NULL_KINDS)} worlds)")
    tasks = []
    for kind in NULL_KINDS:
        kw = dict(effect=0.10)
        if kind == "N2b":
            kw["public_burst_per_year"] = 6.0
        tasks += [dict(kind=kind, seed=10_000 * (NULL_KINDS.index(kind) + 1) + i, kw=kw, tag=kind, assoc=True) for i in range(n_null)]
    nulls = pd.DataFrame(run_pool(sim_task, tasks, cal, args.workers))
    nulls.to_csv(out / "null_controls_raw.csv", index=False)
    rows = []
    for kind in NULL_KINDS:
        d = nulls[nulls.tag == kind]
        n = len(d)
        for mn, rn in COMBOS:
            key = f"{mn}|{rn}"
            for rule, col in (("decision (shift p<.05 & boot lo>0)", f"{key}:detect"), ("shift p<.05 only", None), ("naive raw Theta, boot lo>0", f"{key}:detect_naive_raw")):
                k = int((d[f"{key}:p_shift"] < 0.05).sum()) if col is None else int(d[col].sum())
                lo, hi = cp_interval(k, n)
                rows.append({"world": kind, "combo": key, "rule": rule, "n": n, "fpr": k / n, "ci_lo": lo, "ci_hi": hi})
        k = int(d["h5_reject"].sum())
        lo, hi = cp_interval(k, n)
        rows.append({"world": kind, "combo": "H5", "rule": "H5 reject", "n": n, "fpr": k / n, "ci_lo": lo, "ci_hi": hi})
        for c in [c for c in d.columns if c.startswith("assoc:") and c.endswith(":reject")]:
            k = int(d[c].sum())
            lo, hi = cp_interval(k, n)
            rows.append({"world": kind, "combo": c, "rule": "association reject", "n": n, "fpr": k / n, "ci_lo": lo, "ci_hi": hi})
    ns = pd.DataFrame(rows)
    ns.to_csv(out / "null_summary.csv", index=False)
    desc = nulls.groupby("tag")[["I_rate", "F_day_rate", "dM_frac", "dR_frac", "M-B|R-A:mean_s", "M-B|R-A:mean_D", "M-B|R-A:theta_c", "M-B|R-A:theta_raw", "h5_n_events"]].mean()
    desc.to_csv(out / "null_descriptives.csv")

    # ---------------------------------------------------------------------------------- power / recovery
    log("power and recovery")
    tasks = []
    for label, dwell, covol in (("doc-dwell", DOC, False), ("long-dwell", LONG, False), ("doc-dwell+covol", DOC, True)):
        for eff in EFFECTS:
            tasks += [dict(kind="regime", seed=200_000 + 1000 * EFFECTS.index(eff) + i + (50_000 if label != "doc-dwell" else 0) + (90_000 if covol else 0),
                           kw=dict(effect=eff, mean_dwell=dwell, covol=covol), tag=f"{label}|{eff}", combos=True) for i in range(n_pow)]
    pw = pd.DataFrame(run_pool(sim_task, tasks, cal, args.workers))
    pw.to_csv(out / "power_raw.csv", index=False)
    pw[["world", "effect"]] = pw.tag.str.split("|", expand=True)
    keep = ["M-B|R-A:detect", "M-A|R-A:detect", "M-B|R-B-gap:detect", "M-B|R-B:detect", "M-A|R-B-gap:detect", "M-B|R-A:p_shift", "M-B|R-A:theta_c",
            "rec:auc_M", "rec:auc_R", "rec:quad_accuracy", "rec:P(dM=1|I)", "rec:P(dM=1|IV)", "rec:P(dR=1|II)", "rec:P(dR=1|IV)", "rec:P(dM=1|III)", "rec:P(dR=1|III)",
            "rec:tauM|I", "rec:tauM|II", "rec:tauM|III", "rec:tauM|IV", "rec:tauR|I", "rec:tauR|II", "rec:tauR|III", "rec:tauR|IV", "I_rate", "F_day_rate"]
    pws = pw.groupby(["world", "effect"])[keep].mean().reset_index()
    pws["n"] = pw.groupby(["world", "effect"]).size().values
    pws.to_csv(out / "power_summary.csv", index=False)

    # ---------------------------------------------------------------------------------- detection delay
    log("detection delay")
    tasks = []
    for eff in (0.10, 0.15, 0.20):
        tasks += [dict(which="M", seed=300_000 + i + int(eff * 1e3), effect=eff, dwell=400.0) for i in range(n_delay)]
        tasks += [dict(which="R", seed=310_000 + i + int(eff * 1e3), effect=eff, dwell=150.0) for i in range(n_delay)]
        tasks += [dict(which="M", seed=320_000 + i + int(eff * 1e3), effect=eff, dwell=400.0, mom_spec=SPECS["M-B-W70"]) for i in range(n_delay)]
        tasks += [dict(which="R", seed=330_000 + i + int(eff * 1e3), effect=eff, dwell=150.0, rev_spec=SPECS["R-A-W30"]) for i in range(n_delay)]
    dl = run_pool(delay_task, tasks, cal, args.workers)
    rows = []
    df = pd.DataFrame(dl)
    for (which, eff, spec), d in df.groupby(["which", "effect", "spec"]):
        delays = np.concatenate([np.array(x, dtype=float) for x in d["delays"]]) if len(d) else np.array([])
        n_sw = int(d["n_switch"].sum())
        sp = SPECS[spec]
        th = solve_states(eff)
        drho = th["I" if which == "M" else "II"].nets()["M-B" if which == "M" else "R-A"]
        neff = float(d["n_eff"].mean())
        ds = d_star(sp, 1.28, neff, drho)
        rows.append({"crowd": which, "spec": spec, "effect": eff, "n_switch": n_sw, "n_detected": len(delays), "detect_rate": len(delays) / max(n_sw, 1),
                     "median_delay": float(np.median(delays)) if len(delays) else float("nan"), "q25": float(np.quantile(delays, .25)) if len(delays) else float("nan"),
                     "q75": float(np.quantile(delays, .75)) if len(delays) else float("nan"), "n_eff": neff, "d_star_lower_bound": ds["d_star"], "d_window_pred": ds["d_window"],
                     "ratio_median_over_window_pred": (float(np.median(delays)) / ds["d_window"]) if len(delays) else float("nan"), "window_rule_W": ds["window_rule"], "W_used": sp.W})
    pd.DataFrame(rows).to_csv(out / "delay_summary.csv", index=False)

    # ---------------------------------------------------------------------------------- informed events
    log("informed events")
    tasks = []
    for z in (3.0, 4.0, 5.0):
        tasks += [dict(kind="informed", seed=400_000 + int(z * 10) * 1000 + i, kw=dict(effect=0.0, informed_per_year=6.0, informed_z=z), tag=f"informed z={z}", combos=False) for i in range(n_inf)]
    tasks += [dict(kind="N2b", seed=450_000 + i, kw=dict(effect=0.10, public_burst_per_year=6.0), tag="N2b public bursts", combos=False) for i in range(n_inf)]
    inf = pd.DataFrame(run_pool(sim_task, tasks, cal, args.workers))
    inf.to_csv(out / "informed_raw.csv", index=False)
    cols = [c for c in ["inf_events", "inf_hits", "inf_delay_med", "flag_asset_days", "flag_precision", "F_day_rate", "I_rate", "h5_n_events", "h5_diff", "h5_mean_F", "h5_mean_Fc", "h5_reject"] if c in inf.columns]
    inf.groupby("tag")[cols].mean().to_csv(out / "informed_summary.csv")

    # ---------------------------------------------------------------------------------- settlement-price bias (Working 1960)
    log("settlement bias")
    wb = working_bias_check(cal, n_sims=max(int(20 * sc), 4))
    pd.DataFrame([wb]).to_csv(out / "working_bias.csv", index=False)

    (out / "acceptance_inputs.json").write_text(json.dumps({"n_null": n_null, "n_pow": n_pow, "n_delay": n_delay, "n_inf": n_inf}, indent=2))
    log("done")


if __name__ == "__main__":
    main()
