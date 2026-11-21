"""Non-defining variables of doc section 5 (none of them enters the state definition):
g^OI, abnormal volume AV, Amihud ILLIQ, the Llorente-Michaely-Saar-Wang coefficient b2, member-ranking (seat) signatures and
exogenous margin / limit events. Each state's signature is compared with state IV by block bootstrap and cyclic-shift null.
All series are point-in-time (row t uses data through t)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import InferenceParams
from .inference import mean_diff_test, quantile_ci, stationary_bootstrap_indices
from .rolling import expanding_window_mean, roll_mean, shift
from .statevars import nanmean_rows


def zscore_own(x: np.ndarray, window: int = 250, min_n: int = 100) -> np.ndarray:
    """z-score of x_t against the asset's own last up-to-`window` values ending at t-1."""
    m = expanding_window_mean(x, window, min_n, lag=1)
    m2 = expanding_window_mean(x**2, window, min_n, lag=1)
    with np.errstate(invalid="ignore"):
        sd = np.sqrt(np.maximum(m2 - m**2, 0.0))
        z = (x - m) / sd
    z[~np.isfinite(z)] = np.nan
    return z


def oi_growth(oi: np.ndarray, k: int = 5) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        g = np.log(oi) - np.log(shift(oi, k))
    g[~np.isfinite(g)] = np.nan
    return zscore_own(g)


