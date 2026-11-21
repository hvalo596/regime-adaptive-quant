"""State variables of docs/state-construction.md section 3 (all point-in-time: row t uses data through the close of t).

  standardise()         3.1  vol-standardised, clipped returns (denominator uses t-1 and earlier)
  loo_factor_regress()  3.2  leave-one-out equal-weight factor, 60d rolling regression, R^2, pre-day residuals
  mr_stat()             3.3/3.4  M_t, R_t, R^gap_t: strategy-matched autocorrelation rho^(L,H) (cross-product form)
  concentration()       3.5  C_t, u_i, p_i, flagged set F_t
  environment()         3.6  V_t, Phi_t, Phi-perp_t and their rolling z-scores
Nothing here looks at returns after t.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import LegSpec, StateParams, kappa_LH, pairs_in_window
from .rolling import expanding_window_mean, ewma_sum, roll_count, roll_mean, roll_sum, shift

def nanmean_rows(a: np.ndarray) -> np.ndarray:
    ok = ~np.isnan(a)
    n = ok.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, np.where(ok, a, 0.0).sum(axis=1) / n, np.nan)


# ---------------------------------------------------------------------------------------------- 3.1 standardise


def standardise(ret: np.ndarray, window: int = 60, clip: float = 5.0) -> tuple[np.ndarray, np.ndarray]:
    """r_tilde_t = clip(r_t / sigma_hat_{t-1}, +-clip); sigma_hat^2_{t-1} = mean of r^2 over the 60 days up to t-1."""
    s2 = roll_mean(ret**2, window, lag=1, min_count=window)
    sig_prev = np.sqrt(s2)
    with np.errstate(invalid="ignore", divide="ignore"):
        rt = np.clip(ret / sig_prev, -clip, clip)
    rt[~np.isfinite(rt)] = np.nan
    return rt, sig_prev


def vol_exante(ret: np.ndarray, window: int = 60) -> np.ndarray:
    """sigma_hat_t through the close of t (used to size positions held from t to t+1)."""
    return np.sqrt(roll_mean(ret**2, window, min_count=window))


# ---------------------------------------------------------------------------------------- 3.2 factor regression


@dataclass
class FactorFit:
    r2: np.ndarray  # (T, N) R^2 of the 60d regression ending at t
    resid: np.ndarray  # (T, N) pre-day (out-of-sample) residuals
    beta: np.ndarray
    n_assets: np.ndarray  # (T,) number of assets with a valid r_tilde


def loo_factor_regress(rt: np.ndarray, window: int = 60, min_assets: int = 6) -> FactorFit:
    valid = ~np.isnan(rt)
    n = valid.sum(axis=1)
    tot = np.where(valid, rt, 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        f = (tot[:, None] - np.where(valid, rt, 0.0)) / (n[:, None] - 1)
    f[(n - 1) < min_assets, :] = np.nan
    f = np.where(valid, f, np.nan)
    m = valid & ~np.isnan(f)
    x = np.where(m, f, 0.0)
    y = np.where(m, rt, 0.0)
    cnt = roll_sum(m.astype(float), window)
    sx, sy = roll_sum(x, window), roll_sum(y, window)
    sxx, sxy, syy = roll_sum(x * x, window), roll_sum(x * y, window), roll_sum(y * y, window)
    with np.errstate(invalid="ignore", divide="ignore"):
        mx, my = sx / cnt, sy / cnt
        vx = sxx / cnt - mx**2
        vy = syy / cnt - my**2
        cxy = sxy / cnt - mx * my
        beta = cxy / vx
        alpha = my - beta * mx
        r2 = cxy**2 / (vx * vy)
    full = cnt >= window
    beta, alpha, r2 = (np.where(full, a, np.nan) for a in (beta, alpha, r2))
    resid = rt - shift(alpha, 1) - shift(beta, 1) * f
    return FactorFit(r2=r2, resid=resid, beta=beta, n_assets=n)


# ---------------------------------------------------------------------------------------------- 3.3/3.4 M and R


def mean_sq_corr(rt: np.ndarray, window: int = 250, min_valid: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Trailing mean of squared pairwise correlations among assets with a full window; returns (rho2_bar, n_full)."""
    T, N = rt.shape
    valid = ~np.isnan(rt)
    x = np.where(valid, rt, 0.0)
    full = roll_sum(valid.astype(float), window) >= window
    cs = np.zeros((T + 1, N, N))
    # float32 cumulative outer products are not accurate enough; chunk the cumulative sum in float64
    prod = x[:, :, None] * x[:, None, :]
    np.cumsum(prod, axis=0, out=cs[1:])
    out = np.full(T, np.nan)
    nfull = np.zeros(T)
    for t in range(window - 1, T):
        a = cs[t + 1] - cs[t + 1 - window]
        d = np.sqrt(np.diag(a))
        ok = full[t] & (d > 0)
        k = int(ok.sum())
        nfull[t] = k
        if k < min_valid:
            continue
        sub = a[np.ix_(ok, ok)] / np.outer(d[ok], d[ok])
        off = (sub**2).sum() - k
        out[t] = off / (k * (k - 1))
    return out, nfull


