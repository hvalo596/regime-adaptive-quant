"""One-off null calibration of the state-variable tests (doc 3.3: "simulate once, then fix").

For each strategy-matched statistic rho^(L,H) (spec, window W) we measure on stateless worlds
  bias   b      = mean of rho_hat                       (window demeaning of overlapping sums gives ~ -sqrt(L*H)/T)
  se_mult c_se  = sqrt(mean(((rho_hat - b)/se_formula)^2))   (fat tails + vol clustering inflate the Isserlis se)
The same constants are then used everywhere (synthetic evaluation, real data). They are NOT re-fitted per world.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from .config import LegSpec, MOM_MAIN, MOM_SECOND, REV_MAIN, REV_SECOND, REV_SECOND_GAP
from .statevars import mean_sq_corr, mr_stat, standardise
from .world import WorldSpec, generate

ALL_SPECS = (MOM_MAIN, MOM_SECOND, REV_MAIN, REV_SECOND, REV_SECOND_GAP)


def calibrate(specs=ALL_SPECS, n_sims: int = 30, seed0: int = 90_000, n_days: int = 2500, n_assets: int = 40, mask: np.ndarray | None = None, kind: str = "N0z") -> dict:
    """`mask` (T, N) bool optional availability pattern (True = live) so the calibration can mimic a real unbalanced panel."""
    rho = {sp.name: [] for sp in specs}
    se = {sp.name: [] for sp in specs}
    for k in range(n_sims):
        w = generate(WorldSpec(kind=kind, n_days=n_days, n_assets=n_assets, seed=seed0 + k))
        r = w.ret.copy()
        if mask is not None:
            r = np.where(mask[: len(r), : r.shape[1]], r, np.nan)
        rt, _ = standardise(r)
        r2, nf = mean_sq_corr(rt)
        for sp in specs:
            st = mr_stat(rt, sp, r2, nf)
            ok = np.isfinite(st.rho) & np.isfinite(st.se_formula)
            rho[sp.name].append(st.rho[ok])
            se[sp.name].append(st.se_formula[ok])
    out = {}
    for sp in specs:
        x, s = np.concatenate(rho[sp.name]), np.concatenate(se[sp.name])
        b = float(x.mean())
        out[sp.name] = {"bias": b, "se_mult": float(np.sqrt(np.mean(((x - b) / s) ** 2))), "sd_rho": float(x.std()), "mean_se": float(s.mean()), "n": int(len(x))}
    return out


def save(cal: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cal, indent=2))


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def calibrate_c_null(n_grid=(8, 12, 16, 20, 25, 30, 35, 40, 45), n_sims: int = 16, seed0: int = 95_000, level: float = 0.95, n_days: int = 2500, kind: str = "N0z") -> dict:
    """Pipeline-level null of C: the `level` quantile of C_t over stateless worlds with N assets (vol clustering and
    cross-correlation included). Keys are N as strings so the table survives JSON."""
    from .config import StateParams
    from .statevars import concentration, loo_factor_regress

    out = {}
    for n in n_grid:
        vals = []
        for k in range(n_sims):
            w = generate(WorldSpec(kind=kind, n_days=n_days, n_assets=int(n), seed=seed0 + 31 * int(n) + k))
            rt, _ = standardise(w.ret)
            fit = loo_factor_regress(rt)
            conc = concentration(fit.resid, StateParams())
            c = conc.C[~np.isnan(conc.C)]
            vals.append(c)
        out[str(int(n))] = float(np.quantile(np.concatenate(vals), level))
    return out
