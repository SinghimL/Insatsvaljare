"""Tests for tax calculations."""

from __future__ import annotations

import pytest

from insatsvaljare.tax import (
    AccountType,
    annual_investment_tax,
    effective_interest_rate,
    isk_kapitalunderlag,
    isk_schablonskatt,
    other_account_tax,
    ranteavdrag,
)


class TestRanteavdrag:
    def test_below_cap(self):
        assert ranteavdrag(50_000) == pytest.approx(15_000)  # 30%

    def test_at_cap(self):
        assert ranteavdrag(100_000) == pytest.approx(30_000)

    def test_above_cap(self):
        # 100k * 0.30 + 50k * 0.21 = 30_000 + 10_500
        assert ranteavdrag(150_000) == pytest.approx(40_500)

    def test_zero(self):
        assert ranteavdrag(0) == 0

    def test_negative_is_zero(self):
        assert ranteavdrag(-100) == 0


class TestIskKapitalunderlag:
    def test_basic(self):
        # (1M + 1M + 1M + 1M + 100k deposits) / 4 = 1.025M
        assert isk_kapitalunderlag(
            [1_000_000] * 4, 100_000
        ) == pytest.approx(1_025_000)

    def test_wrong_quarters(self):
        with pytest.raises(ValueError):
            isk_kapitalunderlag([1_000_000] * 3, 0)


class TestIskSchablonskatt:
    def test_below_fribelopp_no_tax(self):
        # 200k balance, 1 person, fribelopp 300k → no tax
        tax = isk_schablonskatt([200_000] * 4, 0, n_persons=1)
        assert tax == pytest.approx(0)

    def test_at_fribelopp_no_tax(self):
        tax = isk_schablonskatt([300_000] * 4, 0, n_persons=1)
        assert tax == pytest.approx(0)

    def test_above_fribelopp(self):
        # 1M avg, fribelopp 300k → 700k taxable × 1.065% = 7,455
        tax = isk_schablonskatt([1_000_000] * 4, 0, n_persons=1)
        assert tax == pytest.approx(7_455)

    def test_two_persons_double_fribelopp(self):
        # 600k balance, 2 persons, fribelopp 600k → no tax
        tax = isk_schablonskatt([600_000] * 4, 0, n_persons=2)
        assert tax == pytest.approx(0)


class TestOtherAccountTax:
    def test_default_30pct(self):
        assert other_account_tax(100_000) == pytest.approx(30_000)

    def test_custom_rate(self):
        assert other_account_tax(100_000, rate=0.22) == pytest.approx(22_000)

    def test_no_gain_no_tax(self):
        assert other_account_tax(-10_000) == 0
        assert other_account_tax(0) == 0


class TestAnnualInvestmentTax:
    def test_isk_dispatch(self):
        t = annual_investment_tax(
            AccountType.ISK,
            quarterly_openings=[1_000_000] * 4,
            annual_deposits=0,
            realized_gains=0,
        )
        assert t > 0  # ISK always charges even without realization

    def test_other_realizes(self):
        t = annual_investment_tax(
            AccountType.OTHER,
            quarterly_openings=[1_000_000] * 4,
            annual_deposits=0,
            realized_gains=100_000,
            other_rate=0.30,
        )
        assert t == pytest.approx(30_000)

    def test_kf_same_as_isk(self):
        isk_t = annual_investment_tax(
            AccountType.ISK,
            quarterly_openings=[1_000_000] * 4,
            annual_deposits=0,
            realized_gains=0,
        )
        kf_t = annual_investment_tax(
            AccountType.KF,
            quarterly_openings=[1_000_000] * 4,
            annual_deposits=0,
            realized_gains=0,
        )
        assert isk_t == kf_t


class TestEffectiveInterestRate:
    def test_below_kink(self):
        # 3 % on 50k interest → all tier 1 → 3 % × (1 − 0.30) = 2.10 %
        eff = effective_interest_rate(0.03, 50_000)
        assert eff == pytest.approx(0.021, abs=1e-4)

    def test_zero_interest(self):
        assert effective_interest_rate(0.03, 0) == 0.03
