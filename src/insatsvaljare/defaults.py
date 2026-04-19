"""Stockholm 2026 default parameters for the simulation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from insatsvaljare.rates import RateScenario
from insatsvaljare.tax import AccountType


class SimulationConfig(BaseModel):
    """All inputs for one simulation run. Horizon length is set via `years`."""

    # Property
    property_value: float = Field(6_000_000.0, description="Purchase price in kr")
    living_area_m2: float = 55.0
    monthly_avgift_per_m2: float = 60.0
    property_appreciation: float = Field(0.04, description="Annual nominal, e.g. 0.04 = 4 %")
    avgift_inflation: float = 0.025

    # Loan
    ltv_fraction: float = Field(0.85, ge=0.10, le=0.90)
    binding_months: int = 3
    rate_scenario: RateScenario = RateScenario.BASE
    rate_override: float | None = Field(
        None,
        description="Manual rate override in decimal, bypasses scenario lookup",
    )

    # Starting cash (insats + initial investment).
    # Must be >= property_value × (1 - ltv_fraction). Excess goes into
    # the portfolio at t=0 — this is the core mechanism of the model.
    initial_cash: float = Field(
        5_400_000.0,
        description="Total buying power; insats + seed portfolio. "
        "Must cover the insats at the chosen LTV.",
    )

    # Amortization basis
    allow_5y_revaluation: bool = Field(
        False,
        description="If True, re-anchor amortization-LTV to market value every 5 years",
    )

    # Household cash flow
    annual_gross_income: float = 900_000.0
    monthly_living_cost: float = 25_000.0
    income_growth: float = 0.03
    liquidity_buffer: float = 50_000.0

    # Investment
    portfolio_return: float = Field(0.065, description="Annual nominal return")
    account_type: AccountType = AccountType.ISK
    n_persons_for_fribelopp: int = 1
    other_account_tax_rate: float = 0.30

    # Exit
    sell_at_end: bool = False
    broker_fee_fraction: float = 0.04

    # Horizon
    years: int = 10

    model_config = ConfigDict(use_enum_values=False)


DEFAULT_CONFIG = SimulationConfig()
