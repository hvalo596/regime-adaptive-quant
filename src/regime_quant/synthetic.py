"""Synthetic multi-asset futures-return generator with KNOWN regimes (and stateless nulls).

Model for asset i on day t, in regime s_t (a sticky Markov chain):

    r_it = m_it + n_it
    m_it = RHO_TREND * m_i,t-1 + trend_sd[s_t] * eps_it                (slow traders: persistent drift)
    n_it = ar1[s_t] * n_i,t-1 + sqrt(1-ar1^2) * vol[s_t] * u_it        (impatient traders: short-run rebound)
    u_it = sqrt(share[s_t]) * f_t + sqrt(1-share[s_t]) * z_it          (common vs idiosyncratic shock)

Financial reading (see docs/regime-identification-why.md):
  * "slow"   : news absorbed gradually -> persistent drift -> momentum pays (long-scale VR > 1)
  * "rushed" : forced sellers / liquidity stress -> negative short-run autocorrelation, high vol,
               high common share -> reversal pays (short-scale VR < 1)
  * "calm"   : neither group is active -> approximately efficient

Scenarios
  * "regime"        : 3 regimes with different microstructure (the answer is known).
  * "null_const"    : NO regime. Constant parameters equal to the time-average of "regime",
                      so unconditional momentum/reversal strength is comparable. Placebo for C2/C3.
  * "null_volonly"  : regimes differ ONLY in vol and common share; trend/autocorr held at the average.
                      Decoy: state-dependent total risk but no state-dependent strategy edge. Raw strategy
                      returns change with vol; the risk-standardised spread D should not.

Everything is reproducible from `seed`. Synthetic returns are close-to-close; no roll gaps are modelled
(roll handling is a real-data concern for the next stage).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

RHO_TREND = 0.96  # persistence of the latent drift (half-life ~17 days)


@dataclass(frozen=True)
class RegimeSpec:
    name: str
    vol: float  # daily total-noise stdev
    share: float  # share of noise variance from the common factor
    trend_sd: float  # innovation stdev of the latent per-asset drift (0 = no momentum source)
    ar1: float  # lag-1 autocorrelation of the noise (negative = reversal source)


REGIME_SPECS = (
    RegimeSpec("slow", vol=0.010, share=0.25, trend_sd=0.00080, ar1=0.0),
    RegimeSpec("rushed", vol=0.016, share=0.55, trend_sd=0.0, ar1=-0.25),
    RegimeSpec("calm", vol=0.008, share=0.20, trend_sd=0.0, ar1=0.0),
)

SCENARIOS = ("regime", "null_const", "null_volonly")


@dataclass
class SyntheticMarket:
    scenario: str
    returns: pd.DataFrame  # (days x assets) daily returns
    states: pd.Series  # true regime id per day (0 for null_const)
    state_names: tuple[str, ...]
    specs: tuple[RegimeSpec, ...]
    transition: np.ndarray
    seed: int
    meta: dict = field(default_factory=dict)


def sticky_transition(k: int, stay_prob: float) -> np.ndarray:
    if k == 1:
        return np.ones((1, 1))
    off = (1.0 - stay_prob) / (k - 1)
    p = np.full((k, k), off)
    np.fill_diagonal(p, stay_prob)
    return p


def _averaged(specs: tuple[RegimeSpec, ...], name: str) -> RegimeSpec:
    return RegimeSpec(
        name=name,
        vol=float(np.mean([s.vol for s in specs])),
        share=float(np.mean([s.share for s in specs])),
        trend_sd=float(np.mean([s.trend_sd for s in specs])),
        ar1=float(np.mean([s.ar1 for s in specs])),
    )


def scenario_specs(scenario: str) -> tuple[RegimeSpec, ...]:
    if scenario == "regime":
        return REGIME_SPECS
    if scenario == "null_const":
        return (_averaged(REGIME_SPECS, "none"),)
    if scenario == "null_volonly":
        avg = _averaged(REGIME_SPECS, "avg")
        return tuple(
            replace(avg, name=f"vol_{s.name}", vol=s.vol, share=s.share) for s in REGIME_SPECS
        )
    raise ValueError(f"unknown scenario {scenario!r}; choose from {SCENARIOS}")


def sample_states(n_days: int, transition: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    k = transition.shape[0]
    states = np.empty(n_days, dtype=int)
    states[0] = rng.integers(k)
    cum = np.cumsum(transition, axis=1)
    u = rng.random(n_days)
    for t in range(1, n_days):
        states[t] = min(int(np.searchsorted(cum[states[t - 1]], u[t])), k - 1)
    return states


def generate(
    scenario: str = "regime",
    n_days: int = 6000,
    n_assets: int = 8,
    seed: int = 0,
    stay_prob: float = 0.98,
    start: str = "2010-01-04",
) -> SyntheticMarket:
    specs = scenario_specs(scenario)
    k = len(specs)
    transition = sticky_transition(k, stay_prob)
    rng = np.random.default_rng(seed)

    states = sample_states(n_days, transition, rng)
    f = rng.standard_normal(n_days)
    z = rng.standard_normal((n_days, n_assets))
    eps = rng.standard_normal((n_days, n_assets))

    vol = np.array([s.vol for s in specs])[states]
    share = np.array([s.share for s in specs])[states]
    trend_sd = np.array([s.trend_sd for s in specs])[states]
    ar1 = np.array([s.ar1 for s in specs])[states]

    u = np.sqrt(share)[:, None] * f[:, None] + np.sqrt(1.0 - share)[:, None] * z
    innov = (np.sqrt(1.0 - ar1**2) * vol)[:, None] * u
    drift_innov = trend_sd[:, None] * eps

    returns = np.empty((n_days, n_assets))
    m = np.zeros(n_assets)
    n = np.zeros(n_assets)
    for t in range(n_days):
        m = RHO_TREND * m + drift_innov[t]
        n = ar1[t] * n + innov[t]
        returns[t] = m + n

    idx = pd.bdate_range(start=start, periods=n_days)
    cols = [f"A{i}" for i in range(n_assets)]
    return SyntheticMarket(
        scenario=scenario,
        returns=pd.DataFrame(returns, index=idx, columns=cols),
        states=pd.Series(states, index=idx, name="state"),
        state_names=tuple(s.name for s in specs),
        specs=specs,
        transition=transition,
        seed=seed,
        meta={"n_days": n_days, "n_assets": n_assets, "stay_prob": stay_prob},
    )
