"""Tests for the simulation engine."""

from __future__ import annotations

import pytest

from insatsvaljare.defaults import SimulationConfig
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
            initial_cash=1_000_000,  # way too little
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
        cfg = SimulationConfig(portfolio_return=0.01)  # 1 % portfolio
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


class TestLtvSweep:
    def test_contains_expected_ltvs(self, base_config):
        sweep = ltv_sweep(base_config)
        assert set(sweep["ltv"]).issuperset({0.50, 0.70, 0.85, 0.90})

    def test_baseline_irr_is_none(self, base_config):
        """The 90 % baseline compared to itself has no IRR."""
        sweep = ltv_sweep(base_config)
        irr_at_90 = sweep.loc[sweep["ltv"] == 0.90, "incremental_irr_vs_90"].values[0]
        assert irr_at_90 is None or (isinstance(irr_at_90, float) and irr_at_90 != irr_at_90)  # NaN
