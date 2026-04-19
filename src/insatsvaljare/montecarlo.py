"""Monte Carlo engine for the Insatsväljare model.

Runs N stochastic paths of `simulate()` with correlated asset returns
and rate shocks, then aggregates to per-month quantile DataFrames.

Design notes:
- Path generation is vectorised; simulation itself is still a per-path
  Python loop (simulate() holds per-member / per-bucket state that's
  awkward to vectorise across paths without a rewrite).
- `run_monte_carlo` caches on config JSON + MC params, so subsequent
  renders with the same inputs are instant.
- Rate paths use the AR(1) / OU generator; portfolio returns use
  independent Gaussian draws; property returns are Gaussian with an
  optional negative correlation with rates (realistic: high rates tend
  to compress house prices).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from insatsvaljare.defaults import (
    CustomBucket,
    HouseholdMember,
    InvestmentStrategy,
    SimulationConfig,
    TaxModel,
)
from insatsvaljare.model import simulate
from insatsvaljare.scenarios import ar1_rate_paths, gaussian_return_paths


# Quantile columns we expose on the aggregated output.
_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "net_worth",
    "portfolio",
    "loan",
    "property_value",
    "house_equity",
    "cash_flow",
    "savings",
    "brutto_monthly",
    "tax_gross_monthly",
    "ranteavdrag_monthly",
    "personal_expenses_monthly",
    "interest",
    "amortization",
    "avgift",
)


@dataclass
class MonteCarloParams:
    n_paths: int = 300
    portfolio_vol: float = 0.15        # used by any ISK/KF/AF bucket
    sparkonto_vol: float = 0.0         # sparkonto is effectively deterministic
    property_vol: float = 0.08
    rate_vol: float = 0.015
    rate_mean_reversion: float = 0.25
    rate_long_run_mean: float = 0.035
    property_rate_correlation: float = -0.3  # neg: high rates → weak property growth
    seed: int | None = 42


@dataclass
class MonteCarloResult:
    """Aggregated MC output.

    quantiles: dict[quantile_label → DataFrame]
        e.g. quantiles["p10"], ["p50"], ["p90"] — each DataFrame has the
        same month-indexed columns as simulate() but filled with the
        cross-path quantile at every month.
    terminal_net_worth: np.ndarray of shape (n_paths,) — easy tail-risk summary.
    infeasible_months: np.ndarray of shape (n_paths,) — per-path count.
    """
    quantiles: dict[str, pd.DataFrame]
    terminal_net_worth: np.ndarray
    infeasible_months: np.ndarray
    n_paths: int

    @property
    def p_infeasible(self) -> float:
        """Fraction of paths where at least one month was infeasible."""
        if self.n_paths == 0:
            return 0.0
        return float(np.mean(self.infeasible_months > 0))


def _bucket_vol_for(tax_model: TaxModel, params: MonteCarloParams) -> float:
    if tax_model == TaxModel.SPARKONTO:
        return params.sparkonto_vol
    return params.portfolio_vol


def _effective_buckets(member: HouseholdMember) -> list[CustomBucket]:
    """Flatten a member's strategy into the same bucket list the model uses."""
    if member.strategy == InvestmentStrategy.SPARKONTO:
        return [CustomBucket(
            allocation_fraction=1.0,
            annual_return=member.sparkonto_return,
            tax_model=TaxModel.SPARKONTO,
        )]
    if member.strategy == InvestmentStrategy.RANTEFOND_ISK:
        return [CustomBucket(
            allocation_fraction=1.0,
            annual_return=member.rantefond_isk_return,
            tax_model=TaxModel.ISK,
        )]
    return list(member.custom_buckets)


