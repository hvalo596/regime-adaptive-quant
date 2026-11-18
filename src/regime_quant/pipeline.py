"""One end-to-end synthetic run for a scenario: market -> legs -> D -> proxies -> tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import LegResult, build_legs
from .benchmarks import benchmark_returns, oracle_allocation, spread_d
from .config import CostParams, InferenceParams, ProxyParams, StrategyParams
from .diagnostics import (
    conditional_table,
    align_next_day,
    existence_test,
    expanding_tercile_bins,
    state_proxies,
    state_recovery,
    true_state_table,
)
from .inference import performance_summary
from .synthetic import SyntheticMarket, generate


@dataclass
class ScenarioResult:
    market: SyntheticMarket
    legs: dict[str, LegResult]
    d_net: pd.Series
    d_gross: pd.Series
    benchmarks: pd.DataFrame
    proxies: pd.DataFrame
    bins: dict[str, pd.Series]
    existence: pd.DataFrame
    conditional: pd.DataFrame
    true_state: pd.DataFrame
    recovery: pd.DataFrame


def run_scenario(
    scenario: str,
    seed: int,
    n_days: int = 6000,
    n_assets: int = 8,
    sp: StrategyParams = StrategyParams(),
    cp: CostParams = CostParams(),
    pp: ProxyParams = ProxyParams(),
    ip: InferenceParams = InferenceParams(),
) -> ScenarioResult:
    market = generate(scenario, n_days=n_days, n_assets=n_assets, seed=seed)
    legs = build_legs(market.returns, sp, cp)
    d_net = spread_d(legs, sp, net=True)
    d_gross = spread_d(legs, sp, net=False)
    bench = benchmark_returns(market.returns, legs, sp)
    if scenario == "regime":
        bench["oracle_true_state"] = oracle_allocation(legs, market)
    proxies = state_proxies(market.returns, pp)
    bins = {c: expanding_tercile_bins(proxies[c], pp.bin_min_obs) for c in proxies}
    rng = np.random.default_rng(10_000 + seed)
    existence = pd.DataFrame([existence_test(bins[c], d_net, rng, ip, c) for c in proxies])
    conditional = pd.concat(
        [conditional_table(align_next_day(bins[c], d_net), c, ip) for c in proxies], ignore_index=True
    )
    return ScenarioResult(
        market=market,
        legs=legs,
        d_net=d_net,
        d_gross=d_gross,
        benchmarks=bench,
        proxies=proxies,
        bins=bins,
        existence=existence,
        conditional=conditional,
        true_state=true_state_table(d_net, market.states, market.state_names),
        recovery=state_recovery(proxies, market.states, market.state_names),
    )


def benchmark_table(res: ScenarioResult, ip: InferenceParams, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(20_000 + seed)
    rows = []
    for name, series in res.benchmarks.items():
        s = performance_summary(series.dropna(), rng, ip.n_boot, ip.mean_block, ip.ci_level)
        rows.append({"strategy": name, **s})
    for name in ("mom", "rev"):
        leg = res.legs[name]
        rows.append(
            {
                "strategy": f"{name}_turnover_per_day",
                "ann_ret": float(leg.turnover.mean()),
            }
        )
    return pd.DataFrame(rows)
