"""Mortgage rate lookup: base rate by scenario + LTV penalty.

Reference: ref/swedish-mortgage-policy-2026.md §3 and §4
"""

from __future__ import annotations

from enum import Enum


class RateScenario(str, Enum):
    LOW = "LOW"
    BASE = "BASE"
    HIGH = "HIGH"


# Base rorlig (3-month) rate per scenario — see ref §4.3
SCENARIO_BASE_RATE_3M = {
    RateScenario.LOW: 0.0250,
    RateScenario.BASE: 0.0325,
    RateScenario.HIGH: 0.0425,
}

# Spread added for longer fixation periods (vs 3-month base).
# Approximate from ref §3.1 SBAB snittränta gaps.
FIXATION_SPREAD_BY_MONTHS = {
    3: 0.0,
    12: 0.0020,
    24: 0.0028,
    36: 0.0041,
    60: 0.0078,
    84: 0.0102,
    120: 0.0121,
}


def ltv_penalty(ltv_fraction: float) -> float:
    """LTV-based additive rate penalty in decimal form (0.001 = 0.1 pp).

    Thesis-critical: higher LTV → higher rate, which offsets the "invest
    the freed cash" upside. See ref §3.1 for calibration source.
    """
    if ltv_fraction < 0.50:
        return -0.0005
    if ltv_fraction < 0.70:
        return 0.0000
    if ltv_fraction < 0.85:
        return 0.0010
    # 0.85 – 0.90 (new ceiling)
    return 0.0025


def base_rate(
    scenario: RateScenario,
    binding_months: int = 3,
) -> float:
    """Base rate for a given scenario + fixation period (no LTV adjustment)."""
    base = SCENARIO_BASE_RATE_3M[scenario]
    spread = _spread_for_months(binding_months)
    return base + spread


def _spread_for_months(binding_months: int) -> float:
    """Nearest-neighbor lookup into the fixation spread table."""
    if binding_months in FIXATION_SPREAD_BY_MONTHS:
        return FIXATION_SPREAD_BY_MONTHS[binding_months]
    # Linear interp between two nearest known points
    known = sorted(FIXATION_SPREAD_BY_MONTHS.keys())
    if binding_months <= known[0]:
        return FIXATION_SPREAD_BY_MONTHS[known[0]]
    if binding_months >= known[-1]:
        return FIXATION_SPREAD_BY_MONTHS[known[-1]]
    for lo, hi in zip(known, known[1:]):
        if lo <= binding_months <= hi:
            w = (binding_months - lo) / (hi - lo)
            return (
                (1 - w) * FIXATION_SPREAD_BY_MONTHS[lo]
                + w * FIXATION_SPREAD_BY_MONTHS[hi]
            )
    return FIXATION_SPREAD_BY_MONTHS[known[-1]]


def mortgage_rate(
    ltv_fraction: float,
    scenario: RateScenario = RateScenario.BASE,
    binding_months: int = 3,
) -> float:
    """Full mortgage rate = base(scenario, fixation) + LTV penalty."""
    return base_rate(scenario, binding_months) + ltv_penalty(ltv_fraction)


def amortization_rate(ltv_fraction: float) -> float:
    """Annual mandatory amortization as a fraction of original loan.

    2026 rules (ref §2):
      • LTV < 50 %  → 0 %
      • 50 % ≤ LTV < 70 %  → 1 %
      • LTV ≥ 70 %  → 2 %
    Note: the basis stays at the *original* loan valuation for at least
    5 years; the simulation engine handles that separately.
    """
    if ltv_fraction < 0.50:
        return 0.0
    if ltv_fraction < 0.70:
        return 0.01
    return 0.02
