"""Tests for the simulation engine."""

from __future__ import annotations

import pytest

from insatsvaljare.defaults import (
    CustomBucket,
    HouseholdMember,
    InvestmentStrategy,
    SimulationConfig,
    TaxModel,
)
from insatsvaljare.model import ltv_sweep, simulate, terminal_net_worth
from insatsvaljare.rates import RateScenario


@pytest.fixture
def base_config():
    return SimulationConfig()


class TestSimulate:
    def test_output_shape(self, base_config):
        df = simulate(base_config)
        assert len(df) == 120  # 10 years × 12 months
        assert "net_worth" in df.columns
        assert "loan" in df.columns
        assert "portfolio" in df.columns

    def test_initial_balances(self, base_config):
        df = simulate(base_config)
        first = df.iloc[0]
        # loan at t=0 should be V × LTV minus one month amortization
        expected_loan_start = base_config.property_value * base_config.ltv_fraction
        assert first["loan"] == pytest.approx(
            expected_loan_start - first["amortization"]
        )

    def test_loan_decreases_monotonically(self, base_config):
        df = simulate(base_config)
        deltas = df["loan"].diff().dropna()
        assert (deltas <= 1e-6).all(), "loan must never increase"

    def test_insufficient_cash_raises(self):
        # LTV 10 % requires 5.4 Mkr insats on 6 Mkr property
        cfg = SimulationConfig(
            property_value=6_000_000,
            ltv_fraction=0.10,
            members=[HouseholdMember(initial_cash=1_000_000)],  # way too little
        )
        with pytest.raises(ValueError, match="insats"):
            simulate(cfg)

    def test_higher_return_favors_higher_ltv(self, base_config):
        """With portfolio return > after-tax interest, higher LTV should win."""
        sweep = ltv_sweep(base_config)
        # Terminal NW should be monotonically non-decreasing with LTV
        # in the high-return regime
        assert sweep.loc[sweep["ltv"] == 0.90, "terminal_net_worth"].values[0] > \
               sweep.loc[sweep["ltv"] == 0.50, "terminal_net_worth"].values[0]

    def test_low_return_favors_lower_ltv(self):
        """With portfolio return < interest rate, lower LTV should win."""
        cfg = SimulationConfig(
            members=[HouseholdMember(rantefond_isk_return=0.01)],  # 1 % portfolio
        )
        sweep = ltv_sweep(cfg)
        # Low-LTV terminal NW should beat high-LTV when return is poor
        nw_50 = sweep.loc[sweep["ltv"] == 0.50, "terminal_net_worth"].values[0]
        nw_90 = sweep.loc[sweep["ltv"] == 0.90, "terminal_net_worth"].values[0]
        assert nw_50 > nw_90

    def test_high_rate_scenario_lower_terminal(self, base_config):
        low = simulate(base_config.model_copy(update={"rate_scenario": RateScenario.LOW}))
        high = simulate(base_config.model_copy(update={"rate_scenario": RateScenario.HIGH}))
        assert terminal_net_worth(high) < terminal_net_worth(low)

    def test_5y_revaluation_reduces_later_amortization(self, base_config):
        """With appreciation, 5y revaluation should lower amort-LTV → less amort."""
        cfg_off = base_config.model_copy(update={"allow_5y_revaluation": False})
        cfg_on = base_config.model_copy(update={"allow_5y_revaluation": True})
        df_off = simulate(cfg_off)
        df_on = simulate(cfg_on)
        # After year 5, amort-LTV should be lower (or equal) with revaluation on
        month_72 = 71  # index
        assert df_on["ltv_amort"].iloc[month_72] <= df_off["ltv_amort"].iloc[month_72]

    def test_sell_at_end_zeros_house(self, base_config):
        cfg = base_config.model_copy(update={"sell_at_end": True})
        df = simulate(cfg)
        last = df.iloc[-1]
        assert last["loan"] == 0
        assert last["house_equity"] == 0


