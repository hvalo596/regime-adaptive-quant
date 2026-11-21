"""Roll-adjusted continuous series built from per-contract daily data (not from Tushare's continuous codes).

Why: the official continuous code splices raw prices (roll jumps of several % are in the data), the index
mapping is "current/near month", not the main contract, and the TL continuous code is contaminated before
its real listing (internal/tushare-access-check.md).

Construction (point-in-time):
  * `target[t]` = contract chosen with information through the close of day t.
  * The contract HELD on day t+1 is target[t]; the day-(t+1) return is that contract's own close-to-close return
    close_k(t+1) / close_k(t) - 1. Returns therefore never straddle two contracts, so the roll gap is excluded
    by construction (this is equivalent to ratio back-adjustment, without needing a rebased price level).
  * A roll costs two legs; `roll_flag` marks the first day of holding a new contract so the backtest can charge it.

Selection rules (`RollParams.rule`):
  * "oi":       highest open interest among tradable contracts. Forward-only (never switches to an earlier expiry
                unless forced) with a strict-greater OI switch condition, which stops flip-flopping around OI crossings.
                A contract inside `expiry_buffer_days` of last trading day is never held (delivery-month risk).
  * "official": Tushare fut_mapping contract (falls back to "oi" on days the mapped contract has no data).
  * "auto":     per product, use the official mapping only if it agrees with the OI rule on at least
                `min_agreement` of overlapping days, otherwise the OI rule. This is the "stock-index by OI when the
                mapping mismatches" decision, taken from data per product instead of hard-coded.

Prices are close, never settle (settlement is a volume-weighted average and manufactures autocorrelation).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RollParams:
    rule: str = "auto"
    expiry_buffer_days: int = 10
    switch_margin: float = 1.0  # candidate OI must exceed current OI * margin
    min_agreement: float = 0.8


def _expiry_dates(basic_p: pd.DataFrame, codes: list[str], last_seen: pd.Series) -> pd.DatetimeIndex:
    b = basic_p.set_index("ts_code")
    out = []
    for c in codes:
        e = pd.NaT
        if c in b.index:
            for col in ("last_ddate", "delist_date"):
                v = b.at[c, col] if col in b.columns else None
                if isinstance(v, str) and len(v) == 8:
                    e = pd.to_datetime(v, format="%Y%m%d")
                    break
        out.append(e if pd.notna(e) else last_seen[c])
    return pd.DatetimeIndex(out)


def select_by_oi(
    dates: pd.DatetimeIndex,
    close: np.ndarray,
    oi: np.ndarray,
    vol: np.ndarray,
    expiry: pd.DatetimeIndex,
    last_row: np.ndarray,
    params: RollParams,
) -> np.ndarray:
    """Return the chosen contract column per date (-1 = none). Contracts are columns, dates are rows."""
    T, K = close.shape
    exp_days = (expiry.values[None, :] - dates.values[:, None]).astype("timedelta64[D]").astype(float)
    ok_expiry = exp_days >= params.expiry_buffer_days
    tradable = ~np.isnan(close) & (np.nan_to_num(vol) > 0) & ok_expiry
    oi_f = np.where(np.isnan(oi), -np.inf, oi)
    target = np.full(T, -1, dtype=np.int64)
    cur = -1
    for t in range(T):
        if cur >= 0 and (t > last_row[cur] or not ok_expiry[t, cur]):
            cur = -1
        masked = np.where(tradable[t], oi_f[t], -np.inf)
        cand = int(np.argmax(masked)) if np.isfinite(masked).any() else -1
        if cur < 0:
            cur = cand
        elif cand >= 0 and cand != cur:
            fwd = expiry[cand] > expiry[cur]
            if fwd and masked[cand] > oi_f[t, cur] * params.switch_margin:
                cur = cand
        target[t] = cur
    return target


def enforce_forward_only(
    raw: np.ndarray,
    fallback: np.ndarray,
    dates: pd.DatetimeIndex,
    expiry: pd.DatetimeIndex,
    last_row: np.ndarray,
    params: RollParams,
) -> np.ndarray:
    """Make any target series roll forward only: a switch to an earlier-expiry contract is ignored unless the held
    contract is dead or inside the expiry buffer (then `raw`, else `fallback`, decides). Stops an official mapping
    or a noisy OI crossing from flip-flopping between two contracts (each flip would be a paid roll)."""
    exp_days = (expiry.values[None, :] - dates.values[:, None]).astype("timedelta64[D]").astype(float)
    ok = exp_days >= params.expiry_buffer_days
    out = np.full(len(raw), -1, dtype=np.int64)
    cur = -1
    for t in range(len(raw)):
        if cur >= 0 and (t > last_row[cur] or not ok[t, cur]):
            cur = -1
        k = raw[t] if raw[t] >= 0 else fallback[t]
        if cur < 0:
            cur = k
        elif k >= 0 and k != cur and expiry[k] > expiry[cur]:
            cur = k
        out[t] = cur
    return out


def _share_max_oi(oi: np.ndarray, target: np.ndarray) -> float:
    has = ~np.isnan(oi).all(axis=1) & (target >= 0)
    if not has.any():
        return float("nan")
    best = np.nanargmax(np.where(np.isnan(oi[has]), -np.inf, oi[has]), axis=1)
    return float((best == target[has]).mean())


def build_continuous(
    product: str,
    basic: pd.DataFrame,
    daily: pd.DataFrame,
    mapping: pd.DataFrame | None = None,
    params: RollParams = RollParams(),
) -> tuple[pd.DataFrame, dict]:
    """Return (series, diagnostics). `daily` has a datetime `trade_date`; `basic` is fut_basic (fut_type=1)."""
    basic_p = basic[basic["fut_code"] == product]
    d = daily[daily["ts_code"].isin(basic_p["ts_code"])].copy()
    d = d.dropna(subset=["close"]).drop_duplicates(["ts_code", "trade_date"])
    d = d[d["close"] > 0]
    if d.empty:
        return pd.DataFrame(), {"product": product, "n_days": 0}

    def wide(col):
        return d.pivot(index="trade_date", columns="ts_code", values=col).sort_index()

    close, oi, vol = wide("close"), wide("oi"), wide("vol")
    last_seen = d.groupby("ts_code")["trade_date"].max()
    codes = list(close.columns)
    dates = close.index
    expiry = _expiry_dates(basic_p, codes, last_seen)
    order = np.argsort(expiry.values, kind="stable")
    codes = [codes[i] for i in order]
    close, oi, vol = close[codes], oi[codes], vol[codes]
    expiry = expiry[order]
    last_row = np.array([dates.get_loc(last_seen[c]) for c in codes])

    t_oi = select_by_oi(dates, close.to_numpy(), oi.to_numpy(), vol.to_numpy(), expiry, last_row, params)

    agreement, rule_used, t_off = np.nan, "oi", None
    col_of = {c: i for i, c in enumerate(codes)}
    if mapping is not None and not mapping.empty and params.rule in ("official", "auto"):
        m = mapping.copy()
        if not pd.api.types.is_datetime64_any_dtype(m["trade_date"]):
            m["trade_date"] = pd.to_datetime(m["trade_date"].astype(str), format="%Y%m%d")
        m = m.drop_duplicates("trade_date").set_index("trade_date")["mapping_ts_code"].reindex(dates)
        t_off = np.array([col_of.get(c, -1) if isinstance(c, str) else -1 for c in m.to_numpy()])
        both = (t_off >= 0) & (t_oi >= 0)
        agreement = float((t_off[both] == t_oi[both]).mean()) if both.any() else np.nan
        if params.rule == "official" or (np.isfinite(agreement) and agreement >= params.min_agreement):
            rule_used = "official"
    target = t_oi.copy()
    if rule_used == "official":
        usable = (t_off >= 0) & ~np.isnan(close.to_numpy()[np.arange(len(dates)), np.maximum(t_off, 0)])
        target = enforce_forward_only(np.where(usable, t_off, -1), t_oi, dates, expiry, last_row, params)

    cl = close.to_numpy()
    n = len(dates)
    idx = np.arange(n)
    held = np.r_[-1, target[:-1]]
    ret = np.full(n, np.nan)
    stale = np.zeros(n, dtype=bool)
    for i in range(1, n):
        k = held[i]
        if k < 0:
            continue
        a, b = cl[i - 1, k], cl[i, k]
        if np.isnan(a) or np.isnan(b):
            ret[i], stale[i] = 0.0, True
        else:
            ret[i] = b / a - 1.0
    roll = np.r_[False, (held[1:] != held[:-1]) & (held[1:] >= 0) & (held[:-1] >= 0)]

    spliced = np.where(target >= 0, cl[idx, np.maximum(target, 0)], np.nan)
    unadj = pd.Series(spliced, index=dates).pct_change(fill_method=None)
    adj_ret = pd.Series(ret, index=dates)

    def held_col(df_w):
        a = df_w.to_numpy()
        return np.where(held >= 0, a[idx, np.maximum(held, 0)], np.nan)

    extra = {}
    for col in ("high", "low", "pre_settle", "pre_close", "open", "settle", "amount"):
        if col in d.columns:
            extra[f"h_{col}"] = held_col(wide(col)[codes])
    out = pd.DataFrame(
        {
            "held": [codes[k] if k >= 0 else None for k in held],
            "ret": adj_ret,
            "unadj_ret": unadj,
            "roll_flag": roll,
            "stale": stale,
            "h_close": held_col(close),
            "h_oi": held_col(oi),
            "h_vol": held_col(vol),
            "days_to_expiry": np.where(
                held >= 0, (expiry.values[np.maximum(held, 0)] - dates.values).astype("timedelta64[D]").astype(float), np.nan
            ),
            **extra,
        },
        index=dates,
    )
    out.index.name = "trade_date"
    out["adj_index"] = 100.0 * (1.0 + out["ret"].fillna(0.0)).cumprod()

    roll_days = np.r_[False, (target[1:] != target[:-1]) & (target[1:] >= 0) & (target[:-1] >= 0)]
    gap = (unadj - adj_ret)[roll_days]
    diag = {
        "product": product,
        "first_date": str(dates[0].date()),
        "last_date": str(dates[-1].date()),
        "n_days": int(out["ret"].notna().sum()),
        "n_contracts": len(codes),
        "n_rolls": int(roll.sum()),
        "rule_used": rule_used,
        "official_agreement": agreement,
        "max_abs_unadj_roll_jump": float(gap.abs().max()) if len(gap) else 0.0,
        "mean_abs_unadj_roll_jump": float(gap.abs().mean()) if len(gap) else 0.0,
        "stale_days": int(stale.sum()),
        "share_days_held_is_max_oi": _share_max_oi(oi.to_numpy(), target),
    }
    return out, diag
