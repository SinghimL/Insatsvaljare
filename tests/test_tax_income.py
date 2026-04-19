"""Unit tests for the 2026 Swedish income tax module."""

from __future__ import annotations

import pytest

from insatsvaljare.tax_income import (
    BRYTPUNKT_2026,
    PRISBASBELOPP_2026,
    SKIKTGRANS_2026,
    compute_net_income,
    grundavdrag,
    jobbskatteavdrag,
    ranteavdrag_theoretical,
)


PBB = PRISBASBELOPP_2026


# ---------------------------------------------------------------------------
# Grundavdrag
# ---------------------------------------------------------------------------

def test_grundavdrag_zero_income():
    assert grundavdrag(0) == 0.0


def test_grundavdrag_below_099_pbb_is_full_income():
    # In the first bracket (FFI ≤ 0.99 PBB), deduction equals entire income.
    assert grundavdrag(0.5 * PBB) == pytest.approx(0.5 * PBB)


def test_grundavdrag_max_plateau():
    # Between 2.72 and 3.11 PBB, grundavdrag = 0.77 × PBB.
    expected = 0.77 * PBB
    assert grundavdrag(2.8 * PBB) == pytest.approx(expected)
    assert grundavdrag(3.0 * PBB) == pytest.approx(expected)


def test_grundavdrag_high_income_minimum():
    # Above 7.88 PBB the deduction is fixed at 0.293 × PBB.
    expected = 0.293 * PBB
    assert grundavdrag(10 * PBB) == pytest.approx(expected)
    assert grundavdrag(20 * PBB) == pytest.approx(expected)


def test_grundavdrag_skatteverket_published_bounds():
    # Published min = 17 400 (rounded), max = 45 600 (rounded).
    assert grundavdrag(10_000_000) == pytest.approx(17_346, abs=100)
    assert grundavdrag(2.9 * PBB) == pytest.approx(45_584, abs=100)


# ---------------------------------------------------------------------------
# Jobbskatteavdrag
# ---------------------------------------------------------------------------

def test_jsa_zero_income():
    assert jobbskatteavdrag(0, 0.3055) == 0.0


def test_jsa_zero_kommunal_rate():
    # JSA is (bracket_expr) × KS; with KS=0 there's no credit.
    assert jobbskatteavdrag(500_000, 0.0) == 0.0


def test_jsa_plateau_above_808_pbb():
    # Above 8.08 PBB the bracket expression flattens to (3.027 PBB − GA).
    pbb = PBB
    ga = grundavdrag(10 * pbb)
    expected = (3.027 * pbb - ga) * 0.3055
    assert jobbskatteavdrag(10 * pbb, 0.3055) == pytest.approx(expected, abs=5)
    # No phase-out: 20 PBB should give the same credit (since GA floors out at 0.293 PBB too).
    assert jobbskatteavdrag(20 * pbb, 0.3055) == pytest.approx(expected, abs=5)


def test_jsa_skatteverket_max_average_ks():
    # Skatteverket-published max: ~4 366 kr/mån = 52 392 kr/year at average KS 32.38 %.
    got = jobbskatteavdrag(10 * PBB, 0.3238)
    assert got == pytest.approx(52_400, abs=500)


def test_jsa_monotonic_in_middle_bracket():
    # The 2026-strengthened bracket 3.24–8.08 PBB must be strictly increasing.
    ks = 0.3055
    ai_low = 4 * PBB
    ai_high = 7 * PBB
    assert jobbskatteavdrag(ai_high, ks) > jobbskatteavdrag(ai_low, ks)


# ---------------------------------------------------------------------------
# Ränteavdrag
# ---------------------------------------------------------------------------

def test_ranteavdrag_theoretical_tier1():
    assert ranteavdrag_theoretical(80_000) == pytest.approx(24_000)


def test_ranteavdrag_theoretical_tier2():
    # 30% × 100k + 21% × 50k = 30 000 + 10 500 = 40 500.
    assert ranteavdrag_theoretical(150_000) == pytest.approx(40_500)


def test_ranteavdrag_zero_or_negative():
    assert ranteavdrag_theoretical(0) == 0
    assert ranteavdrag_theoretical(-100) == 0


# ---------------------------------------------------------------------------
# Net income — integration
# ---------------------------------------------------------------------------

def test_net_income_zero_brutto():
    r = compute_net_income(0, 0.3055, 0)
    assert r.netto == 0
    assert r.final_tax == 0


def test_net_income_identity():
    """brutto = netto + final_tax must hold exactly."""
    r = compute_net_income(500_000, 0.3055, 50_000)
    assert r.netto + r.final_tax == pytest.approx(r.brutto)


def test_net_income_statlig_kicks_in_at_brytpunkt():
    # Below brytpunkt: no statlig skatt.
    r_below = compute_net_income(BRYTPUNKT_2026 - 1_000, 0.3055, 0)
    assert r_below.statlig_skatt == pytest.approx(0, abs=1)
    # Above brytpunkt: starts being positive.
    r_above = compute_net_income(BRYTPUNKT_2026 + 10_000, 0.3055, 0)
    assert r_above.statlig_skatt > 0


def test_net_income_ranteavdrag_cap_bites_low_income():
    """Low-income household with high interest can't fully absorb ränteavdrag."""
    # With 150 kkr interest, theoretical = 40.5k. But low brutto means
    # tax after JSA is small, so actual ranteavdrag is capped.
    r = compute_net_income(200_000, 0.3055, 150_000)
    assert r.ranteavdrag_theoretical == pytest.approx(40_500)
    assert r.ranteavdrag_actual < r.ranteavdrag_theoretical


def test_net_income_ranteavdrag_full_for_high_income():
    """High income household absorbs full ränteavdrag."""
    r = compute_net_income(800_000, 0.3055, 150_000)
    assert r.ranteavdrag_actual == pytest.approx(r.ranteavdrag_theoretical)


def test_net_income_kommunal_varies_with_ks():
    """Higher kommunalskatt → higher kommunal tax, but also higher JSA."""
    r_stockholm = compute_net_income(500_000, 0.3055, 0)
    r_dorotea = compute_net_income(500_000, 0.3565, 0)
    assert r_dorotea.kommunal_skatt > r_stockholm.kommunal_skatt
    assert r_dorotea.jobbskatteavdrag > r_stockholm.jobbskatteavdrag


def test_net_income_skiktgrans_computation():
    """At FFI = skiktgräns + grundavdrag_at_that_income, statlig should be zero."""
    ga = grundavdrag(BRYTPUNKT_2026)
    # FFI − GA = brytpunkt − ga ≈ skiktgräns
    taxable = BRYTPUNKT_2026 - ga
    assert taxable == pytest.approx(SKIKTGRANS_2026, abs=100)


def test_net_income_no_interest_means_zero_ranteavdrag():
    r = compute_net_income(500_000, 0.3055, 0)
    assert r.ranteavdrag_actual == 0
    assert r.ranteavdrag_theoretical == 0
