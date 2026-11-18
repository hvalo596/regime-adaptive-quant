"""Pre-registered 24-variant momentum/reversal grid on the commodity panel (see regime_quant/param_grid.py)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.data.panel import PanelParams, build_panel  # noqa: E402
from regime_quant.data.roll import RollParams  # noqa: E402
from regime_quant.data.store import RawStore  # noqa: E402
from regime_quant.data.universe import commodity_products  # noqa: E402
from regime_quant.param_grid import reality_check, run_grid, variant_intervals  # noqa: E402
from regime_quant.phase2 import load_raw  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out", default="artifacts/phase2_param_grid")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    store = RawStore(a.raw_dir)
    avail = set(store.basic()["fut_code"].unique())
    comm = [p for p in commodity_products() if p in avail]
    basic, daily, maps = load_raw(store, comm)
    panel = build_panel(comm, basic, daily, maps, RollParams(), PanelParams())
    summ, g, n = run_grid(panel.returns, panel.roll)
    summ = summ.merge(variant_intervals(g), on="variant")
    fam = {f: list(summ.loc[summ["family"] == f, "variant"]) for f in ("rev", "mom")}
    rc = reality_check(g, fam)
    summ.to_csv(out / "grid_summary.csv", index=False)
    rc.to_csv(out / "reality_check.csv", index=False)
    summ[["variant", "family", "lookback", "hold"]].assign(counted=True).to_csv(out / "trials_param_grid.csv", index=False)
    # Exploratory follow-up allowed by the pre-registration: variants that pass the reality check go to the state test.
    # Pair the best momentum variant with the draft reversal leg (no reversal variant has an edge). 6 extra trials.
    import numpy as np
    import pandas as pd

    from regime_quant.config import CostParams, InferenceParams, ProxyParams, StrategyParams
    from regime_quant.existence import ExistenceParams, compute_d, compute_proxies, existence_row

    best_mom = rc.loc[rc["family"] == "mom", "best_variant"].iloc[0]
    _, lb, h = best_mom.split("_")
    sp = StrategyParams(mom_lookback=int(lb), mom_hold=int(h))
    ep, ip, pp = ExistenceParams(n_boot=1000, n_shift=2000), InferenceParams(), ProxyParams()
    prox = compute_proxies(panel.returns, pp, ep)
    rows = []
    for scen, cp in (("net_draft", CostParams()), ("gross", CostParams(fee_bps=0.0, slip_vol_frac=0.0))):
        d, _, _ = compute_d(panel.returns, sp, cp, panel.roll if scen == "net_draft" else None)
        for k, c in enumerate(prox.columns):
            r = existence_row(c, prox[c], d, ip, ep, pp, 6, np.random.default_rng(ep.seed + k))
            rows.append({"mom_variant": best_mom, "rev_variant": "rev_5_3", "cost": scen,
                         **{x: r.get(x, np.nan) for x in ["proxy", "expected_sign", "n_days", "diff", "ci_adj_lo", "ci_adj_hi", "seg_high", "seg_low", "shift_p_two_sided", "verdict"]}})
    pd.DataFrame(rows).to_csv(out / "state_test_best_mom.csv", index=False)
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print(rc.round(3).to_string(index=False))
    print(summ[["variant", "gross_sharpe", "gross_sharpe_lo", "gross_sharpe_hi", "net_sharpe", "turnover_per_day"]].round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
