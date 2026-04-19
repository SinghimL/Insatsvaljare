"""Tests for rate lookup and amortization tiers."""

from __future__ import annotations

import pytest

from insatsvaljare.rates import (
    RateScenario,
    amortization_rate,
    base_rate,
    ltv_penalty,
    mortgage_rate,
)


class TestAmortizationRate:
    def test_below_50(self):
        assert amortization_rate(0.30) == 0.0
        assert amortization_rate(0.499) == 0.0

    def test_50_to_70(self):
        assert amortization_rate(0.50) == 0.01
        assert amortization_rate(0.65) == 0.01
        assert amortization_rate(0.699) == 0.01

    def test_above_70(self):
        assert amortization_rate(0.70) == 0.02
        assert amortization_rate(0.85) == 0.02
        assert amortization_rate(0.90) == 0.02


class TestLtvPenalty:
    def test_low_ltv_discount(self):
        assert ltv_penalty(0.40) < 0

    def test_mid_range_flat(self):
        assert ltv_penalty(0.60) == 0

    def test_high_ltv_penalty(self):
        assert ltv_penalty(0.80) > 0
        assert ltv_penalty(0.89) > ltv_penalty(0.80)


class TestScenarioRates:
    def test_ordering(self):
        for m in [3, 12, 60]:
            r_low = base_rate(RateScenario.LOW, m)
            r_base = base_rate(RateScenario.BASE, m)
            r_high = base_rate(RateScenario.HIGH, m)
            assert r_low < r_base < r_high

    def test_term_spread_positive(self):
        for s in RateScenario:
            r_3m = base_rate(s, 3)
            r_10y = base_rate(s, 120)
            assert r_10y > r_3m


class TestMortgageRate:
    def test_combines_base_and_penalty(self):
        r = mortgage_rate(0.85, RateScenario.BASE, 3)
        expected = base_rate(RateScenario.BASE, 3) + ltv_penalty(0.85)
        assert r == pytest.approx(expected)
