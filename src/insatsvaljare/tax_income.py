"""Swedish personal income tax calculations for 2026 (under 66 years).

Reference: ref/swedish-income-tax-2026.md

Computes brutto → netto conversion with grundavdrag, jobbskatteavdrag
(Prop. 2025/26:32 strengthened brackets), statlig skatt, and the
ränteavdrag skattereduktion-cap logic. Ignores allmän pensionsavgift
because its skattereduktion offsets it (net zero effect on take-home).
"""

from __future__ import annotations

from dataclasses import dataclass

# 2026 constants (under 66 years old)
PRISBASBELOPP_2026 = 59_200.0
SKIKTGRANS_2026 = 643_000.0  # threshold on taxable income (after grundavdrag)
BRYTPUNKT_2026 = 660_400.0   # corresponding gross-income threshold
STATLIG_RATE = 0.20

# Ränteavdrag rates (also defined in tax.py; repeated here to avoid circular import)
RANTEAVDRAG_TIER1_CAP = 100_000.0
RANTEAVDRAG_TIER1_RATE = 0.30
RANTEAVDRAG_TIER2_RATE = 0.21


def grundavdrag(ffi: float, prisbasbelopp: float = PRISBASBELOPP_2026) -> float:
    """Grundavdrag as a function of fastställd förvärvsinkomst (FFI).

    Piecewise formula for under-66 year-olds. See
    ref/swedish-income-tax-2026.md §4 for bracket bounds and coefficients.
    """
    if ffi <= 0:
        return 0.0
    pbb = prisbasbelopp
    ratio = ffi / pbb
    if ratio <= 0.99:
        return ffi
    if ratio <= 2.72:
        return 0.423 * pbb + 0.2 * (ffi - 0.99 * pbb)
    if ratio <= 3.11:
        return 0.77 * pbb
    if ratio <= 7.88:
        return 0.77 * pbb - 0.1 * (ffi - 3.11 * pbb)
    return 0.293 * pbb


def jobbskatteavdrag(
    arbetsinkomst: float,
    kommunal_rate: float,
    prisbasbelopp: float = PRISBASBELOPP_2026,
) -> float:
    """Jobbskatteavdrag (earned income tax credit) for under-66 year-olds.

    2026 coefficients per Prop. 2025/26:32 — strengthened middle bracket.
    Result is already in kronor (bracket formula × kommunalskattesats).
    No high-income phase-out (abolished 2025).
    """
    if arbetsinkomst <= 0 or kommunal_rate <= 0:
        return 0.0
    pbb = prisbasbelopp
    ai = arbetsinkomst
    ga = grundavdrag(ai, pbb)
    ratio = ai / pbb

    if ratio <= 0.91:
        bracket_expr = ai - ga
    elif ratio <= 3.24:
        bracket_expr = 0.91 * pbb + 0.3874 * (ai - 0.91 * pbb) - ga
    elif ratio <= 8.08:
        bracket_expr = 1.813 * pbb + 0.251 * (ai - 3.24 * pbb) - ga
    else:
        bracket_expr = 3.027 * pbb - ga

    return max(0.0, bracket_expr) * kommunal_rate


@dataclass(frozen=True)
class NetIncomeBreakdown:
    """Full per-year tax breakdown; all fields in kronor.

    Accounting identity: brutto = netto + final_tax
    Sub-identity:        final_tax = kommunal + statlig − jsa − ranteavdrag_actual
    """
    brutto: float
    grundavdrag: float
    taxable: float            # FFI − grundavdrag
    kommunal_skatt: float
    statlig_skatt: float
    jobbskatteavdrag: float
    ranteavdrag_theoretical: float
    ranteavdrag_actual: float
    final_tax: float
    netto: float


def ranteavdrag_theoretical(annual_interest: float) -> float:
    """Theoretical ränteavdrag before skattereduktion cap."""
    if annual_interest <= 0:
        return 0.0
    tier1 = min(annual_interest, RANTEAVDRAG_TIER1_CAP) * RANTEAVDRAG_TIER1_RATE
    tier2 = max(0.0, annual_interest - RANTEAVDRAG_TIER1_CAP) * RANTEAVDRAG_TIER2_RATE
    return tier1 + tier2


def compute_net_income(
    brutto: float,
    kommunal_rate: float,
    annual_interest: float = 0.0,
    prisbasbelopp: float = PRISBASBELOPP_2026,
    skiktgrans: float = SKIKTGRANS_2026,
) -> NetIncomeBreakdown:
    """Compute one year of take-home income after all förvärvsinkomst taxes.

    Order of operations (per Inkomstskattelagen 67 kap):
      1. Kommunal + statlig skatt on taxable income
      2. Subtract jobbskatteavdrag
      3. Subtract ränteavdrag, capped at remaining tax liability

    The ränteavdrag cap is what makes low-salary + high-LTV strategies
    actually less attractive than the naive model assumes.
    """
    if brutto <= 0:
        return NetIncomeBreakdown(
            brutto=max(0.0, brutto),
            grundavdrag=0.0,
            taxable=0.0,
            kommunal_skatt=0.0,
            statlig_skatt=0.0,
            jobbskatteavdrag=0.0,
            ranteavdrag_theoretical=0.0,
            ranteavdrag_actual=0.0,
            final_tax=0.0,
            netto=max(0.0, brutto),
        )

    ga = grundavdrag(brutto, prisbasbelopp)
    taxable = max(0.0, brutto - ga)
    kommunal = taxable * kommunal_rate
    statlig = STATLIG_RATE * max(0.0, taxable - skiktgrans)
    jsa = jobbskatteavdrag(brutto, kommunal_rate, prisbasbelopp)

    tax_before_rant = max(0.0, kommunal + statlig - jsa)
    rant_theoretical = ranteavdrag_theoretical(annual_interest)
    rant_actual = min(rant_theoretical, tax_before_rant)

    final_tax = tax_before_rant - rant_actual
    netto = brutto - final_tax

    return NetIncomeBreakdown(
        brutto=brutto,
        grundavdrag=ga,
        taxable=taxable,
        kommunal_skatt=kommunal,
        statlig_skatt=statlig,
        jobbskatteavdrag=jsa,
        ranteavdrag_theoretical=rant_theoretical,
        ranteavdrag_actual=rant_actual,
        final_tax=final_tax,
        netto=netto,
    )
