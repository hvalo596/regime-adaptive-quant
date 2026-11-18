"""DRAFT implementation of the four "Kai dimensions" (system level / system share / idiosyncratic level /
idiosyncratic concentration) on a futures panel.

STATUS: DRAFT. Kai's own definitions have not been seen (the WeChat screenshot gives names and intent, not formulas).
Everything below is the working draft from docs/kai-dims-and-experiment-steps.md section A and must be replaced
or confirmed before any result built on it is called final. Nothing here is Kai's formula.

Draft decomposition on a rolling window of `window` days (all point-in-time: row t uses returns through t):
    r_i = beta_i * f + e_i,   f = cross-sectional mean of the live assets' returns that day (equal-weight basket)
    S = mean_i( beta_i^2 * var(f) )          common-factor variance, averaged over assets
    I = mean_i( var(e_i) ),  var(e_i) = var(r_i) - cov(r_i, f)^2 / var(f)     (OLS identity, no residual series needed)
    1) sys_level  = 0.5 * log S                      systematic risk level
    2) sys_share  = S / (S + I)                      share of variance that is common (~ average R^2)
    3) idio_level = 0.5 * log I                      idiosyncratic risk level
    4) idio_conc  = (HHI - 1/N) / (1 - 1/N),  HHI = sum_i s_i^2,  s_i = var(e_i) / sum_j var(e_j)
                    normalised so that 0 = perfectly even across the N live assets, 1 = all in one asset
                    (the raw HHI floor 1/N is high for a narrow futures cross-section, hence the normalisation)

Known issue, kept visible: logit(sys_share) = log(S/I) = 2 * (sys_level - idio_level) EXACTLY, so these three carry
only two degrees of freedom. `dependence_report` states this and reports the sample correlation matrix and VIFs, so the
three are never fed to a model as three independent features. The factor (equal-weight mean) also needs
confirmation: a single basket factor over a multi-sector commodity panel is a strong simplification (decision D1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DRAFT = True
DIM_NAMES = ("sys_level", "sys_share", "idio_level", "idio_conc")


def kai_dims(returns: pd.DataFrame, window: int = 60, min_assets: int = 5) -> pd.DataFrame:
    """Rolling draft dimensions. Assets need a full window of returns to count on a given day."""
    r = returns
    f = r.mean(axis=1, skipna=True)
    var_f = f.rolling(window, min_periods=window).var()
    var_i = r.rolling(window, min_periods=window).var()
    cov_if = r.apply(lambda col: col.rolling(window, min_periods=window).cov(f))
    beta = cov_if.div(var_f, axis=0)
    resid_var = (var_i - cov_if.pow(2).div(var_f, axis=0)).clip(lower=0.0)
    live = var_i.notna() & resid_var.notna()
    n = live.sum(axis=1)

    S = (beta.pow(2).where(live).mul(var_f, axis=0)).mean(axis=1)
    I = resid_var.where(live).mean(axis=1)
    shares = resid_var.where(live).div(resid_var.where(live).sum(axis=1), axis=0)
    hhi = shares.pow(2).sum(axis=1, min_count=1)
    conc = (hhi - 1.0 / n) / (1.0 - 1.0 / n)

    out = pd.DataFrame(
        {
            "sys_level": 0.5 * np.log(S.where(S > 0)),
            "sys_share": S / (S + I),
            "idio_level": 0.5 * np.log(I.where(I > 0)),
            "idio_conc": conc.where(n >= 2),
            "n_assets": n.astype(float),
        }
    )
    ok = n >= min_assets
    out.loc[~ok, list(DIM_NAMES)] = np.nan
    return out


def dependence_report(dims: pd.DataFrame) -> dict:
    """Sample correlation matrix, VIFs, and the exact identity residual for logit(share) vs the two levels."""
    d = dims[list(DIM_NAMES)].dropna()
    corr = d.corr()
    inv = np.linalg.pinv(corr.to_numpy())
    vif = pd.Series(np.diag(inv), index=corr.index, name="vif")
    share = d["sys_share"].clip(1e-9, 1 - 1e-9)
    ident = np.log(share / (1 - share)) - 2.0 * (d["sys_level"] - d["idio_level"])
    return {
        "n_obs": len(d),
        "corr": corr,
        "vif": vif,
        "max_abs_identity_residual": float(ident.abs().max()) if len(d) else float("nan"),
    }
