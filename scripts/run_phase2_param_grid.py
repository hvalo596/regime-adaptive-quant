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
    print(rc.round(3).to_string(index=False))
    print(summ[["variant", "gross_sharpe", "gross_sharpe_lo", "gross_sharpe_hi", "net_sharpe", "turnover_per_day"]].round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