class TestMultiMember:
    def _two_member_cfg(self, **overrides):
        """Two members with the same aggregate cash/income as the default single member.
        5 400 000 = 3 000 000 + 2 400 000.  900 000 = 500 000 + 400 000."""
        members = [
            HouseholdMember(
                name="A",
                initial_cash=3_000_000,
                annual_brutto_income=500_000,
                monthly_personal_expenses=12_000,
            ),
            HouseholdMember(
                name="B",
                initial_cash=2_400_000,
                annual_brutto_income=400_000,
                monthly_personal_expenses=13_000,
            ),
        ]
        base = SimulationConfig(members=members)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    def test_two_members_output_shape_matches_one(self, base_config):
        df_single = simulate(base_config)
        df_multi = simulate(self._two_member_cfg())
        assert len(df_multi) == len(df_single)
        assert set(df_multi.columns) == set(df_single.columns)

    def test_two_members_insats_split_proportional(self):
        """Two-member household with same aggregate cash should still cover insats."""
        cfg = self._two_member_cfg(ltv_fraction=0.10)  # 5.4 Mkr insats needed
        df = simulate(cfg)
        assert df["loan"].iloc[0] > 0  # simulation ran

    def test_two_members_isk_fribelopp_advantage(self):
        """Two ISK holders each get 300 k fribelopp → lower schablonskatt vs one person
        with same aggregate portfolio."""
        two = self._two_member_cfg(ltv_fraction=0.90)  # Big portfolio seed
        one = SimulationConfig(ltv_fraction=0.90)      # Same aggregate cash → same seed
        df_two = simulate(two)
        df_one = simulate(one)
        # Two-member household should end up with slightly higher aggregate portfolio
        # because fribelopp doubles and schablonskatt is less bitey.
        assert df_two["portfolio"].iloc[-1] >= df_one["portfolio"].iloc[-1] - 1e-3

    def test_two_members_shared_cost_split_by_income(self):
        """The high-income member's cash_flow should reflect paying more of shared costs."""
        # Indirect test: household total cash_flow should match single-member
        # approximately (net income is equivalent, costs are the same).
        df_two = simulate(self._two_member_cfg())
        df_one = simulate(SimulationConfig())
        # Loan dynamics are identical (same V, same LTV, same income total)
        assert df_two["loan"].iloc[-1] == pytest.approx(df_one["loan"].iloc[-1])


class TestInvestmentStrategies:
    def test_sparkonto_lower_return_than_isk_for_same_params(self):
        """Sparkonto at 2.5 % should yield less than Räntefond ISK at 6.5 %."""
        m_spark = HouseholdMember(
            name="X",
            strategy=InvestmentStrategy.SPARKONTO,
            sparkonto_return=0.025,
        )
        m_isk = HouseholdMember(
            name="X",
            strategy=InvestmentStrategy.RANTEFOND_ISK,
            rantefond_isk_return=0.065,
        )
        nw_spark = simulate(SimulationConfig(members=[m_spark]))["net_worth"].iloc[-1]
        nw_isk = simulate(SimulationConfig(members=[m_isk]))["net_worth"].iloc[-1]
        assert nw_isk > nw_spark

    def test_tax_none_beats_tax_isk_all_else_equal(self):
        """Zero-tax bucket compounds faster than ISK with schablonskatt."""
        m_isk = HouseholdMember(
            name="X",
            strategy=InvestmentStrategy.ANPASSAD,
            custom_buckets=[
                CustomBucket(allocation_fraction=1.0, annual_return=0.05, tax_model=TaxModel.ISK),
            ],
        )
        m_none = HouseholdMember(
            name="X",
            strategy=InvestmentStrategy.ANPASSAD,
            custom_buckets=[
                CustomBucket(allocation_fraction=1.0, annual_return=0.05, tax_model=TaxModel.NONE),
            ],
        )
        nw_isk = simulate(SimulationConfig(members=[m_isk]))["net_worth"].iloc[-1]
        nw_none = simulate(SimulationConfig(members=[m_none]))["net_worth"].iloc[-1]
        assert nw_none > nw_isk

    def test_anpassad_allocation_must_sum_to_one(self):
        with pytest.raises(ValueError, match="allocation_fraction"):
            HouseholdMember(
                name="X",
                strategy=InvestmentStrategy.ANPASSAD,
                custom_buckets=[
                    CustomBucket(allocation_fraction=0.5, annual_return=0.05, tax_model=TaxModel.ISK),
                    # Sum = 0.5 — not 1.0.
                ],
            )

    def test_anpassad_requires_at_least_one_bucket(self):
        with pytest.raises(ValueError, match="ANPASSAD"):
            HouseholdMember(
                name="X",
                strategy=InvestmentStrategy.ANPASSAD,
                custom_buckets=[],
            )


class TestLtvSweep:
    def test_contains_expected_ltvs(self, base_config):
        sweep = ltv_sweep(base_config)
        assert set(sweep["ltv"]).issuperset({0.50, 0.70, 0.85, 0.90})

    def test_baseline_irr_is_none(self, base_config):
        """The 90 % baseline compared to itself has no IRR."""
        sweep = ltv_sweep(base_config)
        irr_at_90 = sweep.loc[sweep["ltv"] == 0.90, "incremental_irr_vs_90"].values[0]
        assert irr_at_90 is None or (isinstance(irr_at_90, float) and irr_at_90 != irr_at_90)  # NaN
