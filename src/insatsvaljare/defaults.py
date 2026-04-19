"""Stockholm 2026 default parameters for the simulation.

The household is modelled as a list of `HouseholdMember`s. Each member
has their own cash, brutto income, personal expenses and investment
strategy. Shared costs (avgift, loan interest, amortisation) are split
proportionally to brutto income; insats contributions are split
proportionally to each member's starting cash.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from insatsvaljare.rates import RateScenario


class InvestmentStrategy(str, Enum):
    SPARKONTO = "sparkonto"
    RANTEFOND_ISK = "rantefond_isk"
    ANPASSAD = "anpassad"


class TaxModel(str, Enum):
    """Per-bucket tax treatment inside the `anpassad` strategy.

    ISK / KF share a single 300 000 kr fribelopp per person; AF and
    SPARKONTO both approximate annual realisation at 30 %; NONE is
    for hypothetical tax-free positions.
    """
    ISK = "ISK"
    KF = "KF"
    AF = "AF"
    SPARKONTO = "SPARKONTO"
    NONE = "NONE"


class CustomBucket(BaseModel):
    """One slot inside the `anpassad` investment strategy."""
    name: str = "Bucket"
    allocation_fraction: float = Field(1.0, ge=0.0, le=1.0)
    annual_return: float = Field(0.04, ge=-0.5, le=0.5)
    tax_model: TaxModel = TaxModel.ISK


class HouseholdMember(BaseModel):
    """One person in the household.

    Notes:
        * `monthly_personal_expenses` covers only personal consumption
          (food, clothes, transport). Shared household costs (avgift,
          loan costs) are split proportionally to `annual_brutto_income`
          inside `simulate()`.
        * `strategy` picks which field feeds the portfolio model:
            - SPARKONTO → `sparkonto_return` (bank interest, 30 % annual tax)
            - RANTEFOND_ISK → `rantefond_isk_return` (ISK 1.065 % schablonskatt)
            - ANPASSAD → `custom_buckets` (user-defined allocation)
    """
    name: str = "Medlem"
    initial_cash: float = Field(5_400_000.0, ge=0.0)
    annual_brutto_income: float = Field(900_000.0, ge=0.0)
    monthly_personal_expenses: float = Field(25_000.0, ge=0.0)
    strategy: InvestmentStrategy = InvestmentStrategy.RANTEFOND_ISK
    sparkonto_return: float = Field(0.025, ge=-0.5, le=0.5)
    rantefond_isk_return: float = Field(0.065, ge=-0.5, le=0.5)
    custom_buckets: list[CustomBucket] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_custom_buckets(self) -> "HouseholdMember":
        if self.strategy == InvestmentStrategy.ANPASSAD:
            if not self.custom_buckets:
                raise ValueError(
                    f"Member '{self.name}' uses ANPASSAD strategy but has no custom_buckets"
                )
            total = sum(b.allocation_fraction for b in self.custom_buckets)
            if abs(total - 1.0) > 1e-4:
                raise ValueError(
                    f"Member '{self.name}' custom_buckets allocation_fraction "
                    f"must sum to 1.0 (got {total:.4f})"
                )
        return self


def _default_members() -> list[HouseholdMember]:
    return [HouseholdMember(name="Medlem 1")]


class SimulationConfig(BaseModel):
    """All inputs for one simulation run. Horizon length is set via `years`."""

    # Property
    property_value: float = Field(6_000_000.0, description="Purchase price in kr")
    monthly_avgift: float = Field(3_300.0, description="Current total monthly BRF fee in kr")
    property_appreciation: float = Field(0.04, description="Annual nominal, e.g. 0.04 = 4 %")
    avgift_inflation: float = 0.025

    # Loan
    ltv_fraction: float = Field(0.85, ge=0.0, le=0.90)
    binding_months: int = 3
    rate_scenario: RateScenario = RateScenario.BASE
    rate_override: float | None = Field(
        None,
        description="Manual rate override in decimal, bypasses scenario lookup",
    )

    # Amortization basis
    allow_5y_revaluation: bool = Field(
        False,
        description="If True, re-anchor amortization-LTV to market value every 5 years",
    )

    # Household — list of members (1+). Total cash, income, expenses derive
    # from the member list. CLAUDE.md §2 thesis still holds: the household's
    # aggregate initial_cash is held constant across LTV comparisons.
    members: list[HouseholdMember] = Field(default_factory=_default_members)

    # Shared tax / household settings
    kommunal_tax_rate: float = Field(
        0.3055,
        ge=0.0,
        le=0.5,
        description="Total kommunalskatt (kommun + region) as decimal. Stockholm default.",
    )
    income_growth: float = Field(0.03, description="Applied to every member's brutto annually")
    liquidity_buffer: float = Field(50_000.0, description="Per-household infeasibility threshold")

    # Exit
    sell_at_end: bool = False
    broker_fee_fraction: float = 0.04

    # Horizon
    years: int = 10

    model_config = ConfigDict(use_enum_values=False)

    # Convenience aggregates (derived, not stored) --------------------------

    @property
    def total_initial_cash(self) -> float:
        return sum(m.initial_cash for m in self.members)

    @property
    def total_brutto_income(self) -> float:
        return sum(m.annual_brutto_income for m in self.members)

    @property
    def total_personal_expenses(self) -> float:
        return sum(m.monthly_personal_expenses for m in self.members)


DEFAULT_CONFIG = SimulationConfig()
