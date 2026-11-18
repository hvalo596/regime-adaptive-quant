"""Step 2 of the experiment doc on real (or fallback) panels: does D = risk-scaled(mom) - risk-scaled(rev) differ
across observable-state bins, beyond what a no-regime world produces?

What is computed per proxy (VR short/long + the four DRAFT Kai dimensions):
  1. high-bin minus low-bin mean D (labels from expanding terciles, matched with next-day D), with
     a) stationary block-bootstrap CI over days (95% and Bonferroni-adjusted for the number of primary tests),
     b) segment-level test: mean D per contiguous bin segment (>= min_segment_len days) and a bootstrap over
        SEGMENTS, the honest effective sample size (Kai: ~ a dozen independent high-risk episodes);
  2. two nulls where possible:
     a) circular-shift null: labels shifted in time against D by a random lag (keeps label persistence and the
        autocorrelation of D, breaks their association);
     b) pipeline-level "no regime beyond ~block length" null: resample the whole panel in blocks (joint across
        assets), rerun legs -> D -> proxies -> bins and recompute the statistic; family-wise p via max |z|;
  3. robustness: exclude days next to limit-locked proxies, sub-period halves, block-length sensitivity.
Pre-registered sign (DRAFT, written before any real-data run, mechanism in docs/regime-identification-why.md):
  vr_short, vr_long : D increases (VR>1 favours momentum)           -> +1
  sys_level, sys_share : D decreases (panic/liquidity state, reversal paid)  -> -1
  idio_level, idio_conc: D increases (information shocks, reversal catches falling knives) -> +1
The Kai-dimension signs are the weakest part of the draft; a wrong-sign significant result is reported, not hidden.
Decision rule (draft, to be confirmed by the user): expected-side CI excludes 0 AND both extreme bins have >=
`min_segments_per_bin` segments. Cost-exceedance is reported separately (needs a per-switch cost model).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import build_legs
from .benchmarks import spread_d
from .config import CostParams, InferenceParams, ProxyParams, StrategyParams
from .diagnostics import align_next_day, conditional_table, count_segments, expanding_tercile_bins, state_proxies
from .inference import group_mean_diff_ci, stationary_bootstrap_indices
from .kai_dims import DIM_NAMES, kai_dims

EXPECTED_SIGN = {
    "vr_short": +1, "vr_long": +1,
    "sys_level": -1, "sys_share": -1,
    "idio_level": +1, "idio_conc": +1,
}


@dataclass(frozen=True)
class ExistenceParams:
    n_boot: int = 1000
    n_shift: int = 2000
    n_panel_null: int = 100
    null_mean_block: int = 20
    block_lens: tuple[int, ...] = (10, 20, 60)
    min_assets: int = 5
    kai_window: int = 60
    seed: int = 7


@dataclass
class TrialLedger:
    """Counts primary hypothesis tests (proxy x parameter set x universe) for multiple-testing accounting."""

    rows: list[dict] = field(default_factory=list)

    def add(self, name: str, **info) -> None:
        self.rows.append({"trial": name, **info})

    @property
    def n(self) -> int:
        return len(self.rows)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def compute_proxies(returns: pd.DataFrame, pp: ProxyParams, ep: ExistenceParams) -> pd.DataFrame:
    vr = state_proxies(returns, pp, min_assets=ep.min_assets)
    kd = kai_dims(returns, window=ep.kai_window, min_assets=ep.min_assets)
    return pd.concat([vr, kd[list(DIM_NAMES)]], axis=1)


def compute_d(returns: pd.DataFrame, sp: StrategyParams, cp: CostParams, roll_mask=None) -> tuple[pd.Series, pd.Series, dict]:
    legs = build_legs(returns, sp, cp, roll_mask, nan_when_flat=True)
    return spread_d(legs, sp, net=True), spread_d(legs, sp, net=False), legs


def _ci_q(draws: np.ndarray, level: float) -> tuple[float, float]:
    a = (1 - level) / 2
    return float(np.quantile(draws, a)), float(np.quantile(draws, 1 - a))


def segment_level_test(
    df: pd.DataFrame, rng: np.random.Generator, min_len: int, n_boot: int, level: float
) -> dict:
    """Difference of mean-of-segment-means (high tercile minus low tercile), bootstrap over segments."""
    def seg_means(b: float) -> np.ndarray:
        lab = (df["bin"] == b).to_numpy()
        d = df["D"].to_numpy()
        out, start = [], None
        for i, v in enumerate(np.r_[lab, False]):
            if v and start is None:
                start = i
            elif not v and start is not None:
                if i - start >= min_len:
                    out.append(float(np.nanmean(d[start:i])))
                start = None
        return np.array(out)

    hi, lo = seg_means(2.0), seg_means(0.0)
    res = {"seg_n_high": len(hi), "seg_n_low": len(lo), "seg_diff": np.nan, "seg_ci_lo": np.nan, "seg_ci_hi": np.nan}
    if len(hi) < 2 or len(lo) < 2:
        return res
    boot = rng.choice(hi, (n_boot, len(hi))).mean(axis=1) - rng.choice(lo, (n_boot, len(lo))).mean(axis=1)
    lo_ci, hi_ci = _ci_q(boot, level)
    res.update(seg_diff=float(hi.mean() - lo.mean()), seg_ci_lo=lo_ci, seg_ci_hi=hi_ci)
    return res


def circular_shift_null(
    d: np.ndarray, bins: np.ndarray, n_shift: int, rng: np.random.Generator, min_shift: int
) -> np.ndarray:
    """Null draws of (mean D | high) - (mean D | low) with the label series circularly shifted against D."""
    n = len(d)
    if n < 4 * min_shift:
        return np.array([])
    shifts = rng.integers(min_shift, n - min_shift, n_shift)
    hi, lo = bins == 2.0, bins == 0.0
    out = np.empty(n_shift)
    for j, s in enumerate(shifts):
        h, l = np.roll(hi, s), np.roll(lo, s)
        out[j] = d[h].mean() - d[l].mean() if h.any() and l.any() else np.nan
    return out[np.isfinite(out)]


def _passes(sign: int, diff: float, lo: float, hi: float, seg_ok: bool) -> bool:
    if not (np.isfinite(lo) and np.isfinite(hi)) or not seg_ok:
        return False
    return (lo > 0) if sign > 0 else (hi < 0)


def existence_row(
    name: str,
    proxy: pd.Series,
    d: pd.Series,
    ip: InferenceParams,
    ep: ExistenceParams,
    pp: ProxyParams,
    n_primary: int,
    rng: np.random.Generator,
    exclude: pd.Series | None = None,
    mean_block: int | None = None,
) -> dict:
    sign = EXPECTED_SIGN.get(name, 0)
    bins = expanding_tercile_bins(proxy, pp.bin_min_obs)
    df = align_next_day(bins, d)
    if exclude is not None:
        df = df[~exclude.reindex(df.index).fillna(False).to_numpy()]
    x, bb = df["D"].to_numpy(), df["bin"].to_numpy()
    hi, lo = bb == 2.0, bb == 0.0
    base = {"proxy": name, "expected_sign": sign, "n_days": len(df)}
    if hi.sum() < 20 or lo.sum() < 20:
        return {**base, "diff": np.nan, "verdict": "insufficient data"}
    mb = mean_block or ip.mean_block
    adj_level = 1 - (1 - ip.ci_level) / max(n_primary, 1)
    idx = stationary_bootstrap_indices(len(x), mb, ep.n_boot, rng)
    xb, hb, lb = x[idx], hi[idx], lo[idx]
    with np.errstate(invalid="ignore", divide="ignore"):
        diffs = (xb * hb).sum(1) / hb.sum(1) - (xb * lb).sum(1) / lb.sum(1)
    diffs = diffs[np.isfinite(diffs)]
    diff = float(x[hi].mean() - x[lo].mean())
    ci = _ci_q(diffs, ip.ci_level)
    ci_adj = _ci_q(diffs, adj_level)
    seg = segment_level_test(df, rng, ip.min_segment_len, ep.n_boot, ip.ci_level)
    seg_hi = count_segments(df["bin"], 2.0, ip.min_segment_len)
    seg_lo = count_segments(df["bin"], 0.0, ip.min_segment_len)
    seg_ok = min(seg_hi, seg_lo) >= ip.min_segments_per_bin
    null = circular_shift_null(x, bb, ep.n_shift, rng, min_shift=max(250, 4 * mb))
    p_two = float((1 + (np.abs(null) >= abs(diff)).sum()) / (1 + len(null))) if len(null) else np.nan
    p_one = np.nan
    if len(null) and sign != 0:
        p_one = float((1 + ((sign * null) >= sign * diff).sum()) / (1 + len(null)))
    pass_unadj = _passes(sign, diff, *ci, seg_ok)
    pass_adj = _passes(sign, diff, *ci_adj, seg_ok)
    wrong_sig = bool(sign != 0 and ((sign > 0 and ci[1] < 0) or (sign < 0 and ci[0] > 0)))
    verdict = "pass (adj)" if pass_adj else "pass (unadj only)" if pass_unadj else "wrong-direction significant" if wrong_sig else "fail"
    return {
        **base,
        "diff": diff, "ci_lo": ci[0], "ci_hi": ci[1], "ci_adj_lo": ci_adj[0], "ci_adj_hi": ci_adj[1],
        "mean_block": mb, "adj_level": adj_level,
        "seg_high": seg_hi, "seg_low": seg_lo, "seg_ok": seg_ok, **{k: v for k, v in seg.items() if k.startswith("seg_") and k not in ("seg_n_high", "seg_n_low")},
        "shift_p_two_sided": p_two, "shift_p_expected_side": p_one,
        "wrong_direction_significant": wrong_sig, "pass_unadj": pass_unadj, "pass_adj": pass_adj, "verdict": verdict,
    }


def panel_null_stats(
    returns: pd.DataFrame,
    roll_mask: pd.DataFrame | None,
    sp: StrategyParams,
    cp: CostParams,
    pp: ProxyParams,
    ep: ExistenceParams,
    n_rep: int,
    min_obs: int | None = None,
) -> pd.DataFrame:
    """Pipeline-level null: block-resample whole days jointly across assets, rerun everything, return the
    high-minus-low D difference per proxy per replicate (rows = replicates)."""
    rng = np.random.default_rng(ep.seed + 101)
    n = len(returns)
    idx = stationary_bootstrap_indices(n, ep.null_mean_block, n_rep, rng)
    fake_dates = pd.bdate_range("2000-01-03", periods=n)
    rows = []
    for b in range(n_rep):
        r = returns.iloc[idx[b]].copy()
        r.index = fake_dates
        rm = None
        if roll_mask is not None:
            rm = roll_mask.iloc[idx[b]].copy()
            rm.index = fake_dates
        d_net, _, _ = compute_d(r, sp, cp, rm)
        prox = compute_proxies(r, pp, ep)
        row = {}
        for name in prox.columns:
            bins = expanding_tercile_bins(prox[name], min_obs or pp.bin_min_obs)
            df = align_next_day(bins, d_net)
            hi, lo = df["bin"] == 2.0, df["bin"] == 0.0
            row[name] = float(df.loc[hi, "D"].mean() - df.loc[lo, "D"].mean()) if hi.sum() > 20 and lo.sum() > 20 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def panel_null_pvalues(observed: dict[str, float], null: pd.DataFrame) -> pd.DataFrame:
    """Per-proxy two-sided and expected-side p-values, plus family-wise p from max |z| (z = diff / null sd)."""
    sd = null.std(ddof=1)
    zmax_null = (null.abs() / sd).max(axis=1)
    rows = []
    for name, obs in observed.items():
        if name not in null or not np.isfinite(obs):
            continue
        col = null[name].dropna()
        sign = EXPECTED_SIGN.get(name, 0)
        z_obs = abs(obs) / sd[name]
        rows.append(
            {
                "proxy": name, "observed_diff": obs, "null_mean": float(col.mean()), "null_sd": float(sd[name]),
                "z": float(obs / sd[name]), "n_null": len(col),
                "p_two_sided": float((1 + (col.abs() >= abs(obs)).sum()) / (1 + len(col))),
                "p_expected_side": float((1 + ((sign * col) >= sign * obs).sum()) / (1 + len(col))) if sign else np.nan,
                "p_familywise_maxz": float((1 + (zmax_null >= z_obs).sum()) / (1 + len(zmax_null))),
            }
        )
    return pd.DataFrame(rows)


def limit_adjacent_mask(limit_locked: pd.DataFrame) -> pd.Series:
    """True on day t if any asset is limit-locked (proxy) on t or t-1."""
    any_lock = limit_locked.any(axis=1)
    return (any_lock | any_lock.shift(1, fill_value=False)).rename("limit_adjacent")


def conditional_tables(proxies: pd.DataFrame, d: pd.Series, pp: ProxyParams, ip: InferenceParams) -> pd.DataFrame:
    parts = []
    for name in proxies.columns:
        if name == "n_assets":
            continue
        bins = expanding_tercile_bins(proxies[name], pp.bin_min_obs)
        parts.append(conditional_table(align_next_day(bins, d), name, ip))
    return pd.concat(parts, ignore_index=True)
