"""Step 3: can the state be recognised in time? (doc state-construction 4.6; experiment doc step 3)

Layers, each must justify its extra complexity over the previous one:
  rule baseline     the step-2 hysteresis on tau (not re-implemented here)
  hmm / hsmm        two-state chain per crowd (slow, rushed) on DAILY increments z_t of the strategy-matched products
                    (not on the rolling rho_hat, whose overlap would manufacture persistence), Gaussian or Student-t
                    emissions, geometric (sticky HMM) or negative-binomial (HSMM, r phases) sojourn
  change points     Bayesian online change-point detector on the same increments (number of states not preset)
Only FILTERED probabilities are produced (smoothing / Viterbi use the future). Parameters are re-estimated on an expanding window
every `refit_every` days from data up to the refit date only; the two states are ordered by their mean, so labels cannot swap
(degenerate fits are counted instead).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numba import njit
from scipy.optimize import minimize
from scipy.special import gammaln

from .config import LegSpec, kappa_LH
from .rolling import expanding_window_mean, roll_count, roll_sum, shift
from .statevars import mean_sq_corr


# ------------------------------------------------------------------------------------------------ daily increments


@dataclass
class Increments:
    z: np.ndarray  # (T,) daily strategy-matched product, mean ~ rho (slow chain) or -rho (rushed chain) of the current crowd composition
    sig: np.ndarray  # (T,) model scale sqrt(kappa / N_eff_t)
    n_use: np.ndarray
    n_eff: np.ndarray
    spec: LegSpec


def increments(rt: np.ndarray, spec: LegSpec, rho2_bar: np.ndarray | None = None, min_assets: int = 5, demean_window: int = 250, thin: bool = True) -> Increments:
    """z_u = sum_i Xd_{i,u-g-H} Yd_{i,u} / n_u with self-normalised window sums X = sum r~ / sqrt(sum r~^2): the pair completed on day u (known at the close of u), with X, Y de-meaned by the
    asset's own trailing 250-day mean (lagged), so a drift does not enter. E[z] ~ rho of the current crowd composition.
    thin=True (default): overlapping pairs make the daily noise of z an MA(min(L,H)-1) process, which any two-state model reads as short states.
    Observations are therefore BLOCK MEANS of the last k = L+H+gap daily z values, taken once every k days (global index, causal): adjacent blocks share
    almost no overlap and every day is used. Exact variance of a block mean: v_k / N_eff with v_k = (k + 2 sum_j (k-j) c_j) / k^2, c_j = (L-j)^+ (H-j)^+ / (L H).
    The filter lets the state evolve on the other days. thin=False keeps every day with the quasi-likelihood variance kappa / N_eff."""
    L, H, g = spec.L, spec.H, spec.gap
    valid = ~np.isnan(rt)
    rt2 = np.where(valid, rt**2, np.nan)
    # self-normalised window sums: divide by the root of the window's own sum of squares, so a volatility burst that the lagged 60-day
    # standardisation did not absorb does not inflate z (X/sqrt(S_L) and Y/sqrt(S_H) have unit variance under the null whatever the vol level)
    SL = np.where(roll_count(valid, L) >= L, roll_sum(np.nan_to_num(rt2), L), np.nan)
    SH = np.where(roll_count(valid, H) >= H, roll_sum(np.nan_to_num(rt2), H), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        X = np.where(roll_count(valid, L) >= L, roll_sum(rt, L) / np.sqrt(SL), np.nan)
        Y = np.where(roll_count(valid, H) >= H, roll_sum(rt, H) / np.sqrt(SH), np.nan)
    Xu = shift(X, g + H)
    mx = expanding_window_mean(Xu, demean_window, 100, lag=1)
    my = expanding_window_mean(Y, demean_window, 100, lag=1)
    pair = ~np.isnan(Xu) & ~np.isnan(Y) & ~np.isnan(mx) & ~np.isnan(my)
    prod = np.where(pair, (Xu - mx) * (Y - my), 0.0)
    n = pair.sum(axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = prod.sum(axis=1) / n
    z[n < min_assets] = np.nan
    if spec.kind == "rev":
        z = -z  # so that the high-mean state is the crowd being present for BOTH chains (R = -rho)
    if rho2_bar is None:
        rho2_bar, _ = mean_sq_corr(rt, max(spec.W, 40), min_valid=min(min_assets, 5)) if rt.shape[1] > 1 else (np.zeros(len(rt)), None)
    with np.errstate(invalid="ignore", divide="ignore"):
        n_eff = n / (1.0 + (n - 1.0) * np.nan_to_num(rho2_bar, nan=0.0))
    if thin:
        k = L + H + g
        c = [max(L - j, 0) * max(H - j, 0) / (L * H) for j in range(1, min(L, H))]
        v_k = (k + 2 * sum((k - j) * cj for j, cj in zip(range(1, min(L, H)), c))) / k**2
        zv = np.isfinite(z)
        zs = np.where(zv, z, 0.0)
        cnt = roll_count(zv, k)
        zb = np.where(cnt >= k, roll_sum(zs, k) / k, np.nan)
        off = (np.arange(len(z)) % k) != 0
        z = np.where(off, np.nan, zb)
        with np.errstate(invalid="ignore", divide="ignore"):
            sig = np.sqrt(v_k / n_eff)
    else:
        with np.errstate(invalid="ignore", divide="ignore"):
            sig = np.sqrt(kappa_LH(L, H) / n_eff)
    sig[~np.isfinite(sig)] = np.nan
    return Increments(z, sig, n, n_eff, spec)


# ------------------------------------------------------------------------------------------------ forward filter


@njit(cache=True)
def forward_filter(logB, A, tv, pi0):
    """Normalised forward recursion. logB (T,K) log emission densities, A (K,K) or (T,K,K) when tv, pi0 (K). NaN rows of logB are
    'no observation' days (the state just evolves). Returns filtered probabilities (T,K) and the log-likelihood."""
    T, K = logB.shape
    out = np.zeros((T, K))
    ll = 0.0
    p = pi0.copy()
    for t in range(T):
        Am = A[t] if tv else A[0]
        q = np.zeros(K)
        for j in range(K):
            s = 0.0
            for i in range(K):
                s += p[i] * Am[i, j]
            q[j] = s
        if not np.isnan(logB[t, 0]):
            m = logB[t, 0]
            for j in range(1, K):
                if logB[t, j] > m:
                    m = logB[t, j]
            tot = 0.0
            for j in range(K):
                q[j] *= np.exp(logB[t, j] - m)
                tot += q[j]
            if tot <= 0 or not np.isfinite(tot):
                tot = 1e-300
            ll += np.log(tot) + m
            for j in range(K):
                q[j] /= tot
        for j in range(K):
            out[t, j] = q[j]
        p = q
    return out, ll


def _logdens(z, mu, scale, dist, nu):
    u = (z - mu) / scale
    if dist == "gauss":
        return -0.5 * u * u - np.log(scale) - 0.5 * np.log(2 * np.pi)
    c = gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(nu * np.pi)
    return c - np.log(scale) - (nu + 1) / 2 * np.log1p(u * u / nu)


def _sig_(x):
    return 1.0 / (1.0 + np.exp(-x))


@dataclass(frozen=True)
class ChainSpec:
    kind: str = "hmm"  # "hmm" | "hsmm"
    dist: str = "t"  # "t" | "gauss"
    nu: float = 5.0
    phases: int = 3  # HSMM sojourn ~ NegBin(phases, q)
    covariate: bool = False  # R-chain only: logistic entry probability with an exogenous event covariate
    min_sojourn: float = 1.0  # stickiness: mean sojourn >= this (days). Rolling filters use 2(L+H-1): a state shorter than the MA overlap of the increments cannot be told from noise


def build_system(theta: np.ndarray, z: np.ndarray, sig: np.ndarray, cs: ChainSpec, x: np.ndarray | None = None):  # noqa: C901
    """theta = [mu0, log(mu1-mu0), a0, a1, log c (, beta)].  a_s: sojourn parameter of state s
    hmm : mean sojourn = min_sojourn + exp(a_s), P(stay) = 1 - 1/sojourn      hsmm: mean sojourn = max(min_sojourn, phases) + exp(a_s)
    Returns logB (T,K), A, tv, macro (K,) state index of every phase."""
    mu0, mu1 = theta[0], theta[0] + np.exp(theta[1])
    c = np.exp(theta[4])
    scale = c * sig
    lb0 = _logdens(z, mu0, scale, cs.dist, cs.nu)
    lb1 = _logdens(z, mu1, scale, cs.dist, cs.nu)
    if cs.kind == "hmm":
        T = len(z)
        m0_, m1_ = cs.min_sojourn + np.exp(theta[2]), cs.min_sojourn + np.exp(theta[3])
        stay = [1 - 1 / max(m0_, 1.0001), 1 - 1 / max(m1_, 1.0001)]
        if cs.covariate and x is not None:
            enter = _sig_(theta[2] + theta[5] * np.nan_to_num(x))  # P(0 -> 1) = logistic(alpha + beta x); `theta[2]` is alpha here
            A = np.zeros((T, 2, 2))
            A[:, 0, 1] = enter
            A[:, 0, 0] = 1 - enter
            A[:, 1, 1] = stay[1]
            A[:, 1, 0] = 1 - stay[1]
            tv = True
        else:
            A = np.array([[[stay[0], 1 - stay[0]], [1 - stay[1], stay[1]]]])
            tv = False
        logB = np.stack([lb0, lb1], axis=1)
        return logB, A, tv, np.array([0, 1])
    r = cs.phases
    q = [r / (max(cs.min_sojourn, r) + np.exp(theta[2])), r / (max(cs.min_sojourn, r) + np.exp(theta[3]))]
    K = 2 * r
    A = np.zeros((K, K))
    for s in (0, 1):
        for j in range(r):
            i = s * r + j
            if j < r - 1:
                A[i, i] = 1 - q[s]
                A[i, i + 1] = q[s]
            else:
                A[i, i] = 1 - q[s]
                A[i, (1 - s) * r] = q[s]
    logB = np.stack([lb0] * r + [lb1] * r, axis=1)
    return logB, A[None], False, np.array([0] * r + [1] * r)


def _stationary(A2):
    w, v = np.linalg.eig(A2.T)
    k = np.argmin(np.abs(w - 1))
    p = np.real(v[:, k])
    return np.abs(p) / np.abs(p).sum()


def _pi0(theta, A, K, tv):
    Am = A[0]
    return _stationary(Am) if not tv else np.ones(K) / K


def neg_loglik(theta, z, sig, cs, x=None):
    if not np.all(np.isfinite(theta)) or abs(theta[4]) > 3 or theta[1] < -6 or theta[1] > 3:
        return 1e12
    logB, A, tv, macro = build_system(theta, z, sig, cs, x)
    K = logB.shape[1]
    _, ll = forward_filter(logB, A, tv, _pi0(theta, A, K, tv))
    return -ll if np.isfinite(ll) else 1e12


@dataclass
class FitResult:
    theta: np.ndarray
    ll: float
    mu0: float
    mu1: float
    mean_sojourn0: float
    mean_sojourn1: float
    c: float
    degenerate: bool
    n: int
    spec: ChainSpec
    beta: float = np.nan


def _sojourn(theta, cs):
    base = max(cs.min_sojourn, cs.phases if cs.kind == "hsmm" else 1.0)
    return base + np.exp(theta[2]), base + np.exp(theta[3])


def fit_chain(z: np.ndarray, sig: np.ndarray, cs: ChainSpec, x: np.ndarray | None = None, seed: int = 0, theta_init: np.ndarray | None = None) -> FitResult:
    ok = np.isfinite(z) & np.isfinite(sig)
    i0 = int(np.flatnonzero(ok)[0])
    z, sig = z[i0:].copy(), sig[i0:].copy()
    xx = x[i0:] if x is not None else None
    zf = z[np.isfinite(z) & np.isfinite(sig)]
    sd = float(np.std(zf / sig[np.isfinite(z) & np.isfinite(sig)])) if len(zf) > 10 else 1.0
    med = float(np.median(zf))
    best = None
    k0 = 6 if (cs.covariate and cs.kind == "hmm") else 5
    starts = [(np.log(max(g_ * np.std(zf), 1e-3)), a0, a1) for g_ in (0.25, 0.5, 1.0, 1.5) for a0, a1 in ((np.log(40.0), np.log(25.0)), (np.log(200.0), np.log(100.0)))]
    inits = [None] * len(starts) + ([np.asarray(theta_init, dtype=float)] if theta_init is not None else [])
    for k_, init in enumerate(inits):
        if init is not None:
            th0 = list(init)
        else:
            d0, a0, a1 = starts[k_]
            th0 = [med - 0.3 * np.std(zf), d0, a0, a1, 0.0] + ([0.0] if k0 == 6 else [])
            if cs.covariate and cs.kind == "hmm":
                th0[2] = -3.0
        res = minimize(neg_loglik, th0, args=(z, sig, cs, xx), method="Nelder-Mead", options={"maxiter": 1200, "xatol": 1e-4, "fatol": 1e-5})
        res = minimize(neg_loglik, res.x, args=(z, sig, cs, xx), method="L-BFGS-B", bounds=[(-1, 1), (-6, 3), (-6, 9), (-6, 9), (-1.5, 1.5)] + ([(-5, 5)] if k0 == 6 else []))
        if best is None or res.fun < best.fun:
            best = res
    th = best.x
    m0, m1 = _sojourn(th, cs)
    mu0, mu1 = th[0], th[0] + np.exp(th[1])
    at_bound = (cs.kind == "hmm" and not cs.covariate) and (th[2] < -4.5 or th[3] < -4.5)  # sojourn pinned at the stickiness floor
    degenerate = bool((mu1 - mu0) < 0.25 * np.std(zf) or at_bound or th[2] > 8.5 or th[3] > 8.5)
    return FitResult(th, -best.fun, float(mu0), float(mu1), float(m0), float(m1), float(np.exp(th[4])), degenerate, int(len(zf)), cs, float(th[5]) if k0 == 6 else np.nan)


def fit_null(z: np.ndarray, sig: np.ndarray, cs: ChainSpec) -> float:
    """One-state (no-state) model: z = mu + c sig eps. Returns the maximised log-likelihood."""
    ok = np.isfinite(z) & np.isfinite(sig)
    z, sig = z[ok], sig[ok]

    def f(p):
        return -np.sum(_logdens(z, p[0], np.exp(p[1]) * sig, cs.dist, cs.nu))

    res = minimize(f, [float(np.mean(z)), 0.0], method="Nelder-Mead")
    return -float(res.fun)


# ------------------------------------------------------------------------------------------------ rolling filter


@dataclass
class RollingFilter:
    p: np.ndarray  # (T,) filtered P(state 1) (NaN before the first refit)
    fits: list = field(default_factory=list)  # (day index, FitResult)
    degenerate_share: float = np.nan
    p_guard: np.ndarray | None = None  # p with 0.5 (no information) in every epoch whose fit was flagged degenerate


def rolling_filter(inc: Increments, cs: ChainSpec = ChainSpec(), refit_every: int = 250, min_train: int = 500, x: np.ndarray | None = None) -> RollingFilter:
    """Causal filtered probability of the high-mean state. Parameters used on day t were estimated with data up to the last refit
    date <= t only; the filter state is carried across refits."""
    z, sig = inc.z, inc.sig
    T = len(z)
    ok = np.isfinite(z) & np.isfinite(sig)
    idx = np.flatnonzero(ok)
    p = np.full(T, np.nan)
    pg = np.full(T, np.nan)
    if len(idx) < max(min_train // 8, 20):
        return RollingFilter(p, p_guard=pg)
    first = idx[0]
    t = first + min_train
    if t >= T:
        return RollingFilter(p, p_guard=pg)
    fits = []
    while t < T:
        t_next = min(t + refit_every, T)
        fr = fit_chain(z[first:t], sig[first:t], cs, x[first:t] if x is not None else None)
        fits.append((t, fr))
        # parameters estimated on data < t, filter re-run from the first valid day up to t_next: the output on day u in [t, t_next)
        # uses data <= u and parameters fixed at t - 1, so nothing from the future enters
        logB, A, tv, macro = build_system(fr.theta, z[first:t_next], sig[first:t_next], cs, x[first:t_next] if x is not None else None)
        K = logB.shape[1]
        filt, _ = forward_filter(logB, A, tv, _pi0(fr.theta, A, K, tv))
        pr = filt[:, macro == 1].sum(axis=1)
        p[t:t_next] = pr[(t - first) : (t_next - first)]
        pg[t:t_next] = 0.5 if fr.degenerate else p[t:t_next]
        t = t_next
    deg = float(np.mean([f.degenerate for _, f in fits])) if fits else np.nan
    return RollingFilter(p, fits, deg, pg)


# ------------------------------------------------------------------------------------------------ change points


def bocpd(z: np.ndarray, sig: np.ndarray, hazard: float = 1 / 120.0, prior_sd: float = 0.15, max_run: int = 600) -> dict:
    """Bayesian online change-point detection (Adams & MacKay 2007) for a Gaussian mean with known (heteroscedastic) variance and a
    N(0, prior_sd^2) prior on the segment mean. Returns P(run length < 10) per day (change-point mass), the expected run length and
    the day-by-day predictive mean of the current segment (a causal 'state level')."""
    T = len(z)
    cp_mass = np.full(T, np.nan)
    exp_run = np.full(T, np.nan)
    level = np.full(T, np.nan)
    R = np.zeros(max_run + 1)
    R[0] = 1.0
    prec = np.full(max_run + 1, 1.0 / prior_sd**2)  # posterior precision of the segment mean per run length
    s_over = np.zeros(max_run + 1)  # sum of z/sig^2 per run length
    for t in range(T):
        zt, st = z[t], sig[t]
        if not (np.isfinite(zt) and np.isfinite(st)):
            continue
        var = st**2
        mean = s_over / prec
        pv = 1.0 / prec + var
        pred = np.exp(-0.5 * (zt - mean) ** 2 / pv) / np.sqrt(2 * np.pi * pv)
        growth = R * pred * (1 - hazard)
        cp = (R * pred * hazard).sum()
        Rn = np.empty_like(R)
        Rn[0] = cp
        Rn[1:] = growth[:-1]
        Rn[-1] += growth[-1]
        tot = Rn.sum()
        if tot <= 0 or not np.isfinite(tot):
            Rn = np.zeros_like(R)
            Rn[0] = 1.0
            tot = 1.0
        Rn /= tot
        new_prec = np.empty_like(prec)
        new_s = np.empty_like(s_over)
        new_prec[0], new_s[0] = 1.0 / prior_sd**2, 0.0
        new_prec[1:] = prec[:-1] + 1.0 / var
        new_s[1:] = s_over[:-1] + zt / var
        prec, s_over, R = new_prec, new_s, Rn
        cp_mass[t] = R[:10].sum()
        exp_run[t] = (R * np.arange(len(R))).sum()
        level[t] = (R * (s_over / prec)).sum()
    return {"cp_mass": cp_mass, "expected_run": exp_run, "level": level}


# ------------------------------------------------------------------------------------------------ soft state helpers


def entropy4(pm: np.ndarray, pr: np.ndarray) -> np.ndarray:
    """Entropy of the four-quadrant distribution (independent chains), in nats (max ln 4)."""
    out = np.zeros_like(pm)
    for a in (pm, 1 - pm):
        for b in (pr, 1 - pr):
            q = a * b
            with np.errstate(invalid="ignore", divide="ignore"):
                out = out - np.where(q > 0, q * np.log(q), 0.0)
    out[np.isnan(pm) | np.isnan(pr)] = np.nan
    return out


def soft_signal(pm: np.ndarray, pr: np.ndarray, penalise: bool = True) -> np.ndarray:
    """s_t = p^M - p^R (doc 4.6), optionally times (1 - H_t / ln 4)."""
    s = pm - pr
    if penalise:
        s = s * (1.0 - entropy4(pm, pr) / np.log(4.0))
    return s
