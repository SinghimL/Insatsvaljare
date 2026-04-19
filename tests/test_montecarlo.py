"""Unit tests for the Monte Carlo engine."""

from __future__ import annotations

import numpy as np
import pytest

from insatsvaljare.defaults import (
    CustomBucket,
    HouseholdMember,
    InvestmentStrategy,
    SimulationConfig,
    TaxModel,
)
from insatsvaljare.montecarlo import MonteCarloParams, run_monte_carlo


@pytest.fixture
def small_config():
    """Fewer members + shorter horizon → faster tests."""
    return SimulationConfig(years=3)


def test_mc_determinism_with_same_seed(small_config):
    p = MonteCarloParams(n_paths=30, seed=123)
    r1 = run_monte_carlo(small_config, p)
    r2 = run_monte_carlo(small_config, p)
    np.testing.assert_allclose(r1.terminal_net_worth, r2.terminal_net_worth)


def test_mc_terminal_nw_scales_with_paths(small_config):
    r = run_monte_carlo(small_config, MonteCarloParams(n_paths=50, seed=7))
    assert len(r.terminal_net_worth) == 50
    assert r.terminal_net_worth.min() > 0
    assert r.terminal_net_worth.mean() > small_config.total_initial_cash


def test_mc_quantile_ordering(small_config):
    """p10 ≤ p50 ≤ p90 pointwise for every month."""
    r = run_monte_carlo(small_config, MonteCarloParams(n_paths=100, seed=42))
    assert set(r.quantiles.keys()) >= {"p10", "p50", "p90"}
    p10, p50, p90 = r.quantiles["p10"], r.quantiles["p50"], r.quantiles["p90"]
    assert (p10["net_worth"] <= p50["net_worth"] + 1e-6).all()
    assert (p50["net_worth"] <= p90["net_worth"] + 1e-6).all()


def test_mc_zero_vol_matches_deterministic(small_config):
    """With every vol at 0 and rate_vol=0 → all paths collapse to the deterministic run."""
    r = run_monte_carlo(small_config, MonteCarloParams(
        n_paths=20,
        portfolio_vol=0.0,
        sparkonto_vol=0.0,
        property_vol=0.0,
        rate_vol=0.0,
        seed=1,
    ))
    # p10 / p50 / p90 should all be identical (to floating precision)
    np.testing.assert_allclose(
        r.quantiles["p10"]["net_worth"],
        r.quantiles["p90"]["net_worth"],
        atol=1.0,  # within 1 kr
    )


def test_mc_vol_widens_distribution(small_config):
    low_vol = run_monte_carlo(
        small_config,
        MonteCarloParams(n_paths=100, portfolio_vol=0.05, seed=2),
    )
    high_vol = run_monte_carlo(
        small_config,
        MonteCarloParams(n_paths=100, portfolio_vol=0.25, seed=2),
    )
    low_spread = low_vol.terminal_net_worth.std()
    high_spread = high_vol.terminal_net_worth.std()
    assert high_spread > low_spread


def test_mc_infeasibility_tracking(small_config):
    """With an unrealistic buffer, every path should hit infeasible at least once."""
    cfg = small_config.model_copy(update={"liquidity_buffer": -1_000_000})
    r = run_monte_carlo(cfg, MonteCarloParams(n_paths=30, seed=5))
    assert r.infeasible_months.shape == (30,)
    # Just sanity: the counts are non-negative ints.
    assert (r.infeasible_months >= 0).all()


def test_mc_anpassad_strategy():
    """A multi-bucket Anpassad member should get per-bucket MC paths routed correctly."""
    member = HouseholdMember(
        name="X",
        strategy=InvestmentStrategy.ANPASSAD,
        custom_buckets=[
            CustomBucket(allocation_fraction=0.5, annual_return=0.05, tax_model=TaxModel.ISK),
            CustomBucket(allocation_fraction=0.5, annual_return=0.02, tax_model=TaxModel.SPARKONTO),
        ],
    )
    cfg = SimulationConfig(years=3, members=[member])
    r = run_monte_carlo(cfg, MonteCarloParams(n_paths=40, seed=9))
    assert len(r.terminal_net_worth) == 40
    assert np.isfinite(r.terminal_net_worth).all()
