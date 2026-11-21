"""Alternative explanations of doc section 6 as far as the data allow: settlement-price averaging (Working 1960), limit-locked
days, bid-ask bounce (Roll 1984), time-varying risk premium (carry, undemeaned M), pure volatility (H8 lives in step2.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import InferenceParams, MOM_MAIN, REV_MAIN
from .inference import theta_test
from .pipeline import StateRun, run_state_pipeline
from .statevars import tau_stat


def settle_returns(panel, columns=None) -> pd.DataFrame:
    """Same-contract settle-to-settle return of the held contract: settle_t / pre_settle_t - 1 (pre_settle is the previous
    settlement of the same contract). Aligned with panel.returns (same eligibility mask)."""
    cols = list(columns or panel.returns.columns)
    out = {}
    for p in cols:
        c = panel.continuous[p]
        s = c["h_settle"] / c["h_pre_settle"] - 1.0
        out[p] = s.reindex(panel.returns.index)
    df = pd.DataFrame(out)
    df[panel.returns[cols].isna()] = np.nan
    return df


def compare_runs(a: StateRun, b: StateRun, ip: InferenceParams, rng: np.random.Generator) -> dict:
    v = a.valid & b.valid
    agree = float(np.mean(np.array(a.quad, dtype=object)[v] == np.array(b.quad, dtype=object)[v])) if v.any() else float("nan")
    ok = v & np.isfinite(a.tau_m) & np.isfinite(b.tau_m) & np.isfinite(a.tau_r) & np.isfinite(b.tau_r)
    th = theta_test(b.s, b.D_next, ip, rng)
    return {"label_agreement": agree, "corr_tauM": float(np.corrcoef(a.tau_m[ok], b.tau_m[ok])[0, 1]) if ok.sum() > 10 else np.nan,
            "corr_tauR": float(np.corrcoef(a.tau_r[ok], b.tau_r[ok])[0, 1]) if ok.sum() > 10 else np.nan, "theta_c_alt": th.theta_c, "p_shift_alt": th.p_shift, "detect_alt": th.detect,
            "mean_rho_M_alt": float(np.nanmean(b.mr_m.rho)), "mean_rho_M_main": float(np.nanmean(a.mr_m.rho)), "mean_rho_Rgap_or_R_alt": float(np.nanmean(-b.mr_r.rho)), "mean_R_main": float(np.nanmean(-a.mr_r.rho))}


def settle_channel(panel, ret_close: np.ndarray, cal: dict, main_run: StateRun, ip: InferenceParams, rng: np.random.Generator) -> dict:
    sr = settle_returns(panel).to_numpy(dtype=float)
    alt = run_state_pipeline(sr, cal, MOM_MAIN, REV_MAIN, with_portfolio=False)
    out = compare_runs(main_run, alt, ip, rng)
    out["channel"] = "settle-price returns instead of close (Working 1960: tau_R should fall, tau_M rise)"
    return out


def locked_channel(panel, ret_close: np.ndarray, cal: dict, main_run: StateRun, ip: InferenceParams, rng: np.random.Generator, min_assets: int = 5) -> dict:
    lock = (panel.limit_locked | panel.one_price).to_numpy()
    cells = lock | np.vstack([np.zeros((1, lock.shape[1]), bool), lock[:-1]])  # the day itself and the next
    alt = run_state_pipeline(ret_close, cal, MOM_MAIN, REV_MAIN, with_portfolio=False, exclude_cells=cells, min_pair_frac=0.7, min_assets=min_assets)
    drop = lock.any(axis=1) | np.r_[lock.any(axis=1)[1:], False] | np.r_[False, lock.any(axis=1)[:-1]]
    s = np.where(drop, np.nan, alt.s)
    D = np.where(drop, np.nan, alt.D_next)
    th = theta_test(s, D, ip, rng)
    out = compare_runs(main_run, alt, ip, rng)
    out.update({"theta_c_alt": th.theta_c, "p_shift_alt": th.p_shift, "detect_alt": th.detect, "n_locked_cells": int(lock.sum()), "n_days_dropped": int(drop.sum()),
                "channel": "drop limit-locked / one-price asset-days (and next day) from the state variables; drop days within +-1 of a lock from Theta"})
    return out


def roll_spread(ret: pd.DataFrame) -> pd.DataFrame:
    """Roll (1984) implied spread per product from the first-order autocovariance of RAW daily close returns:
    gamma_1 = Cov(r_t, r_{t-1}); spread = 2 sqrt(-gamma_1) if gamma_1 < 0. Reported in basis points and in units of the
    product's median |return|. A spread far above one tick cannot be a bounce; no tick table is used here (data not available)."""
    rows = []
    for p in ret.columns:
        r = ret[p].dropna()
        if len(r) < 250:
            continue
        a, b = r.to_numpy()[1:], r.to_numpy()[:-1]
        g1 = float(np.mean((a - a.mean()) * (b - b.mean())))
        se = float(np.std(a) * np.std(b) / np.sqrt(len(a)))
        sp = 2 * np.sqrt(-g1) if g1 < 0 else 0.0
        rows.append({"product": p, "n": len(r), "gamma1": g1, "gamma1_t": g1 / se if se > 0 else np.nan, "roll_spread_bp": sp * 1e4, "median_abs_ret_bp": float(np.median(np.abs(r)) * 1e4),
                     "spread_over_median_abs_ret": sp / float(np.median(np.abs(r))) if np.median(np.abs(r)) > 0 else np.nan})
    return pd.DataFrame(rows)


def risk_premium_channel(run: StateRun, carry: pd.DataFrame | None, index: pd.DatetimeIndex, ip: InferenceParams, rng: np.random.Generator) -> pd.DataFrame:
    """H0 with carry as a control, and the undemeaned-minus-demeaned M (drift component) as an extra predictor.
    The coefficient on s should survive; (M_raw - M) should not carry the state effect."""
    from .step2 import ols_boot

    D = run.D_next
    cols = [np.ones(len(D)), run.s]
    names = ["const", "s"]
    if carry is not None:
        c = carry.reindex(index).mean(axis=1).to_numpy()
        cm = pd.Series(c).rolling(750, min_periods=250).mean().shift(1).to_numpy()
        cs = pd.Series(c).rolling(750, min_periods=250).std().shift(1).to_numpy()
        cols.append((c - cm) / cs)
        names.append("z_carry")
    if run.mr_m.rho_raw is not None:
        drift = run.mr_m.rho_raw - run.mr_m.rho
        dm = pd.Series(drift).rolling(750, min_periods=250).mean().shift(1).to_numpy()
        ds = pd.Series(drift).rolling(750, min_periods=250).std().shift(1).to_numpy()
        cols.append((drift - dm) / ds)
        names.append("z_(M_raw-M)")
    cols.append(run.env.zV)
    names.append("zV")
    X = np.column_stack(cols)
    b, lo, hi = ols_boot(D, X, ip, rng)
    return pd.DataFrame({"term": names, "coef": b, "ci_lo": lo, "ci_hi": hi})
