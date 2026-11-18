"""Small strategy-parameter grid to ask ONE question: does any momentum / reversal variant show a gross edge on the
Chinese commodity panel? Not a tuning exercise.

PRE-REGISTRATION (committed before any result was computed):
  * Reversal: lookback in {1, 2, 5, 10} days x hold in {1, 3, 5} days  -> 12 variants (family "rev")
  * Momentum: lookback in {20, 60, 120, 250} days x hold in {5, 20, 60} days -> 12 variants (family "mom")
  * Everything else fixed at the draft values (vol window 60, 10% target vol per asset, same panel, same roll handling).
  * Metric: GROSS annualised Sharpe of the leg, all variants evaluated on the common sample (the latest first-valid date).
  * Inference: White-style reality check for the best Sharpe in each family and across all 24: stationary block bootstrap
    (mean block 20) with the SAME resampled dates for every variant, each variant demeaned. A variant counts as an edge
    only if its family-wise reality-check p < 0.05. Per-variant intervals are reported but are not the decision.
  * Trial ledger: all 24 variants are recorded whether or not they look good. Negative edges (e.g. short-horizon
    continuation) are reported with the same test in the other tail but are not a hypothesis of this study.
  * No variant that fails the reality check is carried into the state test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import build_legs
from .config import CostParams, StrategyParams
from .inference import stationary_bootstrap_indices

REV_GRID = [(lb, h) for lb in (1, 2, 5, 10) for h in (1, 3, 5)]
MOM_GRID = [(lb, h) for lb in (20, 60, 120, 250) for h in (5, 20, 60)]


def _variant_legs(returns: pd.DataFrame, family: str, lb: int, hold: int, cost: CostParams, roll_mask):
    if family == "rev":
        sp = StrategyParams(rev_lookback=lb, rev_hold=hold)
    else:
        sp = StrategyParams(mom_lookback=lb, mom_hold=hold)
    legs = build_legs(returns, sp, cost, roll_mask, nan_when_flat=True)
    return legs[family]


def run_grid(returns: pd.DataFrame, roll_mask=None, net_cost: CostParams = CostParams()) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (summary, gross daily series, net daily series), series aligned on the common sample."""
    gross, net, meta = {}, {}, []
    for family, grid in (("rev", REV_GRID), ("mom", MOM_GRID)):
        for lb, h in grid:
            leg0 = _variant_legs(returns, family, lb, h, CostParams(fee_bps=0.0, slip_vol_frac=0.0), None)
            leg1 = _variant_legs(returns, family, lb, h, net_cost, roll_mask)
            key = f"{family}_{lb}_{h}"
            gross[key], net[key] = leg0.gross, leg1.net
            meta.append({"variant": key, "family": family, "lookback": lb, "hold": h,
                         "turnover_per_day": float(leg1.turnover.mean())})
    g, n = pd.DataFrame(gross), pd.DataFrame(net)
    start = max(g[c].first_valid_index() for c in g)
    g, n = g.loc[start:], n.loc[start:]
    ok = g.notna().all(axis=1)
    g, n = g[ok], n[ok]
    ann = np.sqrt(252)
    summ = pd.DataFrame(meta).set_index("variant")
    summ["gross_sharpe"] = g.mean() / g.std() * ann
    summ["net_sharpe"] = n.mean() / n.std() * ann
    summ["gross_ann_ret"] = g.mean() * 252
    summ["n_days"] = len(g)
    summ["common_start"] = str(g.index[0].date())
    return summ.reset_index(), g, n


def reality_check(gross: pd.DataFrame, families: dict[str, list[str]], n_boot: int = 2000, mean_block: int = 20, seed: int = 11) -> pd.DataFrame:
    """White reality check on the max (and min) Sharpe per family: bootstrap dates jointly, demean each variant."""
    x = gross.to_numpy()
    n = len(x)
    ann = np.sqrt(252)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, mean_block, n_boot, rng)
    mu, sd = x.mean(0), x.std(0, ddof=1)
    obs = mu / sd * ann
    xb = x[idx]  # (n_boot, n, k)
    mub, sdb = xb.mean(1), xb.std(1, ddof=1)
    null = (mub - mu) / sdb * ann  # centred bootstrap distribution of each variant's Sharpe
    rows = []
    cols = list(gross.columns)
    for fam, names in {**families, "all": cols}.items():
        j = [cols.index(c) for c in names]
        best, worst = j[int(np.argmax(obs[j]))], j[int(np.argmin(obs[j]))]
        p_max = float((1 + (null[:, j].max(1) >= obs[best]).sum()) / (1 + n_boot))
        p_min = float((1 + (null[:, j].min(1) <= obs[worst]).sum()) / (1 + n_boot))
        rows.append({"family": fam, "n_variants": len(j), "best_variant": cols[best], "best_gross_sharpe": float(obs[best]),
                     "rc_p_best_positive": p_max, "worst_variant": cols[worst], "worst_gross_sharpe": float(obs[worst]),
                     "rc_p_worst_negative": p_min})
    return pd.DataFrame(rows)


def variant_intervals(gross: pd.DataFrame, n_boot: int = 1000, mean_block: int = 20, seed: int = 13) -> pd.DataFrame:
    x = gross.to_numpy()
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(len(x), mean_block, n_boot, rng)
    xb = x[idx]
    sh = xb.mean(1) / xb.std(1, ddof=1) * np.sqrt(252)
    lo, hi = np.quantile(sh, [0.025, 0.975], axis=0)
    return pd.DataFrame({"variant": gross.columns, "gross_sharpe_lo": lo, "gross_sharpe_hi": hi})
