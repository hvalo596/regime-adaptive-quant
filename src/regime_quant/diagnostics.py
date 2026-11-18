"""Observable state proxies (point-in-time), conditional analysis of D, and the existence test.

Proxies are variance ratios VR(q) = Var(q-day return) / (q * Var(1-day return)) over a rolling window,
averaged across assets. They map to the two trader types at their own time scales:
  * short scale (q~5):  VR < 1  <->  impatient traders / rebound  <->  reversal pays
  * long scale  (q~20): VR > 1  <->  slow traders / persistence   <->  momentum pays
Pre-registered direction for D = mom - rev: D increases with BOTH proxies (high bin minus low bin > 0).

Anti-look-ahead rules enforced here:
  * proxies at row t use returns through t only;
  * bin thresholds are EXPANDING quantiles through t (never full-sample quantiles);
  * the bin label at t is matched with D earned on day t+1 (the label is known at the close of t).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS, InferenceParams, ProxyParams
from .inference import group_mean_diff_ci


def variance_ratio(returns: pd.DataFrame, q: int, window: int) -> pd.Series:
    """Cross-asset mean of rolling Lo-MacKinlay VR(q). Overlapping q-sums; window in days."""
    var1 = returns.rolling(window, min_periods=window).var()
    sq = returns.rolling(q, min_periods=q).sum()
    varq = sq.rolling(window - q + 1, min_periods=window - q + 1).var()
    return (varq / (q * var1)).mean(axis=1)


def state_proxies(returns: pd.DataFrame, p: ProxyParams) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "vr_short": variance_ratio(returns, p.vr_short_q, p.vr_short_window),
            "vr_long": variance_ratio(returns, p.vr_long_q, p.vr_long_window),
        }
    )


def expanding_tercile_bins(proxy: pd.Series, min_obs: int) -> pd.Series:
    """0 = low, 1 = mid, 2 = high, using thresholds estimated on data through t only."""
    clean = proxy.dropna()
    q1 = clean.expanding(min_periods=min_obs).quantile(1 / 3)
    q2 = clean.expanding(min_periods=min_obs).quantile(2 / 3)
    bins = pd.Series(np.nan, index=proxy.index)
    b = np.where(clean < q1, 0.0, np.where(clean < q2, 1.0, 2.0))
    b = np.where(q1.isna(), np.nan, b)
    bins.loc[clean.index] = b
    return bins


def count_segments(labels: pd.Series, value: float, min_len: int) -> int:
    """Number of contiguous runs of `value` of at least min_len days (a proxy for independent episodes)."""
    is_v = (labels == value).to_numpy()
    n, run = 0, 0
    for v in is_v:
        if v:
            run += 1
        else:
            if run >= min_len:
                n += 1
            run = 0
    if run >= min_len:
        n += 1
    return n


def align_next_day(bins: pd.Series, d: pd.Series) -> pd.DataFrame:
    """Pair the bin known at close t-1 with D earned on day t."""
    return pd.DataFrame({"D": d, "bin": bins.shift(1)}).dropna()


def conditional_table(df: pd.DataFrame, bins_name: str, inf: InferenceParams) -> pd.DataFrame:
    rows = []
    for b in (0.0, 1.0, 2.0):
        sub = df[df["bin"] == b]["D"]
        rows.append(
            {
                "proxy": bins_name,
                "bin": {0.0: "low", 1.0: "mid", 2.0: "high"}[b],
                "n_days": len(sub),
                "n_segments": count_segments(df["bin"], b, inf.min_segment_len),
                "mean_D": float(sub.mean()) if len(sub) else np.nan,
                "ann_sharpe_D": float(sub.mean() / sub.std(ddof=1) * np.sqrt(TRADING_DAYS))
                if len(sub) > 2
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def existence_test(
    bins: pd.Series,
    d: pd.Series,
    rng: np.random.Generator,
    inf: InferenceParams,
    proxy_name: str,
) -> dict:
    """High-minus-low-bin difference in mean D with a block-bootstrap CI.
    Draft decision rule (TO CONFIRM): pass iff the CI lies above 0 (pre-registered positive direction)
    and both extreme bins contain at least `min_segments_per_bin` independent segments."""
    df = align_next_day(bins, d)
    x = df["D"].to_numpy()
    hi = (df["bin"] == 2.0).to_numpy()
    lo = (df["bin"] == 0.0).to_numpy()
    res = group_mean_diff_ci(x, hi, lo, rng, inf.n_boot, inf.mean_block, inf.ci_level)
    seg_hi = count_segments(df["bin"], 2.0, inf.min_segment_len)
    seg_lo = count_segments(df["bin"], 0.0, inf.min_segment_len)
    passed = bool(
        np.isfinite(res["ci_lo"])
        and res["ci_lo"] > 0
        and min(seg_hi, seg_lo) >= inf.min_segments_per_bin
    )
    return {"proxy": proxy_name, **res, "seg_high": seg_hi, "seg_low": seg_lo, "pass": passed}


def true_state_table(d: pd.Series, states: pd.Series, names: tuple[str, ...]) -> pd.DataFrame:
    """Oracle conditioning on the KNOWN state (only possible on synthetic data): the ceiling for step 2."""
    df = pd.DataFrame({"D": d, "state": states.shift(1)}).dropna()
    rows = []
    for k, name in enumerate(names):
        sub = df[df["state"] == k]["D"]
        rows.append(
            {
                "true_state": name,
                "n_days": len(sub),
                "mean_D": float(sub.mean()),
                "ann_sharpe_D": float(sub.mean() / sub.std(ddof=1) * np.sqrt(TRADING_DAYS)),
            }
        )
    return pd.DataFrame(rows)


def proxy_auc(proxy: pd.Series, flag: pd.Series) -> float:
    """P(proxy on a flagged day > proxy on an unflagged day) -- rank-based recovery score; 0.5 = chance."""
    df = pd.DataFrame({"p": proxy, "f": flag}).dropna()
    r = df["p"].rank()
    n1 = int(df["f"].sum())
    n0 = len(df) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((r[df["f"].astype(bool)].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def state_recovery(proxies: pd.DataFrame, market_states: pd.Series, names: tuple[str, ...]) -> pd.DataFrame:
    """How well each observable proxy separates the known states (AUC; slow vs rest on vr_long,
    rushed vs rest on -vr_short). Only meaningful for scenarios with the 3 regimes."""
    rows = []
    if "slow" in names:
        rows.append(
            {"target": "slow vs rest", "proxy": "vr_long", "auc": proxy_auc(proxies["vr_long"], market_states == names.index("slow"))}
        )
    if "rushed" in names:
        rows.append(
            {
                "target": "rushed vs rest",
                "proxy": "-vr_short",
                "auc": proxy_auc(-proxies["vr_short"], market_states == names.index("rushed")),
            }
        )
    return pd.DataFrame(rows)
