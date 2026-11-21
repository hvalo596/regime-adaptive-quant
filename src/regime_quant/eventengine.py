"""Day-by-day (streaming) re-implementation of the leg construction and the state-selected portfolio.

It shares NO code with backtest.py: it keeps explicit histories, sees one day of returns at a time, and can therefore not
look ahead by construction. `reconcile` runs both on the same inputs and reports the largest daily difference
(research doc step 1: two implementations, reconciled day by day).
"""

from __future__ import annotations

import numpy as np

from .config import TRADING_DAYS, CostParams, LegSpec, StateParams


class _LegStream:
    def __init__(self, spec: LegSpec, n_assets: int, T: int, sp: StateParams):
        self.spec, self.sp = spec, sp
        self.sig_hist = np.full((T, n_assets), np.nan)  # daily sign signals (after the +-1 of the leg kind)
        self.g_hist = np.full(T, np.nan)  # unscaled leg pnl realised on each day
        self.prev_unit = np.zeros(n_assets)  # unscaled weights decided at the previous close

    def update(self, t: int, rt_hist: np.ndarray, r_t: np.ndarray, vol_t: np.ndarray) -> tuple[np.ndarray, float]:
        sp, spec = self.sp, self.spec
        N = len(r_t)
        if t >= 1 and self._had_position:
            self.g_hist[t] = float(np.sum(self.prev_unit * np.nan_to_num(r_t, nan=0.0)))
        else:
            self.g_hist[t] = np.nan
        sig = np.full(N, np.nan)
        if t + 1 >= spec.L:
            win = rt_hist[t + 1 - spec.L : t + 1]
            ok = ~np.isnan(win).any(axis=0)
            sig[ok] = np.sign(win[:, ok].sum(axis=0))
        if spec.kind == "rev":
            sig = -sig
        self.sig_hist[t] = sig
        pos = np.full(N, np.nan)
        lo, hi = t - spec.gap - spec.H + 1, t - spec.gap
        if lo >= 0:
            w = self.sig_hist[lo : hi + 1]
            ok = ~np.isnan(w).any(axis=0)
            pos[ok] = w[:, ok].mean(axis=0)
        live = ~np.isnan(pos) & ~np.isnan(vol_t) & (vol_t > 0)
        unit = np.zeros(N)
        n = int(live.sum())
        if n:
            unit[live] = pos[live] / vol_t[live] / n
        self._had_position = n > 0
        self.prev_unit = unit
        gwin = self.g_hist[t + 1 - sp.leg_vol_window : t + 1] if t + 1 >= sp.leg_vol_window else None
        if gwin is not None and not np.isnan(gwin).any():
            sd = float(np.sqrt(np.mean(gwin**2)))
            target = sp.target_ann_vol / np.sqrt(TRADING_DAYS)
            scale = min(target / sd, 10.0) if sd > 0 else np.nan
        else:
            scale = np.nan
        return unit, scale

    _had_position = False


