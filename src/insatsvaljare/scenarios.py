"""Interest-rate scenario generators.

The simulation engine consumes a monthly rate path (length = years × 12)
for each scenario. v1 supports the three deterministic scenarios from the
ref doc; a Monte Carlo generator is provided for optional use.
"""

from __future__ import annotations

import numpy as np

from insatsvaljare.rates import RateScenario, mortgage_rate


def deterministic_path(
    ltv_fraction: float,
    binding_months: int,
    scenario: RateScenario,
    years: int,
) -> np.ndarray:
    """Constant rate path for a given scenario, in decimal form (0.0325 = 3.25%)."""
    r = mortgage_rate(ltv_fraction, scenario, binding_months)
    return np.full(years * 12, r, dtype=float)


def ar1_mc_paths(
    ltv_fraction: float,
    binding_months: int,
    years: int,
    n_paths: int = 500,
    long_run_mean: float = 0.035,
    vol_annual: float = 0.0075,
    mean_reversion: float = 0.25,
    seed: int | None = 42,
) -> np.ndarray:
    """Ornstein-Uhlenbeck / AR(1) rate paths around a long-run mean.

    Returns shape (n_paths, years*12). Rate starts from the BASE scenario
    (LTV-adjusted) and mean-reverts to long_run_mean + LTV penalty.

    vol_annual is the standard deviation of *annual* changes; we scale to
    monthly via sqrt(12). The mean_reversion parameter is the annual speed;
    at 0.25 a shock decays with half-life ~2.8 years.
    """
    rng = np.random.default_rng(seed)
    n_months = years * 12
    dt = 1.0 / 12
    theta = mean_reversion * dt
    sigma_month = vol_annual / np.sqrt(12)

    base = mortgage_rate(ltv_fraction, RateScenario.BASE, binding_months)
    mu = long_run_mean + (base - mortgage_rate(ltv_fraction, RateScenario.BASE, binding_months) + 0)
    # (base already contains the LTV penalty; mu is long-run assumption + same penalty)
    mu = long_run_mean + base - mortgage_rate(ltv_fraction, RateScenario.BASE, 3)

    paths = np.zeros((n_paths, n_months))
    paths[:, 0] = base
    eps = rng.standard_normal((n_paths, n_months - 1)) * sigma_month
    for t in range(1, n_months):
        paths[:, t] = (
            paths[:, t - 1] + theta * (mu - paths[:, t - 1]) + eps[:, t - 1]
        )
    # Floor at 0 (no negative mortgage rates in practice)
    return np.maximum(paths, 0.0)
