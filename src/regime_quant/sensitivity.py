"""Phase 2 follow-ups that do NOT add model complexity:
  A. cost sensitivity: does the (null) state effect on D change when costs are removed/scaled? Also the D decomposition
     into its two legs, so a cost-eaten reversal leg cannot hide a state effect silently.
  B. sector-wise panels (commodity sectors with >= 5 products): the cross-section Kai's dimensions were designed for.
  C. single-product / pooled controls for stock-index and treasury futures (VR proxies only: the four dims need a wide
     cross-section), including the 2015-09 restriction-period exclusion for stock index.
All of these are sensitivity analyses of the pre-registered step-2 test. They are reported with their own multiple-testing
denominators and never replace the primary result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .benchmarks import risk_standardise
from .config import CostParams, InferenceParams, ProxyParams, StrategyParams
from .data.panel import Panel
from .data.universe import PRODUCTS
from .diagnostics import state_proxies
from .existence import ExistenceParams, compute_d, compute_proxies, existence_row

COST_GRID = {
    "zero": dict(fee_bps=0.0, slip_vol_frac=0.0, roll=False),
    "half": dict(fee_bps=0.5, slip_vol_frac=0.025, roll=True),
    "draft": dict(fee_bps=1.0, slip_vol_frac=0.05, roll=True),
    "double": dict(fee_bps=2.0, slip_vol_frac=0.10, roll=True),
}


def _row(proxy_name, proxy, series, ip, ep, pp, n_primary, seed):
    r = existence_row(proxy_name, proxy, series, ip, ep, pp, n_primary, np.random.default_rng(seed))
    keep = ["proxy", "expected_sign", "n_days", "diff", "ci_lo", "ci_hi", "ci_adj_lo", "ci_adj_hi", "seg_high", "seg_low",
            "shift_p_two_sided", "verdict"]
    return {k: r.get(k, np.nan) for k in keep}


def cost_sensitivity(
    panel: Panel, sp: StrategyParams, pp: ProxyParams, ip: InferenceParams, ep: ExistenceParams, n_primary: int = 6
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (existence by cost scenario, leg Sharpe by scenario, leg decomposition at zero cost)."""
    ret = panel.returns
    prox = compute_proxies(ret, pp, ep)
    rows, legs_rows = [], []
    for name, g in COST_GRID.items():
        cp = CostParams(fee_bps=g["fee_bps"], slip_vol_frac=g["slip_vol_frac"])
        d, _, legs = compute_d(ret, sp, cp, panel.roll if g["roll"] else None)
        for k, c in enumerate(prox.columns):
            rows.append({"scenario": name, **_row(c, prox[c], d, ip, ep, pp, n_primary, ep.seed + k)})
        for leg in ("mom", "rev"):
            x = legs[leg].net.dropna()
            legs_rows.append({"scenario": name, "leg": leg, "ann_ret": x.mean() * 252, "ann_vol": x.std() * np.sqrt(252),
                              "sharpe": x.mean() / x.std() * np.sqrt(252), "turnover_per_day": legs[leg].turnover.mean()})
    # leg decomposition at zero cost: does either leg alone vary with the state?
    _, _, legs0 = compute_d(ret, sp, CostParams(fee_bps=0.0, slip_vol_frac=0.0), None)
    z = {leg: risk_standardise(legs0[leg].gross, sp.vol_window) for leg in ("mom", "rev")}
    dec = []
    for leg, s in z.items():
        for k, c in enumerate(prox.columns):
            r = _row(c, prox[c], s, ip, ep, pp, n_primary, ep.seed + 50 + k)
            dec.append({"leg": f"z_{leg}_gross", **r})
    return pd.DataFrame(rows), pd.DataFrame(legs_rows), pd.DataFrame(dec)


def sector_products(panel: Panel, min_assets: int = 5) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in panel.returns.columns:
        sec = PRODUCTS.get(p, ("", "other"))[1]
        out.setdefault(sec, []).append(p)
    return {s: ps for s, ps in out.items() if len(ps) >= min_assets}


def single_product_tests(
    panels: dict[str, Panel], sp: StrategyParams, cp: CostParams, pp: ProxyParams, ip: InferenceParams,
    ep: ExistenceParams, n_primary: int, restricted_exclusion: tuple[str, str] | None = None,
) -> pd.DataFrame:
    """VR proxies on each panel (single product or pooled group). `restricted_exclusion` drops evaluation days inside
    the (draft, unverified) stock-index restriction window as a sensitivity variant."""
    rows = []
    for name, pan in panels.items():
        ret = pan.returns
        d, _, _ = compute_d(ret, sp, cp, pan.roll)
        prox = state_proxies(ret, pp, min_assets=1)
        variants = {"full": None}
        if restricted_exclusion and PRODUCTS.get(name.split("+")[0], ("", ""))[1] == "index":
            a, b = (pd.Timestamp(x) for x in restricted_exclusion)
            variants["excl_restricted"] = pd.Series((d.index >= a) & (d.index < b), index=d.index)
        for vname, excl in variants.items():
            for k, c in enumerate(prox.columns):
                r = existence_row(c, prox[c], d, ip, ep, pp, n_primary, np.random.default_rng(ep.seed + k), exclude=excl)
                rows.append({"group": name, "variant": vname, "n_assets": ret.shape[1],
                             "first": str(ret.dropna(how="all").index[0].date()), **{k2: r.get(k2, np.nan) for k2 in
                             ["proxy", "expected_sign", "n_days", "diff", "ci_lo", "ci_hi", "ci_adj_lo", "ci_adj_hi",
                              "seg_high", "seg_low", "shift_p_two_sided", "verdict"]}})
    return pd.DataFrame(rows)