def abnormal_volume(vol: np.ndarray, window: int = 60) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.log(vol)
    lv[~np.isfinite(lv)] = np.nan
    base = roll_mean(lv, window, lag=1, min_count=window // 2)
    return lv - base


def amihud(ret: np.ndarray, amount: np.ndarray, window: int = 20) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        x = np.abs(ret) / amount
    x[~np.isfinite(x)] = np.nan
    m = roll_mean(x, window, min_count=window // 2)
    with np.errstate(invalid="ignore", divide="ignore"):
        lm = np.log(m)
    lm[~np.isfinite(lm)] = np.nan
    return zscore_own(lm)


def llorente_stats(rt: np.ndarray, av: np.ndarray, cell_mask: np.ndarray | None = None) -> np.ndarray:
    """Per-day sufficient statistics (S11, S12, S22, T1, T2) of the pooled regression
        r_tilde_{i,t+1} = a_i + b1 r_tilde_{i,t} + b2 AV_{i,t} r_tilde_{i,t},
    with asset means removed over the whole sample (fixed effects). `cell_mask` (T, N) restricts to asset-days (e.g. flagged
    assets). Shape (T, 5); decision-day indexing (day t holds the pair formed at t and realised at t+1)."""
    y = np.full_like(rt, np.nan)
    y[:-1] = rt[1:]
    x1 = rt
    x2 = av * rt
    ok = ~np.isnan(y) & ~np.isnan(x1) & ~np.isnan(x2)
    if cell_mask is not None:
        ok &= cell_mask
    def dm(a):
        a = np.where(ok, a, np.nan)
        return a - np.nanmean(a, axis=0, keepdims=True)
    y0, a0, b0 = dm(y), dm(x1), dm(x2)
    z = lambda a: np.where(ok, a, 0.0)  # noqa: E731
    a0, b0, y0 = z(a0), z(b0), z(y0)
    return np.stack([(a0 * a0).sum(1), (a0 * b0).sum(1), (b0 * b0).sum(1), (a0 * y0).sum(1), (b0 * y0).sum(1)], axis=1)


def b2_from_stats(stats: np.ndarray, day_mask: np.ndarray) -> tuple[float, float]:
    s = stats[day_mask].sum(axis=0)
    det = s[0] * s[2] - s[1] ** 2
    if not np.isfinite(det) or abs(det) < 1e-12:
        return float("nan"), float("nan")
    b1 = (s[2] * s[3] - s[1] * s[4]) / det
    b2 = (s[0] * s[4] - s[1] * s[3]) / det
    return float(b1), float(b2)


def b2_bootstrap(stats: np.ndarray, day_mask: np.ndarray, ip: InferenceParams, rng: np.random.Generator) -> dict:
    """b2 of the pooled regression on the days in `day_mask`, with a stationary-block-bootstrap CI over the whole timeline."""
    b1, b2 = b2_from_stats(stats, day_mask)
    T = len(day_mask)
    idx = stationary_bootstrap_indices(T, ip.mean_block, ip.n_boot, rng)
    st = stats[idx] * day_mask[idx][:, :, None]
    s = st.sum(axis=1)
    det = s[:, 0] * s[:, 2] - s[:, 1] ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        bb = (s[:, 0] * s[:, 4] - s[:, 1] * s[:, 3]) / det
    bb = bb[np.isfinite(bb)]
    lo, hi = quantile_ci(bb, ip.ci_level) if len(bb) > 20 else (float("nan"), float("nan"))
    p_pos = float((1 + (bb <= 0).sum()) / (1 + len(bb))) if len(bb) else float("nan")
    return {"b1": b1, "b2": b2, "ci_lo": lo, "ci_hi": hi, "p_b2_le_0": p_pos, "n_days": int(day_mask.sum())}


def panel_series(x: np.ndarray, cell_mask: np.ndarray | None = None) -> np.ndarray:
    y = np.where(cell_mask, x, np.nan) if cell_mask is not None else x
    return nanmean_rows(y)


def state_signature_table(series: dict[str, np.ndarray], labels: np.ndarray, ref: str = "IV", ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None) -> pd.DataFrame:
    """Delta_jk = E[Z_j | k] - E[Z_j | IV] for every state k in I, II, III and series Z_j."""
    rng = rng or np.random.default_rng(0)
    rows = []
    ref_mask = labels == ref
    for name, z in series.items():
        for k in ("I", "II", "III"):
            m = labels == k
            r = mean_diff_test(z, m, ref_mask, ip, rng)
            rows.append({"signature": name, "state": k, "mean_state": float(np.nanmean(z[m])) if m.any() else np.nan, "mean_IV": float(np.nanmean(z[ref_mask])) if ref_mask.any() else np.nan,
                         "diff": r.diff, "ci_lo": r.ci_lo, "ci_hi": r.ci_hi, "p_shift": r.p_shift, "n_state": r.n_a, "n_IV": r.n_b, "segments_state": r.segs_a})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------- member rankings


def seat_panel(holding: pd.DataFrame, oi: pd.DataFrame, products: list[str], k: int = 5) -> dict[str, pd.DataFrame]:
    """Top-20 member holdings (fut_holding) summed over the contracts of a product on a date:
        gross = sum(long + short), net = sum(long - short). Returns the k-day change of gross / OI and of net / OI.
    Seats are not clients and hedgers are not separated: semi-direct evidence only (doc 5.3)."""
    h = holding.copy()
    h["product"] = h["symbol"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
    h = h[h["product"].isin(products) & h["broker"].notna() & ~h["broker"].astype(str).str.contains("期货公司", na=False)]
    h["trade_date"] = pd.to_datetime(h["trade_date"].astype(str), format="%Y%m%d")
    g = h.groupby(["trade_date", "product"]).agg(long=("long_hld", "sum"), short=("short_hld", "sum")).reset_index()
    g["gross"] = g["long"] + g["short"]
    g["net"] = g["long"] - g["short"]
    gross = g.pivot(index="trade_date", columns="product", values="gross").reindex(oi.index).reindex(columns=products)
    net = g.pivot(index="trade_date", columns="product", values="net").reindex(oi.index).reindex(columns=products)
    d_gross = (gross - gross.shift(k)) / oi
    d_net = (net - net.shift(k)) / oi
    return {"d_gross_over_oi": d_gross, "d_net_over_oi": d_net}


# --------------------------------------------------------------------------------------------- events


def events_from_mask(mask: pd.DataFrame, min_gap: int = 20) -> dict[str, np.ndarray]:
    """Event days per product from a boolean (date x product) frame; consecutive events closer than `min_gap` days are merged
    to the first (one event = one episode)."""
    out = {}
    for p in mask.columns:
        idx = np.flatnonzero(mask[p].to_numpy(dtype=bool))
        keep, last = [], -10**9
        for i in idx:
            if i - last >= min_gap:
                keep.append(i)
            last = i
        out[p] = np.array(keep, dtype=int)
    return out


def margin_events_from_settle(settle_params: pd.DataFrame, dates: pd.DatetimeIndex, products: list[str], col: str = "long_margin_rate") -> pd.DataFrame:
    """Boolean (date x product): the product's exchange margin rate (max over its contracts) rose versus the previous trading day."""
    s = settle_params.copy()
    s["product"] = s["ts_code"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
    s["trade_date"] = pd.to_datetime(s["trade_date"].astype(str), format="%Y%m%d")
    m = s.groupby(["trade_date", "product"])[col].max().unstack().reindex(dates).reindex(columns=products).ffill()
    return (m.diff() > 1e-9).fillna(False)


def event_study(events: dict[str, np.ndarray], series: dict[str, np.ndarray], horizon: int = 10, guard: int = 20, ip: InferenceParams = InferenceParams(), rng: np.random.Generator | None = None) -> dict:
    """For every event (product p, day e): mean of the series over days e+1..e+horizon minus the same quantity at the nearest control
    day of the same product with no event within +-`guard` days. Returns the mean difference with a bootstrap over events."""
    rng = rng or np.random.default_rng(0)
    diffs = []
    for p, ev in events.items():
        x = series.get(p)
        if x is None or len(ev) == 0:
            continue
        T = len(x)
        busy = np.zeros(T, dtype=bool)
        for e in ev:
            busy[max(e - guard, 0) : min(e + guard + 1, T)] = True
        free = np.flatnonzero(~busy)
        if len(free) == 0:
            continue
        def post(i):
            w = x[i + 1 : i + 1 + horizon]
            return np.nanmean(w) if len(w) == horizon and np.isfinite(w).sum() >= horizon // 2 else np.nan
        for e in ev:
            c = free[np.argmin(np.abs(free - e))]
            a, b = post(e), post(c)
            if np.isfinite(a) and np.isfinite(b):
                diffs.append(a - b)
    d = np.array(diffs)
    if len(d) < 5:
        return {"n_events": len(d), "mean_diff": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan")}
    boot = d[rng.integers(0, len(d), size=(ip.n_boot, len(d)))].mean(axis=1)
    lo, hi = quantile_ci(boot, ip.ci_level)
    return {"n_events": len(d), "mean_diff": float(d.mean()), "ci_lo": lo, "ci_hi": hi}
