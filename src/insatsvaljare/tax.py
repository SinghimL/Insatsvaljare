"""Swedish tax calculations for mortgage interest and investment accounts.

Reference: ref/swedish-mortgage-policy-2026.md §5
"""

from __future__ import annotations

from enum import Enum


class AccountType(str, Enum):
    ISK = "ISK"
    KF = "KF"
    OTHER = "OTHER"


# 2026 constants
RANTEAVDRAG_TIER1_CAP = 100_000.0
RANTEAVDRAG_TIER1_RATE = 0.30
RANTEAVDRAG_TIER2_RATE = 0.21

ISK_FRIBELOPP_2026 = 300_000.0
ISK_EFFECTIVE_RATE_2026 = 0.01065


def ranteavdrag(annual_interest: float) -> float:
    """Tax reduction (skattereduktion) from mortgage interest.

    30 % on the first 100 000 kr, 21 % on the excess. Assumes the household
    has sufficient kapitalinkomst / earned income to fully absorb the credit.
    """
    if annual_interest <= 0:
        return 0.0
    tier1 = min(annual_interest, RANTEAVDRAG_TIER1_CAP) * RANTEAVDRAG_TIER1_RATE
    tier2 = max(0.0, annual_interest - RANTEAVDRAG_TIER1_CAP) * RANTEAVDRAG_TIER2_RATE
    return tier1 + tier2


def isk_kapitalunderlag(
    quarterly_openings: list[float],
    annual_deposits: float,
) -> float:
    """Swedish ISK kapitalunderlag formula.

    (Q1 ingående + Q2 ingående + Q3 ingående + Q4 ingående + sum of deposits) / 4.
    """
    if len(quarterly_openings) != 4:
        raise ValueError("quarterly_openings must have exactly 4 entries")
    return (sum(quarterly_openings) + annual_deposits) / 4.0


def isk_schablonskatt(
    quarterly_openings: list[float],
    annual_deposits: float,
    n_persons: int = 1,
    fribelopp_per_person: float = ISK_FRIBELOPP_2026,
    effective_rate: float = ISK_EFFECTIVE_RATE_2026,
) -> float:
    """ISK / KF schablonskatt for the year.

    2026 regler: 300 000 kr fribelopp per person (summed across ISK + KF),
    effective rate 1.065 % on the excess kapitalunderlag.
    """
    kapitalunderlag = isk_kapitalunderlag(quarterly_openings, annual_deposits)
    taxable = max(0.0, kapitalunderlag - n_persons * fribelopp_per_person)
    return taxable * effective_rate


def other_account_tax(realized_gains: float, rate: float = 0.30) -> float:
    """Realized capital-gains tax for a non-ISK/KF account.

    Default 30 % matches vanlig depå. Override for parent's account, foreign
    jurisdiction, or corporate holding. No fribelopp, no schablonskatt — tax
    only triggers when gains are realized.
    """
    return max(0.0, realized_gains) * rate


def annual_investment_tax(
    account_type: AccountType,
    quarterly_openings: list[float],
    annual_deposits: float,
    realized_gains: float,
    n_persons: int = 1,
    other_rate: float = 0.30,
) -> float:
    """Dispatch to the right tax computation based on account type."""
    if account_type in (AccountType.ISK, AccountType.KF):
        return isk_schablonskatt(
            quarterly_openings,
            annual_deposits,
            n_persons=n_persons,
        )
    elif account_type == AccountType.OTHER:
        return other_account_tax(realized_gains, rate=other_rate)
    raise ValueError(f"Unknown account type: {account_type}")


def effective_interest_rate(nominal_rate: float, annual_interest: float) -> float:
    """After-tax effective interest rate, accounting for ränteavdrag.

    Nonlinear because of the 100k kink. Used for reporting only; the
    simulation engine applies ränteavdrag as an annual refund instead.
    """
    if annual_interest <= 0 or nominal_rate <= 0:
        return nominal_rate
    credit = ranteavdrag(annual_interest)
    return nominal_rate * (1 - credit / annual_interest)
