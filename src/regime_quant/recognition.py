"""Step 3 (rule-baseline layer only): how fast can a causal rule recognise a state? DRAFT, no HMM yet.

Causal label  = expanding tercile bin of the proxy through t (what a live system would know).
Reference     = the same proxy smoothed with a CENTERED rolling median (uses the future: ex-post "truth",
                the real-data approximation the doc prescribes) and binned with full-sample terciles of the
                smoothed series. Reference segments are runs >= `min_len` days in the high (2) or low (0) bin.
Detection delay of a reference segment = days from its start until the causal label first equals the segment's bin
(NaN = missed). Headline number: mean segment duration / mean detection delay (doc step 3; delay floored at 1 day). Also reported: share of
segments missed, and the flip rate of the causal label (flips per 252 days) as a churn proxy.
Smoothing window and thresholds are TO_LOCK; the reference is a convenience, not ground truth.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .diagnostics import expanding_tercile_bins


def reference_bins(proxy: pd.Series, smooth: int) -> pd.Series:
    sm = proxy.rolling(smooth, center=True, min_periods=smooth).median()
    q1, q2 = sm.quantile(1 / 3), sm.quantile(2 / 3)
    out = pd.Series(np.nan, index=proxy.index)
    ok = sm.notna()
    out[ok] = np.where(sm[ok] < q1, 0.0, np.where(sm[ok] < q2, 1.0, 2.0))
    return out


def _runs(labels: np.ndarray, value: float, min_len: int):
    start = None
    for i, v in enumerate(np.r_[labels == value, False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_len:
                yield start, i
            start = None


def recognition_stats(proxy: pd.Series, min_obs: int = 250, smooth: int = 20, min_len: int = 10) -> pd.DataFrame:
    causal = expanding_tercile_bins(proxy, min_obs)
    ref = reference_bins(proxy, smooth)
    df = pd.DataFrame({"c": causal, "r": ref}).dropna()
    c, r = df["c"].to_numpy(), df["r"].to_numpy()
    rows = []
    for value, name in ((2.0, "high"), (0.0, "low")):
        durs, delays, missed = [], [], 0
        for a, b in _runs(r, value, min_len):
            hit = np.flatnonzero(c[a:b] == value)
            durs.append(b - a)
            if len(hit):
                delays.append(int(hit[0]))
            else:
                missed += 1
        n = len(durs)
        md, mdel = (float(np.mean(durs)) if n else np.nan), (float(np.mean(delays)) if delays else np.nan)
        rows.append(
            {
                "bin": name, "n_segments": n, "mean_duration": md, "mean_delay": mdel,
                "median_delay": float(np.median(delays)) if delays else np.nan,
                "share_missed": missed / n if n else np.nan,
                "duration_over_delay": md / max(mdel, 1.0) if n and delays else np.nan,
                "causal_flips_per_year": float((np.diff(c) != 0).sum() / len(c) * 252),
            }
        )
    return pd.DataFrame(rows)


def recognition_table(proxies: pd.DataFrame, **kw) -> pd.DataFrame:
    parts = []
    for name in proxies.columns:
        t = recognition_stats(proxies[name], **kw)
        t.insert(0, "proxy", name)
        parts.append(t)
    return pd.concat(parts, ignore_index=True)
