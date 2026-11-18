"""Phase 2 sensitivity: cost grid + leg decomposition, sector panels, stock-index / treasury controls.

    python scripts/run_phase2_sensitivity.py --raw-dir data/raw --out artifacts/phase2_sensitivity
Needs raw data for the commodity universe (fetch_tushare_futures.py --group commodity) and, for part C,
IF,IH,IC,IM,TS,TF,T,TL. Missing products are skipped and listed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regime_quant.config import CostParams, InferenceParams, ProxyParams, StrategyParams  # noqa: E402
from regime_quant.data.panel import PanelParams, build_panel, subset_panel  # noqa: E402
from regime_quant.data.roll import RollParams  # noqa: E402
from regime_quant.data.store import RawStore  # noqa: E402
from regime_quant.data.universe import PRODUCTS, commodity_products  # noqa: E402
from regime_quant.existence import ExistenceParams  # noqa: E402
from regime_quant.phase2 import analyze_panel, load_raw  # noqa: E402
from regime_quant.sensitivity import cost_sensitivity, sector_products, single_product_tests  # noqa: E402

INDEX, BOND = ["IF", "IH", "IC", "IM"], ["TS", "TF", "T", "TL"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out", default="artifacts/phase2_sensitivity")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--n-null", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    store = RawStore(a.raw_dir)
    sp, cp, pp, ip = StrategyParams(), CostParams(), ProxyParams(), InferenceParams()
    ep = ExistenceParams(n_boot=a.n_boot, n_shift=1000, seed=a.seed)
    log = []

    avail = set(store.basic()["fut_code"].unique())
    comm = [p for p in commodity_products() if p in avail]
    basic, daily, maps = load_raw(store, comm)
    panel = build_panel(comm, basic, daily, maps, RollParams(), PanelParams())
    print(f"commodity panel: {panel.returns.shape[1]} products")

    # A. costs
    ex, legs, dec = cost_sensitivity(panel, sp, pp, ip, ep)
    ex.to_csv(out / "cost_existence.csv", index=False)
    legs.to_csv(out / "cost_legs.csv", index=False)
    dec.to_csv(out / "leg_decomposition_zero_cost.csv", index=False)
    print("A done")

    # B. sectors (family = 6 proxies x number of sectors)
    secs = sector_products(panel, 5)
    n_fam = 6 * len(secs)
    sec_rows = []
    for sec, ps in secs.items():
        sub = subset_panel(panel, ps)
        r = analyze_panel(sub, source="tushare", ep=ep, n_null=a.n_null, n_primary_override=n_fam, progress=lambda *_: None)
        t = r.primary.copy()
        t.insert(0, "sector", sec)
        t.insert(1, "n_products", len(ps))
        nulls = r.null_panel[["proxy", "p_two_sided", "p_familywise_maxz"]].rename(
            columns={"p_two_sided": "pipeline_p", "p_familywise_maxz": "pipeline_fw_p"}) if len(r.null_panel) else None
        if nulls is not None:
            t = t.merge(nulls, on="proxy", how="left")
        sec_rows.append(t)
        log.append(f"sector {sec}: {ps}")
    pd.concat(sec_rows).to_csv(out / "sector_existence.csv", index=False)
    print("B done")

    # C. index / bond controls
    ib = [p for p in INDEX + BOND if p in avail]
    if ib:
        b2, d2, m2 = load_raw(store, ib)
        pan_ib = build_panel(ib, b2, d2, m2, RollParams(), PanelParams())
        groups = {p: subset_panel(pan_ib, [p]) for p in ib if p in pan_ib.returns.columns}
        pool_idx = [p for p in ["IF", "IH", "IC"] if p in groups]
        pool_bond = [p for p in ["TS", "TF", "T"] if p in groups]
        if len(pool_idx) >= 2:
            groups["IF+IH+IC"] = subset_panel(pan_ib, pool_idx)
        if len(pool_bond) >= 2:
            groups["TS+TF+T"] = subset_panel(pan_ib, pool_bond)
        n_fam_c = 2 * len(groups)
        t = single_product_tests(groups, sp, cp, pp, ip, ep, n_fam_c, restricted_exclusion=("2015-09-07", "2017-02-17"))
        t.to_csv(out / "index_bond_existence.csv", index=False)
        pan_ib.diagnostics.to_csv(out / "index_bond_roll_quality.csv", index=False)
        log.append(f"index/bond groups: {list(groups)}")
        print("C done")
    (out / "run_log.txt").write_text("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