@dataclass
class MRStat:
    rho: np.ndarray  # (T,) pooled rho_hat^(L,H)
    se_formula: np.ndarray  # (T,) sqrt(kappa / (T_pairs * N_eff)) (before calibration multiplier)
    n_assets: np.ndarray
    n_eff: np.ndarray
    t_pairs: int
    kappa: float


def mr_stat(rt: np.ndarray, spec: LegSpec, rho2_bar: np.ndarray | None = None, nfull_corr: np.ndarray | None = None) -> MRStat:
    """Pooled strategy-matched autocorrelation, per-asset window demeaning (doc 3.3):
        X_s = sum of r_tilde over the last L days ending s,  Y_s = sum over days s+gap+1 .. s+gap+H,
        pair completed at u = s+gap+H, window = the T = W-L-H-gap+1 latest completed pairs.
    rho_hat = sum_i cov_i / sqrt(sum_i varX_i * sum_i varY_i)."""
    L, H, g = spec.L, spec.H, spec.gap
    T_pairs = pairs_in_window(spec)
    valid = ~np.isnan(rt)
    x_ok = roll_count(valid, L) >= L
    y_ok = roll_count(valid, H) >= H
    X = np.where(x_ok, roll_sum(rt, L), np.nan)
    Y = np.where(y_ok, roll_sum(rt, H), np.nan)
    Xu = shift(X, g + H)
    pair = ~np.isnan(Xu) & ~np.isnan(Y)
    xu = np.where(pair, Xu, 0.0)
    yu = np.where(pair, Y, 0.0)
    n = roll_sum(pair.astype(float), T_pairs)
    sx, sy = roll_sum(xu, T_pairs), roll_sum(yu, T_pairs)
    sxy, sxx, syy = roll_sum(xu * yu, T_pairs), roll_sum(xu * xu, T_pairs), roll_sum(yu * yu, T_pairs)
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy - sx * sy / n
        vx = sxx - sx**2 / n
        vy = syy - sy**2 / n
    use = n >= T_pairs
    cov, vx, vy = (np.where(use, a, 0.0) for a in (cov, vx, vy))
    na = use.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = cov.sum(axis=1) / np.sqrt(vx.sum(axis=1) * vy.sum(axis=1))
    rho[na < 5] = np.nan
    if rho2_bar is None:
        rho2_bar, nfull_corr = mean_sq_corr(rt)
    with np.errstate(invalid="ignore", divide="ignore"):
        n_eff = na / (1.0 + (na - 1.0) * np.nan_to_num(rho2_bar, nan=np.nan))
    kap = kappa_LH(L, H)
    with np.errstate(invalid="ignore", divide="ignore"):
        se = np.sqrt(kap / (T_pairs * n_eff))
    se[~np.isfinite(se) | (na < 5)] = np.nan
    return MRStat(rho=rho, se_formula=se, n_assets=na.astype(float), n_eff=n_eff, t_pairs=T_pairs, kappa=kap)


def tau_stat(stat: MRStat, kind: str, bias: float, se_mult: float) -> np.ndarray:
    """tau^M = (M - b^M)/se with M = rho; tau^R = (R - b^R)/se with R = -rho and b^R = -b^rho."""
    sign = 1.0 if kind == "mom" else -1.0
    return sign * (stat.rho - bias) / (se_mult * stat.se_formula)


# ---------------------------------------------------------------------------------------------- 3.5 concentration


def excess_kurtosis_window(e: np.ndarray, window: int, lag: int) -> np.ndarray:
    m2 = roll_mean(e**2, window, lag=lag, min_count=window)
    m4 = roll_mean(e**4, window, lag=lag, min_count=window)
    with np.errstate(invalid="ignore", divide="ignore"):
        return m4 / m2**2 - 3.0