def run_monte_carlo(
    config: SimulationConfig,
    params: MonteCarloParams | None = None,
) -> MonteCarloResult:
    """Run MC simulation and return quantile DataFrames + terminal distributions.

    This is the function to call from the UI. It's deterministic given
    the same config + params + seed, which makes it cacheable.
    """
    params = params or MonteCarloParams()
    rng = np.random.default_rng(params.seed)

    rate_paths = ar1_rate_paths(
        ltv_fraction=config.ltv_fraction,
        binding_months=config.binding_months,
        years=config.years,
        n_paths=params.n_paths,
        long_run_mean=params.rate_long_run_mean,
        vol_annual=params.rate_vol,
        mean_reversion=params.rate_mean_reversion,
        seed=int(rng.integers(0, 2**31 - 1)),
    )

    # Property return path, correlated with rate innovations.
    # We draw an i.i.d. Gaussian then mix with the standardised rate innovations.
    prop_mean_monthly = config.property_appreciation / 12
    prop_sigma_monthly = params.property_vol / np.sqrt(12)
    if prop_sigma_monthly > 0 and abs(params.property_rate_correlation) > 0:
        # Approximate rate "innovations" by month-over-month rate changes,
        # standardised to unit variance.
        rate_innov = np.diff(rate_paths, axis=1, prepend=rate_paths[:, :1])
        rate_innov_std = rate_innov.std(axis=1, keepdims=True)
        rate_innov_std = np.where(rate_innov_std > 0, rate_innov_std, 1.0)
        rate_z = rate_innov / rate_innov_std

        indep_z = rng.standard_normal(rate_paths.shape)
        rho = params.property_rate_correlation
        combined_z = rho * rate_z + np.sqrt(max(0.0, 1 - rho**2)) * indep_z
        property_paths = prop_mean_monthly + prop_sigma_monthly * combined_z
    else:
        property_paths = gaussian_return_paths(
            annual_mean=config.property_appreciation,
            annual_vol=params.property_vol,
            years=config.years,
            n_paths=params.n_paths,
            rng=rng,
        )

    # Pre-compute per-member / per-bucket return paths.
    # Each (member_idx, bucket_idx) gets its own independent path.
    portfolio_paths: dict[tuple[int, int], np.ndarray] = {}
    for m_idx, member in enumerate(config.members):
        for b_idx, bucket in enumerate(_effective_buckets(member)):
            vol = _bucket_vol_for(bucket.tax_model, params)
            portfolio_paths[(m_idx, b_idx)] = gaussian_return_paths(
                annual_mean=bucket.annual_return,
                annual_vol=vol,
                years=config.years,
                n_paths=params.n_paths,
                rng=rng,
            )

    # Run simulate() for each path. This is the expensive loop.
    path_dfs: list[pd.DataFrame] = []
    terminal_nw = np.empty(params.n_paths, dtype=float)
    infeasible = np.empty(params.n_paths, dtype=int)

    for p in range(params.n_paths):
        per_path_bucket_returns = {
            key: arr[p] for key, arr in portfolio_paths.items()
        }
        df = simulate(
            config,
            rate_path=rate_paths[p],
            portfolio_monthly_returns=per_path_bucket_returns,
            property_monthly_return=property_paths[p],
        )
        path_dfs.append(df)
        terminal_nw[p] = float(df["net_worth"].iloc[-1])
        infeasible[p] = int(df["infeasible"].sum())

    # Stack per-column into (n_months, n_paths) arrays, then quantile across paths.
    quantiles: dict[str, pd.DataFrame] = {}
    n_months = len(path_dfs[0])
    quantile_labels = {"p10": 0.10, "p50": 0.50, "p90": 0.90}
    for label, q in quantile_labels.items():
        row_data: dict[str, np.ndarray] = {}
        for col in _AGGREGATE_COLUMNS:
            stacked = np.array([df[col].to_numpy() for df in path_dfs])  # (n_paths, n_months)
            row_data[col] = np.quantile(stacked, q, axis=0)
        # Propagate month / year columns from the first path (deterministic)
        row_data["month"] = path_dfs[0]["month"].to_numpy()
        row_data["year"] = path_dfs[0]["year"].to_numpy()
        quantiles[label] = pd.DataFrame(row_data)

    return MonteCarloResult(
        quantiles=quantiles,
        terminal_net_worth=terminal_nw,
        infeasible_months=infeasible,
        n_paths=params.n_paths,
    )
