"""Phase 1 synthetic experiment (research doc step 1: backtest field + synthetic data + null control).

    python scripts/run_phase1_synthetic.py [--seed 1] [--n-seeds 20] [--out artifacts/phase1]

Outputs (CSV tables + PNG figures + summary.md) go to --out.
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from regime_quant.config import CostParams, InferenceParams, ProxyParams, StrategyParams
from regime_quant.pipeline import ScenarioResult, benchmark_table, run_scenario
from regime_quant.synthetic import SCENARIOS

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)
STATE_COLORS = {"slow": "#cfe8cf", "rushed": "#f4cccc", "calm": "#e6e6e6"}


def plot_cumulative(res: ScenarioResult, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    cols = ["mom_leg", "rev_leg", "ew_blend", "vol_target_blend", "oracle_true_state"]
    cum = res.benchmarks[cols].fillna(0).cumsum()
    for c in cum:
        ax.plot(cum.index, cum[c], lw=1.1, label=c)
    states, names = res.market.states, res.market.state_names
    change = np.flatnonzero(np.diff(states.to_numpy(), prepend=-1) != 0)
    bounds = list(change) + [len(states)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        ax.axvspan(states.index[a].to_pydatetime(), states.index[b - 1].to_pydatetime(), color=STATE_COLORS[names[states.iloc[a]]], alpha=0.6, lw=0)
    ax.legend(fontsize=8, loc='lower left')
    ax.set_title("Synthetic 'regime' market: cumulative net return (green=slow, red=rushed, grey=calm)")
    ax.set_ylabel("cumulative net return (sum of daily)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_d_by_state(results: dict[str, ScenarioResult], path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for ax, (sc, r) in zip(axes, results.items()):
        t = r.true_state
        ax.bar(t["true_state"], t["mean_D"], color="#4c78a8")
        ax.axhline(0, color="k", lw=0.6)
        ax.set_title(sc)
        ax.tick_params(axis="x", rotation=20)
    axes[0].set_ylabel("mean daily D (net) by TRUE state")
    fig.suptitle("Oracle conditioning on known state: D = mom - rev (risk-standardised)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_d_by_proxy_bin(results: dict[str, ScenarioResult], path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, proxy in zip(axes, ("vr_short", "vr_long")):
        width = 0.27
        for i, (sc, r) in enumerate(results.items()):
            c = r.conditional[r.conditional["proxy"] == proxy]
            ax.bar(np.arange(3) + (i - 1) * width, c["mean_D"], width, label=sc)
        ax.set_xticks(range(3), ["low", "mid", "high"])
        ax.axhline(0, color="k", lw=0.6)
        ax.set_title(f"D by {proxy} tercile (expanding thresholds)")
    axes[0].set_ylabel("mean daily D (net)")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def multi_seed(n_seeds: int, n_days: int, ip: InferenceParams) -> pd.DataFrame:
    rows = []
    for sc in SCENARIOS:
        for seed in range(100, 100 + n_seeds):
            r = run_scenario(sc, seed, n_days=n_days, ip=ip)
            for _, e in r.existence.iterrows():
                rows.append({"scenario": sc, "seed": seed, **e.to_dict()})
    df = pd.DataFrame(rows)
    return (
        df.groupby(["scenario", "proxy"])
        .agg(
            n_seeds=("pass", "size"),
            pass_rate=("pass", "mean"),
            mean_diff=("diff", "mean"),
            mean_seg_high=("seg_high", "mean"),
            mean_seg_low=("seg_low", "mean"),
        )
        .reset_index()
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n-seeds", type=int, default=20)
    ap.add_argument("--n-days", type=int, default=6000)
    ap.add_argument("--out", default="artifacts/phase1")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ip = InferenceParams()

    results = {sc: run_scenario(sc, args.seed, n_days=args.n_days, ip=ip) for sc in SCENARIOS}
    reg = results["regime"]

    bt = benchmark_table(reg, ip, args.seed)
    bt.to_csv(out / "benchmarks_regime.csv", index=False)
    pd.concat(
        [r.true_state.assign(scenario=sc) for sc, r in results.items()], ignore_index=True
    ).to_csv(out / "d_by_true_state.csv", index=False)
    pd.concat(
        [r.conditional.assign(scenario=sc) for sc, r in results.items()], ignore_index=True
    ).to_csv(out / "d_by_proxy_bin.csv", index=False)
    pd.concat(
        [r.existence.assign(scenario=sc) for sc, r in results.items()], ignore_index=True
    ).to_csv(out / "existence_test_single_seed.csv", index=False)
    reg.recovery.to_csv(out / "proxy_recovery_regime.csv", index=False)

    ms = multi_seed(args.n_seeds, args.n_days, ip)
    ms.to_csv(out / "multi_seed_detection.csv", index=False)

    plot_cumulative(reg, out / "cumulative_regime.png")
    plot_d_by_state(results, out / "d_by_true_state.png")
    plot_d_by_proxy_bin(results, out / "d_by_proxy_bin.png")

    def fmt(df: pd.DataFrame) -> str:
        return "```\n" + df.round(3).to_string(index=False) + "\n```"

    lines = [
        "# Phase 1 synthetic run (auto-generated)",
        "",
        f"seed={args.seed}, n_days={args.n_days}, multi-seed n={args.n_seeds}. All parameters are DRAFT (see README, TO_LOCK).",
        "Synthetic data only: nothing here says anything about real markets.",
        "",
        "## Benchmarks, 'regime' scenario (net of draft costs; Sharpe with 95% block-bootstrap CI)",
        fmt(bt),
        "",
        "## D = mom - rev (risk-standardised) by TRUE state (oracle conditioning, possible only on synthetic)",
        fmt(pd.concat([r.true_state.assign(scenario=sc) for sc, r in results.items()], ignore_index=True)),
        "",
        "## Existence test on observable proxies, single seed (draft rule: CI lower bound > 0 and >=5 segments per extreme bin)",
        fmt(pd.concat([r.existence.assign(scenario=sc) for sc, r in results.items()], ignore_index=True)),
        "",
        "## Recovery of known states by observable proxies (AUC; 0.5 = chance)",
        fmt(reg.recovery),
        "",
        f"## Multi-seed detection rate ({args.n_seeds} seeds per scenario; trials per run = 2 proxies, 1 parameter set)",
        "regime row = detection rate (C3 method works); null rows = false-positive rate (hallucination).",
        fmt(ms),
        "",
        "Figures: cumulative_regime.png, d_by_true_state.png, d_by_proxy_bin.png",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