def run_event_driven(
    ret: np.ndarray,
    mom: LegSpec,
    rev: LegSpec,
    s: np.ndarray,
    kappa: np.ndarray,
    excl: np.ndarray,
    sp: StateParams = StateParams(),
    cost: CostParams = CostParams(),
) -> dict:
    T, N = ret.shape
    rt_hist = np.full((T, N), np.nan)
    r2 = np.full((T, N), np.nan)
    legs = {"mom": _LegStream(mom, N, T, sp), "rev": _LegStream(rev, N, T, sp)}
    W_prev = np.zeros(N)
    gross = np.full(T, np.nan)
    cost_arr = np.zeros(T)
    x_mom = np.full(T, np.nan)
    x_rev = np.full(T, np.nan)
    W_hist = np.zeros((T, N))
    W_mom_prev = np.zeros(N)
    W_rev_prev = np.zeros(N)
    for t in range(T):
        r_t = ret[t]
        # realise day t on the weights decided at the close of t-1
        if t >= 1:
            gross[t - 1] = float(np.sum(W_prev * np.nan_to_num(r_t, nan=0.0)))
            x_mom[t - 1] = float(np.sum(W_mom_prev * np.nan_to_num(r_t, nan=0.0)))
            x_rev[t - 1] = float(np.sum(W_rev_prev * np.nan_to_num(r_t, nan=0.0)))
        r2[t] = r_t**2
        # standardised return uses the 60 days up to t-1 only
        if t >= sp.vol_window:
            prev = r2[t - sp.vol_window : t]
            ok = ~np.isnan(prev).any(axis=0)
            sd = np.full(N, np.nan)
            sd[ok] = np.sqrt(prev[:, ok].mean(axis=0))
            with np.errstate(invalid="ignore", divide="ignore"):
                z = np.clip(r_t / sd, -sp.clip, sp.clip)
            z[~np.isfinite(z)] = np.nan
            rt_hist[t] = z
        # ex-ante vol through t for sizing
        vol_t = np.full(N, np.nan)
        if t + 1 >= sp.vol_window:
            cur = r2[t + 1 - sp.vol_window : t + 1]
            ok = ~np.isnan(cur).any(axis=0)
            vol_t[ok] = np.sqrt(cur[:, ok].mean(axis=0))
        out = {}
        for name, lg in legs.items():
            out[name] = lg.update(t, rt_hist, r_t, vol_t)
        (um, sm), (ur, sr) = out["mom"], out["rev"]
        wm = um * (0.0 if np.isnan(sm) else sm)
        wr = ur * (0.0 if np.isnan(sr) else sr)
        W_mom_prev, W_rev_prev = wm, wr
        st = s[t]
        if np.isnan(st):
            W = np.zeros(N)
        else:
            wr_eff = np.where(excl[t], 0.0, wr)
            W = kappa[t] * ((1 + st) / 2.0 * wm + (1 - st) / 2.0 * wr_eff)
        unit_cost = cost.fee_bps / 1e4 + cost.slip_vol_frac * np.nan_to_num(vol_t, nan=0.0)
        cost_arr[t] = float(np.sum(np.abs(W - W_prev) * unit_cost))
        W_prev = W
        W_hist[t] = W
    gross[-1] = np.nan
    x_mom[-1] = np.nan
    x_rev[-1] = np.nan
    # legs report NaN where the leg scale is undefined
    return {"gross_next": gross, "cost_next": cost_arr, "weights": W_hist, "x_mom_next": x_mom, "x_rev_next": x_rev}


def reconcile(ret, mom, rev, s, kappa, excl, sp: StateParams = StateParams(), cost: CostParams = CostParams()) -> dict:
    """Max abs daily difference between the vectorised engine and the streaming engine (gross, cost, weights, leg returns)."""
    from .backtest import build_legs, run_weights, state_weights

    ev = run_event_driven(ret, mom, rev, s, kappa, excl, sp, cost)
    legs = build_legs(ret, mom, rev, sp)
    W = state_weights(legs, s, kappa, excl)
    pf = run_weights(ret, W, legs.vol, cost)

    def md(a, b):
        ok = np.isfinite(a) & np.isfinite(b)
        return float(np.max(np.abs(a[ok] - b[ok]))) if ok.any() else float("nan"), int(ok.sum())

    x_m = np.where(np.isfinite(legs.mom.scale), legs.mom.x_next, np.nan)
    x_r = np.where(np.isfinite(legs.rev.scale), legs.rev.x_next, np.nan)
    res = {}
    res["gross_max_abs_diff"], res["gross_n"] = md(pf.gross_next, ev["gross_next"])
    res["cost_max_abs_diff"], res["cost_n"] = md(pf.cost_next, ev["cost_next"])
    res["x_mom_max_abs_diff"], _ = md(x_m, ev["x_mom_next"])
    res["x_rev_max_abs_diff"], _ = md(x_r, ev["x_rev_next"])
    res["weights_max_abs_diff"] = float(np.max(np.abs(pf.weights - ev["weights"])))
    res["gross_scale"] = float(np.nanmax(np.abs(pf.gross_next)))
    return res
