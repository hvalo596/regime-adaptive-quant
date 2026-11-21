import numpy as np
import pytest

from regime_quant.backtest import build_legs, run_weights, state_weights
from regime_quant.config import CostParams, MOM_MAIN, REV_MAIN, REV_SECOND_GAP, MOM_SECOND, StateParams
from regime_quant.eventengine import reconcile
from regime_quant.nullcal import calibrate
from regime_quant.pipeline import run_state_pipeline
from regime_quant.world import WorldSpec, generate


@pytest.fixture(scope="module")
def cal():
    return calibrate(n_sims=4, n_days=1500, n_assets=30)


@pytest.fixture(scope="module")
def world():
    w = generate(WorldSpec(kind="regime", effect=0.15, n_days=1500, n_assets=25, seed=3))
    ret = w.ret.copy()
    ret[:300, 20:] = np.nan  # unbalanced panel: five assets enter late
    return ret


def test_vectorised_equals_event_driven(world, cal):
    run = run_state_pipeline(world, cal)
    res = reconcile(world, MOM_MAIN, REV_MAIN, run.s, run.kappa, run.excl)
    assert res["gross_n"] > 500
    assert res["gross_max_abs_diff"] < 1e-10
    assert res["cost_max_abs_diff"] < 1e-10
    assert res["weights_max_abs_diff"] < 1e-10
    assert res["x_mom_max_abs_diff"] < 1e-10 and res["x_rev_max_abs_diff"] < 1e-10


def test_reconcile_other_specs(world, cal):
    run = run_state_pipeline(world, cal, mom=MOM_SECOND, rev=REV_SECOND_GAP)
    res = reconcile(world, MOM_SECOND, REV_SECOND_GAP, run.s, run.kappa, run.excl)
    assert res["gross_max_abs_diff"] < 1e-10 and res["weights_max_abs_diff"] < 1e-10


def test_selection_identity(world, cal):
    """kappa = 1, no exclusion, zero cost: P - (x_mom + x_rev)/2 = s * D / 2 exactly (doc 4.5)."""
    run = run_state_pipeline(world, cal, use_exclusion=False, use_kappa=False, with_portfolio=False)
    legs = run.legs
    W = state_weights(legs, run.s, None, None)
    pf = run_weights(world, W, legs.vol, CostParams(0.0, 0.0))
    lhs = pf.gross_next - 0.5 * (legs.mom.x_next + legs.rev.x_next)
    rhs = 0.5 * run.s * legs.D_next
    ok = np.isfinite(lhs) & np.isfinite(rhs)
    assert ok.sum() > 500
    assert np.max(np.abs(lhs[ok] - rhs[ok])) < 1e-12


def test_no_lookahead_full_pipeline(world, cal):
    """Scramble everything after day t0: every state variable, state, weight and leg return up to t0 stays identical."""
    t0 = 900
    base = run_state_pipeline(world, cal)
    tampered = world.copy()
    rng = np.random.default_rng(0)
    tampered[t0 + 1 :] = rng.standard_normal(tampered[t0 + 1 :].shape) * 0.05
    alt = run_state_pipeline(tampered, cal)

    def same(a, b):
        a, b = np.asarray(a, dtype=float)[: t0 + 1], np.asarray(b, dtype=float)[: t0 + 1]
        return np.allclose(a, b, equal_nan=True, atol=1e-12)

    assert same(base.tau_m, alt.tau_m) and same(base.tau_r, alt.tau_r)
    assert same(base.delta_m, alt.delta_m) and same(base.delta_r, alt.delta_r)
    assert same(base.s, alt.s)
    assert same(base.conc.C, alt.conc.C) and same(base.excl, alt.excl)
    assert same(base.env.V, alt.env.V) and same(base.env.Phi_perp, alt.env.Phi_perp) and same(base.env.zV, alt.env.zV)
    assert same(base.legs.mom.weights, alt.legs.mom.weights) and same(base.legs.rev.weights, alt.legs.rev.weights)
    # the decision at t0 earns on day t0+1, which is allowed to differ; everything decided up to t0-1 is final
    assert same(base.portfolio.weights, alt.portfolio.weights)
    assert np.allclose(base.portfolio.gross_next[:t0], alt.portfolio.gross_next[:t0], equal_nan=True, atol=1e-12)
    assert np.allclose(base.D_next[:t0], alt.D_next[:t0], equal_nan=True, atol=1e-12)


def test_costs_scale_with_turnover(world, cal):
    run = run_state_pipeline(world, cal, with_portfolio=False)
    W = state_weights(run.legs, run.s, run.kappa, run.excl)
    free = run_weights(world, W, run.legs.vol, CostParams(0.0, 0.0))
    base = run_weights(world, W, run.legs.vol, CostParams(1.0, 0.05))
    dbl = run_weights(world, W, run.legs.vol, CostParams(2.0, 0.10))
    assert free.cost_next.sum() == 0
    assert np.isclose(dbl.cost_next.sum(), 2 * base.cost_next.sum(), rtol=1e-9)
    assert np.allclose(free.gross_next, base.gross_next, equal_nan=True)