@dataclass
class Concentration:
    u: np.ndarray  # (T, N) capped abnormal ratio
    p: np.ndarray  # (T, N) shares
    hhi: np.ndarray
    h0: np.ndarray
    C: np.ndarray
    n_live: np.ndarray
    kurt: np.ndarray  # (T,) cross-sectional mean excess kurtosis used in h0
    flagged: np.ndarray  # (T, N) bool: member of F_t on day t (only meaningful when I_t = 1; see apply_threshold)


def concentration(resid: np.ndarray, sp: StateParams = StateParams(), kurt_cap: float = 30.0) -> Concentration:
    e2 = resid**2
    recent = roll_mean(e2, sp.c_recent, min_count=sp.c_recent)
    base = roll_mean(e2, sp.c_base, lag=sp.c_recent, min_count=sp.c_base)
    with np.errstate(invalid="ignore", divide="ignore"):
        u = np.minimum(recent / base, sp.u_cap)
    u[~np.isfinite(u)] = np.nan
    live = ~np.isnan(u)
    n = live.sum(axis=1)
    tot = np.where(live, u, 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(live, u / tot[:, None], np.nan)
        hhi = np.nansum(p**2, axis=1)
    hhi[n < 3] = np.nan
    kx = excess_kurtosis_window(resid, sp.c_base, sp.c_recent)
    kx = np.clip(kx, 0.0, kurt_cap)
    k_mean = nanmean_rows(np.where(live, kx, np.nan))
    with np.errstate(invalid="ignore", divide="ignore"):
        h0 = (1.0 / n) * (1.0 + (2.0 + k_mean) / sp.c_recent)
        C = (hhi - h0) / (1.0 - h0)
    C[n < 3] = np.nan
    flagged = flag_sets(u, p, sp)
    return Concentration(u=u, p=p, hhi=hhi, h0=h0, C=C, n_live=n.astype(float), kurt=k_mean, flagged=flagged)


def flag_sets(u: np.ndarray, p: np.ndarray, sp: StateParams) -> np.ndarray:
    """F_t = smallest set of assets (largest shares first) with cumulative share >= 0.5, every member with u >= 4.
    If the assets with u >= 4 do not carry 50% of the mass in total, F_t is empty."""
    T, N = u.shape
    out = np.zeros((T, N), dtype=bool)
    for t in range(T):
        ut = u[t]
        ok = ~np.isnan(ut) & (ut >= sp.u_flag_min)
        if not ok.any():
            continue
        idx = np.flatnonzero(ok)
        order = idx[np.argsort(-p[t, idx])]
        cum = np.cumsum(p[t, order])
        if cum[-1] < sp.flag_mass:
            continue
        k = int(np.searchsorted(cum, sp.flag_mass - 1e-12)) + 1
        out[t, order[:k]] = True
    return out


_NULL_C_CACHE: dict[tuple[int, float, float], float] = {}


def null_c_threshold(n_assets: int, kurt_excess: float, sp: StateParams = StateParams(), n_rep: int = 1000, seed: int = 12345) -> float:
    """c_C^{95%}(N): quantile of C under 'no concentration' (doc 3.5 item 5): u_i drawn independently from the sampling
    distribution of a 20d / 250d variance ratio for iid t-distributed residuals with the panel's own kurtosis."""
    kurt_excess = float(np.clip(round(float(kurt_excess)), 1.0, 20.0))
    key = (int(n_assets), kurt_excess, sp.c_level)
    if key in _NULL_C_CACHE:
        return _NULL_C_CACHE[key]
    rng = np.random.default_rng(seed + 7919 * int(n_assets))
    nu = 4.0 + 6.0 / max(kurt_excess, 0.05)
    nu = float(np.clip(nu, 4.2, 200.0))
    scale = np.sqrt((nu - 2.0) / nu)
    N = int(n_assets)
    c_vals = np.empty(n_rep)
    for r in range(n_rep):
        z = rng.standard_t(nu, size=(sp.c_recent + sp.c_base, N)) * scale
        rec = (z[-sp.c_recent :] ** 2).mean(axis=0)
        bas = (z[: sp.c_base] ** 2).mean(axis=0)
        u = np.minimum(rec / bas, sp.u_cap)
        p = u / u.sum()
        hhi = (p**2).sum()
        h0 = (1.0 / N) * (1.0 + (2.0 + kurt_excess) / sp.c_recent)
        c_vals[r] = (hhi - h0) / (1.0 - h0)
    thr = float(np.quantile(c_vals, sp.c_level))
    _NULL_C_CACHE[key] = thr
    return thr


def informed_indicator(conc: Concentration, sp: StateParams = StateParams()) -> tuple[np.ndarray, np.ndarray]:
    """I_t = 1{C_t >= c_C(N_t)}; F_t members only where I_t = 1. Returns (I (T,) bool, F (T, N) bool)."""
    T = len(conc.C)
    I = np.zeros(T, dtype=bool)
    for t in range(T):
        if np.isnan(conc.C[t]) or conc.n_live[t] < 3:
            continue
        k = conc.kurt[t] if np.isfinite(conc.kurt[t]) else 6.0
        I[t] = conc.C[t] >= null_c_threshold(int(conc.n_live[t]), k, sp)
    F = conc.flagged & I[:, None]
    return I, F


def exclusion_mask(F: np.ndarray, k_i: int) -> np.ndarray:
    """excl[t, i] = True when asset i was flagged at some t' in (t-k_i, t]: no reversal position from close t."""
    T, N = F.shape
    c = np.concatenate([np.zeros((1, N)), np.cumsum(F.astype(float), axis=0)])
    t = np.arange(T)
    lo = np.maximum(t + 1 - k_i, 0)
    return (c[t + 1] - c[lo]) > 0


# ---------------------------------------------------------------------------------------------- 3.6 V and Phi-perp


def scalar_rolling_ols(x: np.ndarray, y: np.ndarray, w: int, min_n: int, lag: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Intercept and slope of y ~ x over the last up-to-`w` valid rows ending at row t-lag (min `min_n`)."""
    T = len(x)
    ok = ~np.isnan(x) & ~np.isnan(y)
    xs, ys = np.where(ok, x, 0.0), np.where(ok, y, 0.0)
    cs = {k: np.concatenate([[0.0], np.cumsum(v)]) for k, v in dict(n=ok.astype(float), x=xs, y=ys, xx=xs * xs, xy=xs * ys).items()}
    a = np.full(T, np.nan)
    b = np.full(T, np.nan)
    for t in range(lag, T):
        hi = t - lag + 1
        lo = max(hi - w, 0)
        n = cs["n"][hi] - cs["n"][lo]
        if n < min_n:
            continue
        sx, sy = cs["x"][hi] - cs["x"][lo], cs["y"][hi] - cs["y"][lo]
        sxx, sxy = cs["xx"][hi] - cs["xx"][lo], cs["xy"][hi] - cs["xy"][lo]
        vx = sxx / n - (sx / n) ** 2
        if vx <= 0:
            continue
        b[t] = (sxy / n - sx * sy / n**2) / vx
        a[t] = sy / n - b[t] * sx / n
    return a, b


def rolling_z(x: np.ndarray, w: int, min_n: int) -> np.ndarray:
    """z-score of x_t against the mean / sd of the last up-to-`w` values ending at t-1."""
    m = expanding_window_mean(x, w, min_n, lag=1)
    m2 = expanding_window_mean(x**2, w, min_n, lag=1)
    with np.errstate(invalid="ignore"):
        sd = np.sqrt(np.maximum(m2 - m**2, 0.0))
        return (x - m) / sd


@dataclass
class Environment:
    V: np.ndarray
    Phi: np.ndarray
    Phi_perp: np.ndarray
    zV: np.ndarray
    zPhi_perp: np.ndarray


def environment(ret: np.ndarray, r2: np.ndarray, sp: StateParams = StateParams()) -> Environment:
    r_sq = ret**2
    ew = ewma_sum(r_sq, sp.v_halflife)
    base = expanding_window_mean(r_sq, sp.v_base, sp.v_min_base, lag=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.log(ew / base)
    lv[~np.isfinite(lv)] = np.nan
    V = nanmean_rows(lv)
    mr2 = nanmean_rows(r2)
    m = np.clip(mr2, 1e-4, 1 - 1e-4)
    Phi = np.log(m / (1 - m))
    a, b = scalar_rolling_ols(V, Phi, sp.v_base, sp.v_min_base, lag=1)
    Pp = Phi - a - b * V
    return Environment(V=V, Phi=Phi, Phi_perp=Pp, zV=rolling_z(V, sp.z_window, sp.z_min), zPhi_perp=rolling_z(Pp, sp.z_window, sp.z_min))
