"""Data audits for the real-data run: extreme days, night-session start dates, calendar sanity."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data.universe import NIGHT_SESSION_START_DRAFT


def extreme_days(panel, threshold: float = 0.12, context: int = 2) -> pd.DataFrame:
    """Every product-day with |return| above `threshold`, with the evidence needed to classify it by hand:
    held contract, close / pre-close / pre-settle / high / low / settle, volume, one-price and roll flags, neighbouring returns
    and the share of products moving the same way that day. `suspect` is a heuristic label, not a decision."""
    rows = []
    for p, c in panel.continuous.items():
        r = c["ret"]
        big = r[r.abs() > threshold]
        for dt, val in big.items():
            i = c.index.get_loc(dt)
            row = c.iloc[i]
            nb = r.iloc[max(i - context, 0) : i + context + 1]
            same = np.nan
            if dt in panel.returns.index:
                x = panel.returns.loc[dt].dropna()
                same = float((np.sign(x) == np.sign(val)).mean()) if len(x) else np.nan
            close, lo, hi = row.get("h_close"), row.get("h_low"), row.get("h_high")
            outside = bool(pd.notna(lo) and pd.notna(hi) and pd.notna(close) and (close < lo - 1e-9 or close > hi + 1e-9))
            one_price = bool(row.get("one_price", False))
            roll = bool(row.get("roll_flag", False))
            vol = row.get("h_vol")
            if outside or (pd.notna(vol) and vol == 0):
                tag = "data error candidate"
            elif roll and abs(row.get("unadj_ret", 0) - val) > 0.02:
                tag = "roll-related"
            elif one_price:
                tag = "limit/one-price day"
            elif pd.notna(row.get("h_pre_settle")) and abs(close / row["h_pre_settle"] - 1) > 0.2:
                tag = "beyond any daily limit: check"
            elif pd.notna(row.get("h_pre_close")) and pd.notna(row.get("h_pre_settle")) and abs(row["h_pre_close"] / row["h_pre_settle"] - 1) > 0.10:
                tag = "previous close far from previous settle (>10%): close dislocation, check"
            else:
                tag = "plausible genuine move"
            rows.append({"product": p, "date": dt.date(), "ret": float(val), "contract": row.get("held"), "close": close, "pre_settle": row.get("h_pre_settle"), "high": hi, "low": lo, "settle": row.get("h_settle"),
                         "volume": vol, "one_price": one_price, "roll_day": roll, "unadj_ret": row.get("unadj_ret"), "same_sign_share_of_products": same,
                         "ret_window": ",".join(f"{x:+.3f}" for x in nb.to_numpy()), "close_outside_high_low": outside, "suspect": tag})
    return pd.DataFrame(rows).sort_values("ret", key=lambda s: -s.abs()).reset_index(drop=True) if rows else pd.DataFrame()


def night_session_break(panel, search_days: int = 500, min_seg: int = 120, draft: dict | None = None) -> pd.DataFrame:
    """Check the DRAFT night-session start dates with data. When a night session is added, the bar's open becomes the 21:00 print,
    so ln(open / pre_close) spans ~6 hours instead of ~18: its variance should DROP at the start date. For each product we look for the
    single variance break (likelihood ratio on winsorised squared gaps, roll days excluded) within +-`search_days` of the draft date and
    report the detected date, the variance ratio post/pre, and the distance to the draft."""
    draft = draft or NIGHT_SESSION_START_DRAFT
    rows = []
    for p, c in panel.continuous.items():
        if "h_open" not in c or "h_pre_close" not in c:
            continue
        g = np.log(c["h_open"] / c["h_pre_close"]).replace([np.inf, -np.inf], np.nan)
        g[c["roll_flag"].astype(bool)] = np.nan
        g = g.dropna()
        if len(g) < 2 * min_seg:
            continue
        cap = 5 * g.std()
        g2 = (g.clip(-cap, cap) ** 2).to_numpy()
        n = len(g2)
        cs = np.concatenate([[0.0], np.cumsum(g2)])
        d0 = draft.get(p)
        center = g.index.searchsorted(pd.Timestamp(d0)) if d0 else n // 2
        lo, hi = max(min_seg, center - search_days), min(n - min_seg, center + search_days)
        best, arg = -np.inf, None
        for k in range(lo, hi):
            v1, v2 = cs[k] / k, (cs[n] - cs[k]) / (n - k)
            if v1 <= 0 or v2 <= 0:
                continue
            ll = n * np.log((cs[n]) / n) - k * np.log(v1) - (n - k) * np.log(v2)
            if ll > best:
                best, arg = ll, k
        if arg is None:
            continue
        det = g.index[arg]
        rows.append({"product": p, "draft_start": d0, "detected_break": det.date(), "days_from_draft": int((det - pd.Timestamp(d0)).days) if d0 else np.nan,
                     "var_ratio_post_over_pre": float((cs[n] - cs[arg]) / (n - arg) / (cs[arg] / arg)), "lr_stat": float(best), "draft_in_data_range": bool(d0 and g.index[0] <= pd.Timestamp(d0) <= g.index[-1])})
    return pd.DataFrame(rows)


def calendar_checks(daily: pd.DataFrame) -> dict:
    td = daily["trade_date"].drop_duplicates()
    d = (td if pd.api.types.is_datetime64_any_dtype(td) else pd.to_datetime(td.astype(str), format="%Y%m%d")).sort_values()
    gaps = d.diff().dt.days.dropna()
    return {"n_dates": int(len(d)), "first": str(d.iloc[0].date()), "last": str(d.iloc[-1].date()), "weekend_dates": int((d.dt.dayofweek >= 5).sum()), "gaps_over_5_days": int((gaps > 5).sum()),
            "max_gap_days": int(gaps.max()) if len(gaps) else 0}
