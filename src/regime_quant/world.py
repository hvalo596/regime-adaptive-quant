"""Synthetic world of docs/state-construction.md section 7: slow / rushed / informed / market-maker agents,
semi-Markov switching of the crowd composition, and the no-state controls N0, N1, N2, N2b, N3, N4.

Generation is written in terms of crowd composition (7.1, 7.2); the measurement code in statevars.py never sees these
parameters. Per asset i and day t:

  news           u = sqrt(c_m) beta_i g_t + sqrt(c_s) nu_sector + sqrt(rest) eta_i    (eta ~ unit-variance t_nu)
  slow traders   share s_t of the news is absorbed with persistence phi:  G_t = phi G_{t-1} + u_t,
                 return part  r^S_t = (1-s_t) u_t + s_t (1-phi_t) G_{t-1}   (equals the doc's  -s Delta G + news)
  rushed + MM    q_t = common wave zeta_t + idiosyncratic;  inventory B_t = a B_{t-1} + q_t;
                 return part  r^F_t = lambda (q_t - (1-a) B_{t-1})  = lambda * Delta B
  informed       permanent drift  +-z*sigma per day for d_I days before the public date (no reversal)
  vol            common and idiosyncratic stochastic vol multiply BOTH kernels (so N1 can scale them together)

Deviations from the doc text (recorded in docs/step1-result-report.md): (i) vol-neutral state parametrisation: the news
variance is rescaled so the daily return variance does not depend on (s, phi, f); a separate `vol_mult` per state adds
the realistic "Rushed = loud" co-movement when wanted; (ii) zeta_t is iid (a_zeta = 0) so the closed forms of 7.3 hold
exactly; persistence of crowd states comes from the semi-Markov state process; (iii) slow capital K_t is not simulated
(lambda_k is a state constant), the spiral feedback psi is off.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd
from numba import njit
from scipy.optimize import brentq, least_squares

STATES = ("I", "II", "III", "IV")
SECTORS = 5


# -------------------------------------------------------------------------------------- theory (doc 7.3)


def kernel(s: float, phi: float, f: float, a: float, K: int = 600) -> tuple[float, np.ndarray]:
    """Daily variance g0 and autocovariances g_1..g_K of the return (vol-neutral: slow part has unit variance, the fast
    part adds f/(1-f); the whole return is later multiplied by sqrt(1-f) so g0 = 1)."""
    k = np.arange(1, K + 1)
    g0s = (1 - s) ** 2 + s**2 * (1 - phi) / (1 + phi)
    su2 = 1.0 / g0s
    gs = su2 * s * (1 - phi) * phi ** (k - 1) * ((1 - s) + s * phi / (1 + phi))
    lam2 = f / (1 - f) * (1 + a) / 2.0 if f > 0 else 0.0
    gf = -lam2 * (1 - a) * a ** (k - 1) / (1 + a)
    g0 = 1.0 + 2.0 * lam2 / (1 + a)
    return g0, gs + gf


def rho_theory(L: int, H: int, g0: float, g: np.ndarray, gap: int = 0) -> float:
    """rho^(L,H) = Corr(X^(L), Y^(H)) from autocovariances (doc 3.3, trapezoid weights)."""
    lag = np.arange(1, L + 1)[:, None] + np.arange(1, H + 1)[None, :] - 1 + gap  # lag index (1-based) of each pair
    cov = g[lag - 1].sum()

    def var(x):
        kk = np.arange(1, x)
        return x * g0 + 2.0 * ((x - kk) * g[kk - 1]).sum()

    return float(cov / np.sqrt(max(var(L) * var(H), 1e-12)))


@dataclass(frozen=True)
class Theta:
    s: float = 0.0
    phi: float = 0.9
    f: float = 0.0
    a: float = 0.5
    vol_mult: float = 1.0

    def nets(self) -> dict:
        """Theoretical rho for every leg spec of the project (doc 7.3): M-B, M-A, R-A, R-B, R-B-gap (R = -rho)."""
        g0, g = kernel(self.s, self.phi, self.f, self.a)
        return {
            "M-B": rho_theory(20, 5, g0, g), "M-A": rho_theory(60, 20, g0, g),
            "R-A": -rho_theory(5, 3, g0, g), "R-B": -rho_theory(1, 1, g0, g), "R-B-gap": -rho_theory(1, 1, g0, g, gap=1),
        }


def solve_states(effect: float, phi: float = 0.9, a: float = 0.5, covol: bool = False) -> dict[str, Theta]:
    """State parameters such that, in each quadrant, the net strategy-matched correlations hit the planted effect:
    I: rho(20,5) = +effect;  II: -rho(5,3) = +effect;  III: both net;  IV: nothing."""
    vm = dict(I=1.0, II=1.5, III=1.25, IV=0.8) if covol else dict(I=1.0, II=1.0, III=1.0, IV=1.0)
    if effect <= 0:
        return {k: Theta(0.0, phi, 0.0, a, vm[k]) for k in STATES}

    def rm(s, f):
        g0, g = kernel(s, phi, f, a)
        return rho_theory(20, 5, g0, g)

    def rr(s, f):
        g0, g = kernel(s, phi, f, a)
        return -rho_theory(5, 3, g0, g)

    s_i = brentq(lambda s: rm(s, 0.0) - effect, 1e-6, 0.95)
    f_ii = brentq(lambda f: rr(0.0, f) - effect, 1e-6, 0.97)
    # State III needs the rushed core to beat the slow core's contamination of the short scale (doc 7.3); for large
    # effects no composition reaches both nets (max symmetric net ~0.12 here), so take the closest feasible point.
    best = None
    for s0 in (0.3, 0.6, 0.9):
        for f0 in (0.5, 0.8, 0.95):
            sol = least_squares(lambda z: [rm(*z) - effect, rr(*z) - effect], [s0, f0], bounds=([0.0, 0.0], [0.97, 0.97]))
            if best is None or sol.cost < best.cost:
                best = sol
    s_iii, f_iii = float(best.x[0]), float(best.x[1])
    return {
        "I": Theta(s_i, phi, 0.0, a, vm["I"]),
        "II": Theta(0.0, phi, f_ii, a, vm["II"]),
        "III": Theta(s_iii, phi, f_iii, a, vm["III"]),
        "IV": Theta(0.0, phi, 0.0, a, vm["IV"]),
    }


# -------------------------------------------------------------------------------------- spec


@dataclass(frozen=True)
class WorldSpec:
    kind: str = "regime"  # regime | N0 | N0z | N1 | N2 | N2b | N3 | N4 | informed
    n_assets: int = 40
    n_days: int = 2500
    burn: int = 600
    effect: float = 0.10
    phi: float = 0.9
    a: float = 0.5
    covol: bool = False
    mean_dwell: tuple[float, float, float, float] = (120.0, 20.0, 30.0, 120.0)  # I, II, III, IV
    dwell_disp: float = 3.0
    states_used: tuple = (0, 1, 2, 3)  # indices into (I, II, III, IV) the crowd may visit
    nu: float = 5.0
    c_m: float = 0.15
    c_s: float = 0.08
    w_fast_common: float = 0.5
    sv_phi: float = 0.985
    sv_sd: float = 0.30
    isv_phi: float = 0.97
    isv_sd: float = 0.25
    informed_per_year: float = 0.0
    informed_days: int = 10
    informed_z: float = 4.0
    public_burst_per_year: float = 0.0
    public_burst_days: int = 8
    public_burst_mult: float = 4.0
    n3_mu_sd: float = 0.05
    n3_rho: float = 0.998
    half_spread: float = 0.25  # N4, in units of daily sigma
    n1_sv_sd: float = 0.9
    n2_period: float = 60.0
    seed: int = 0


@dataclass
class World:
    ret: np.ndarray  # (T, N) observed close-to-close log returns
    close: np.ndarray  # observed close prices
    settle: np.ndarray | None
    volume: np.ndarray
    oi: np.ndarray
    amount: np.ndarray  # in units of 10k CNY, like Tushare
    quadrant: np.ndarray  # (T,) int 0..3 = I, II, III, IV
    delta_m: np.ndarray  # (T,) true slow-crowd indicator (I, III)
    delta_r: np.ndarray  # (T,) true rushed-crowd indicator (II, III)
    informed: np.ndarray  # (T, N) bool: informed trading active
    burst: np.ndarray  # (T, N) bool: public idiosyncratic burst
    zeta: np.ndarray  # (T,) common rushed wave
    vol_factor: np.ndarray  # (T,)
    sector: np.ndarray
    theta: dict
    spec: WorldSpec
    dates: pd.DatetimeIndex = field(default=None)
    risk_structure: np.ndarray | None = None


# -------------------------------------------------------------------------------------- core


@njit(cache=True)
def _core(u, q, s_t, phi_t, a_t, keep_t, drift):
    T, N = u.shape
    r = np.zeros((T, N))
    qs = np.zeros((T, N))
    G = np.zeros(N)
    B = np.zeros(N)
    for t in range(T):
        s, phi, a = s_t[t], phi_t[t], a_t[t]
        for i in range(N):
            slow_pull = s * (1.0 - phi) * G[i]
            rs = (1.0 - s) * u[t, i] + slow_pull
            rf = q[t, i] - (1.0 - a) * B[i]
            G[i] = phi * G[i] + u[t, i]
            B[i] = a * B[i] + q[t, i]
            r[t, i] = keep_t[t] * (rs + rf) + drift[t, i]
            qs[t, i] = slow_pull
    return r, qs


def _semi_markov(rng: np.random.Generator, T: int, mean_dwell, disp: float, k_states: int, start: int | None = None, allowed: tuple | None = None) -> np.ndarray:
    """Semi-Markov chain, durations 1 + NegBin(mean), jumps uniform over the other allowed states (zero diagonal)."""
    allowed = tuple(range(k_states)) if allowed is None else tuple(allowed)
    out = np.empty(T, dtype=np.int64)
    cur = int(rng.choice(allowed)) if start is None else start
    t = 0
    while t < T:
        m = max(mean_dwell[cur] - 1.0, 0.5)
        p = disp / (disp + m)
        d = 1 + int(rng.negative_binomial(disp, p))
        out[t : t + d] = cur
        t += d
        others = [k for k in allowed if k != cur]
        if others:
            cur = int(rng.choice(others))
    return out


def _ar1(rng: np.random.Generator, T: int, N: int, phi: float, sd_stat: float) -> np.ndarray:
    innov = rng.standard_normal((T, N)) * sd_stat * np.sqrt(1 - phi**2)
    x = np.empty((T, N))
    x[0] = rng.standard_normal(N) * sd_stat
    for t in range(1, T):
        x[t] = phi * x[t - 1] + innov[t]
    return x


def _unit_t(rng: np.random.Generator, shape, nu: float) -> np.ndarray:
    return rng.standard_t(nu, size=shape) * np.sqrt((nu - 2.0) / nu)


def generate(spec: WorldSpec) -> World:
    rng = np.random.default_rng(spec.seed)
    N, Tn = spec.n_assets, spec.n_days
    T = Tn + spec.burn
    kind = spec.kind
    sector = np.arange(N) % SECTORS
    beta = rng.uniform(0.6, 1.4, N)
    beta_f = rng.uniform(0.7, 1.3, N)
    sigma_i = rng.uniform(0.008, 0.025, N)

    theta = solve_states(spec.effect, spec.phi, spec.a, spec.covol)
    th_arr = {k: np.array([[theta[x].s, theta[x].phi, theta[x].f, theta[x].a, theta[x].vol_mult] for x in STATES][i]) for i, k in enumerate(STATES)}
    stationary_w = np.array(spec.mean_dwell) / sum(spec.mean_dwell)

    # ---- crowd composition path
    if kind in ("regime", "informed"):
        quad = _semi_markov(rng, T, spec.mean_dwell, spec.dwell_disp, 4, allowed=spec.states_used)
        par = np.stack([th_arr[STATES[k]] for k in quad])
    else:
        quad = np.full(T, 3, dtype=np.int64)
        base = (stationary_w[:, None] * np.stack([th_arr[k] for k in STATES])).sum(axis=0)
        if kind in ("N0z", "N3", "N4"):
            base = np.array([0.0, spec.phi, 0.0, spec.a, 1.0])
        par = np.tile(base, (T, 1))
        par[:, 4] = 1.0
    s_t, phi_t, f_t, a_t, vm_t = (par[:, j].copy() for j in range(5))

    # ---- shocks
    g = rng.standard_normal(T)
    nu_sec = rng.standard_normal((T, SECTORS))
    eta = _unit_t(rng, (T, N), spec.nu)
    cm = np.full((T, N), spec.c_m)
    risk_structure = np.zeros(T, dtype=np.int64)
    idio_mult = np.ones((T, N))
    if kind == "N2":
        rs = _semi_markov(rng, T, [spec.n2_period] * 3, 3.0, 3)
        risk_structure = rs
        cm = np.where((rs == 1)[:, None], 0.45, np.where((rs == 0)[:, None], 0.06, spec.c_m)) * np.ones((T, N))
        # regime 2: idiosyncratic variance concentrated on three assets (redrawn at each entry)
        t = 0
        while t < T:
            t1 = t
            while t1 < T and rs[t1] == rs[t]:
                t1 += 1
            if rs[t] == 2:
                pick = rng.choice(N, size=3, replace=False)
                idio_mult[t:t1][:, pick] = 3.0
            t = t1
    c_rest = np.clip(1.0 - cm * beta[None, :] ** 2 - spec.c_s, 0.05, None)
    u_raw = np.sqrt(cm) * beta[None, :] * g[:, None] + np.sqrt(spec.c_s) * nu_sec[:, sector] + np.sqrt(c_rest) * eta * idio_mult
    u_var = (cm * beta[None, :] ** 2 + spec.c_s + c_rest * idio_mult**2)
    u_raw = u_raw / np.sqrt(u_var)

    zeta = rng.standard_normal(T)
    eps = _unit_t(rng, (T, N), spec.nu)
    z_i = (beta_f[None, :] * np.sqrt(spec.w_fast_common) * zeta[:, None] + np.sqrt(1 - spec.w_fast_common * 1.0) * eps)
    z_i = z_i / np.sqrt(spec.w_fast_common * beta_f[None, :] ** 2 + (1 - spec.w_fast_common))

    sv_sd = spec.n1_sv_sd if kind == "N1" else spec.sv_sd
    h = _ar1(rng, T, 1, spec.sv_phi, sv_sd)[:, 0]
    hi = _ar1(rng, T, N, spec.isv_phi, spec.isv_sd)
    vol_factor = np.exp(h - 0.5 * sv_sd**2)
    vscale = sigma_i[None, :] * vol_factor[:, None] * np.exp(hi - 0.5 * spec.isv_sd**2) * vm_t[:, None]

    # ---- public bursts (N2b) and informed events
    burst = np.zeros((T, N), dtype=bool)
    informed = np.zeros((T, N), dtype=bool)
    drift = np.zeros((T, N))
    if spec.public_burst_per_year > 0:
        n_ev = rng.poisson(spec.public_burst_per_year * Tn / 252.0)
        for _ in range(n_ev):
            t0 = int(rng.integers(spec.burn, T - spec.public_burst_days))
            k = int(rng.integers(1, 3))
            for i in rng.choice(N, size=k, replace=False):
                burst[t0 : t0 + spec.public_burst_days, i] = True
        vscale = np.where(burst, vscale * spec.public_burst_mult, vscale)
    if spec.informed_per_year > 0:
        n_ev = rng.poisson(spec.informed_per_year * Tn / 252.0)
        for _ in range(n_ev):
            t0 = int(rng.integers(spec.burn, T - spec.informed_days))
            k = int(rng.integers(1, 3))
            sgn = rng.choice([-1.0, 1.0])
            for i in rng.choice(N, size=k, replace=False):
                informed[t0 : t0 + spec.informed_days, i] = True
                drift[t0 : t0 + spec.informed_days, i] += sgn * spec.informed_z * sigma_i[i] * vol_factor[t0 : t0 + spec.informed_days]

    # ---- state-dependent kernels
    g0s = (1 - s_t) ** 2 + s_t**2 * (1 - phi_t) / (1 + phi_t)
    u_sc = (1.0 / np.sqrt(g0s))[:, None] * vscale
    lam_q = np.sqrt(np.where(f_t > 0, f_t / np.maximum(1 - f_t, 1e-9) * (1 + a_t) / 2.0, 0.0))[:, None]
    q_sc = lam_q * vscale
    keep = np.sqrt(1.0 - f_t)
    r, q_slow = _core(u_raw * u_sc, z_i * q_sc, s_t, phi_t, a_t, keep, drift)

    # ---- N3: time-varying risk premium, no participants
    if kind == "N3":
        mu = _ar1(rng, T, N, spec.n3_rho, 1.0) * 0.7 + 0.714 * _ar1(rng, T, 1, spec.n3_rho, 1.0)
        r = r + mu * spec.n3_mu_sd * vscale

    # ---- volume / open interest (7.1): crowd trading intensities
    q_fast = (z_i * q_sc)
    q_inf = np.where(informed, spec.informed_z * sigma_i[None, :] * 1.0, 0.0)
    base_vol = rng.uniform(2.0, 8.0, N)[None, :]
    noise_vol = np.exp(0.35 * rng.standard_normal((T, N)))
    scale_unit = vscale / sigma_i[None, :]
    volume = base_vol * noise_vol * (1.0 + 1.0 * np.abs(q_slow) / sigma_i[None, :] + 1.0 * np.abs(q_fast) / sigma_i[None, :] + 2.0 * np.abs(q_inf) / sigma_i[None, :])
    d_oi = base_vol * (0.30 * np.abs(q_slow) / sigma_i[None, :] + 0.60 * np.abs(q_inf) / sigma_i[None, :] - 0.50 * np.abs(q_fast) / sigma_i[None, :] * (zeta < 0)[:, None]) + 0.05 * base_vol * rng.standard_normal((T, N))
    oi = np.maximum(base_vol * 20.0 + np.cumsum(d_oi, axis=0), base_vol * 2.0)

    # ---- prices; N4 microstructure
    logp = np.log(100.0) + np.cumsum(r, axis=0)
    settle = None
    if kind == "N4":
        h_i = spec.half_spread * sigma_i
        bounce = rng.choice([-1.0, 1.0], size=(T, N))
        obs = logp + h_i[None, :] * bounce
        K = 10
        prev = np.vstack([logp[:1] - r[:1], logp[:-1]])
        wn = rng.standard_normal((T, K, N)) * (vscale[:, None, :] / np.sqrt(K))
        wc = np.cumsum(wn, axis=1)
        bridge = wc - (np.arange(1, K + 1)[None, :, None] / K) * wc[:, -1:, :]
        path = prev[:, None, :] + (np.arange(1, K + 1)[None, :, None] / K) * (logp - prev)[:, None, :] + bridge
        settle = np.exp(path).mean(axis=1)
        logp = obs
    close = np.exp(logp)
    ret = np.diff(logp, axis=0, prepend=logp[:1] - 0.0)
    ret[0] = np.nan

    sl = slice(spec.burn, T)
    ret = ret[sl].copy()
    amount = volume * close * 10.0 / 1e4
    dates = pd.bdate_range("2012-01-02", periods=Tn)
    dm = np.isin(quad, [0, 2]).astype(float) if kind in ("regime", "informed") else np.zeros(T)
    dr = np.isin(quad, [1, 2]).astype(float) if kind in ("regime", "informed") else np.zeros(T)
    return World(
        ret=ret, close=close[sl], settle=None if settle is None else settle[sl], volume=volume[sl], oi=oi[sl], amount=amount[sl],
        quadrant=quad[sl], delta_m=dm[sl], delta_r=dr[sl], informed=informed[sl], burst=burst[sl], zeta=zeta[sl],
        vol_factor=vol_factor[sl], sector=sector, theta=theta, spec=spec, dates=dates, risk_structure=risk_structure[sl],
    )
