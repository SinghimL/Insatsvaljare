"""Interest-rate and market scenario path generators.

Provides both deterministic rate paths (the classic LOW/BASE/HIGH) and
stochastic paths for Monte Carlo simulation: rate paths via a mean-
reverting AR(1) / Ornstein-Uhlenbeck process, and return paths for
portfolio assets and property appreciation via Gaussian noise around a
configurable mean.

The simulation engine can consume any combination; when all paths are
None, the engine falls back to its own deterministic defaults (so
existing call sites continue working unchanged).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from insatsvaljare.rates import RateScenario, mortgage_rate


# ---------------------------------------------------------------------------
# Deterministic (used by the classic 3-scenario UI)
# ---------------------------------------------------------------------------

def deterministic_path(
    ltv_fraction: float,
    binding_months: int,
    scenario: RateScenario,
    years: int,
) -> np.ndarray:
    """Constant rate path for a given scenario, in decimal form (0.0325 = 3.25%)."""
    r = mortgage_rate(ltv_fraction, scenario, binding_months)
    return np.full(years * 12, r, dtype=float)


# ---------------------------------------------------------------------------
# AR(1) rate path — Ornstein-Uhlenbeck around a long-run mean
# ---------------------------------------------------------------------------

def ar1_rate_paths(
    ltv_fraction: float,
    binding_months: int,
    years: int,
    n_paths: int = 300,
    long_run_mean: float = 0.035,
    vol_annual: float = 0.015,
    mean_reversion: float = 0.25,
    seed: int | None = 42,
) -> np.ndarray:
    """AR(1) / OU rate paths anchored at today's BASE rate, reverting to
    `long_run_mean` (with the same LTV penalty applied for consistency).

    Returns shape (n_paths, years * 12) in decimal form.

    Parameters:
        vol_annual: standard deviation of annual rate changes (0.015 = 1.5 pp).
        mean_reversion: annual reversion speed; 0.25 → half-life ~2.8 years.
        seed: for reproducibility; pass None to make each call stochastic.
    """
    rng = np.random.default_rng(seed)
    n_months = years * 12
    dt = 1.0 / 12
    theta = mean_reversion * dt
    sigma_month = vol_annual / np.sqrt(12)

    base = mortgage_rate(ltv_fraction, RateScenario.BASE, binding_months)
    # Add LTV penalty to long-run target too (so the mean reversion
    # destination is consistent with today's starting level).
    ltv_only_penalty = (
        mortgage_rate(ltv_fraction, RateScenario.BASE, 3)
        - mortgage_rate(0.50, RateScenario.BASE, 3)
    )
    mu = long_run_mean + ltv_only_penalty

    paths = np.zeros((n_paths, n_months))
    paths[:, 0] = base
    eps = rng.standard_normal((n_paths, n_months - 1)) * sigma_month
    for t in range(1, n_months):
        paths[:, t] = (
            paths[:, t - 1] + theta * (mu - paths[:, t - 1]) + eps[:, t - 1]
        )
    return np.maximum(paths, 0.0)


# Backward-compatible alias (older call sites / docs)
ar1_mc_paths = ar1_rate_paths


# ---------------------------------------------------------------------------
# Gaussian return paths — for portfolio buckets and property appreciation
# ---------------------------------------------------------------------------

def gaussian_return_paths(
    annual_mean: float,
    annual_vol: float,
    years: int,
    n_paths: int = 300,
    seed: int | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Monthly return paths with i.i.d. Normal(mean/12, vol/sqrt(12)) shocks.

    Returns shape (n_paths, years * 12). Each entry is the *decimal monthly
    return* for that path/month (e.g. 0.005 = +0.5 %).

    Passing `rng` overrides `seed` (useful for correlated draws across
    multiple asset classes in a single Monte Carlo run).
    """
    if rng is None:
        rng = np.random.default_rng(seed)
    n_months = years * 12
    mean_month = annual_mean / 12.0
    sigma_month = annual_vol / np.sqrt(12)
    if annual_vol <= 0:
        return np.full((n_paths, n_months), mean_month, dtype=float)
    return rng.normal(loc=mean_month, scale=sigma_month, size=(n_paths, n_months))


# ---------------------------------------------------------------------------
# Bundle: one full path across all asset classes for a single Monte Carlo draw
# ---------------------------------------------------------------------------

@dataclass
class MarketPath:
    """One Monte Carlo draw: rate + portfolio-return + property-return paths.

    All arrays are length = years * 12.

    `portfolio_monthly_returns` is keyed by (member_index, bucket_index) so
    the simulation engine can apply per-bucket draws while respecting the
    user's allocation structure.
    """
    rate_monthly: np.ndarray
    property_monthly_return: np.ndarray
    portfolio_monthly_returns: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)
