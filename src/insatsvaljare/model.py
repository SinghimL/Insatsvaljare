"""Monthly simulation engine for LTV optimization over a configurable horizon.

The engine takes a SimulationConfig + a monthly interest rate path and
returns a month-by-month DataFrame of balances. Tax effects are applied
at year-end (ränteavdrag refunded, ISK schablonskatt deducted) to match
how they're actually experienced in cash-flow terms.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from insatsvaljare.defaults import SimulationConfig
from insatsvaljare.rates import amortization_rate, mortgage_rate, RateScenario
from insatsvaljare.tax import (
    AccountType,
    annual_investment_tax,
    ranteavdrag,
)


def _rate_path_for(config: SimulationConfig) -> np.ndarray:
    """Build a monthly rate path from config (deterministic scenario)."""
    n_months = config.years * 12
    if config.rate_override is not None:
        return np.full(n_months, config.rate_override, dtype=float)
    r = mortgage_rate(
        config.ltv_fraction,
        config.rate_scenario,
        config.binding_months,
    )
    return np.full(n_months, r, dtype=float)


def simulate(
    config: SimulationConfig,
    rate_path: np.ndarray | None = None,
) -> pd.DataFrame:
    """Run the monthly simulation. Returns a DataFrame indexed by month.

    Columns:
        year, month_in_year, month
        loan              — outstanding loan balance
        property_value    — current market value (grows with appreciation)
        portfolio         — investment account balance
        interest          — monthly interest paid
        amortization      — monthly mandatory amortization
        avgift            — monthly BRF fee
        cash_flow         — income − living − interest − amort − avgift
        savings           — max(0, cash_flow) flowing into portfolio
        rate              — annual nominal rate in effect
        ltv_amort         — LTV used for amortization-tier determination
        ltv_market        — current market LTV (V_t basis)
        house_equity      — property_value − loan
        net_worth         — house_equity + portfolio
        infeasible        — True if monthly cash_flow < −liquidity_buffer
    """
    n_months = config.years * 12
    if rate_path is None:
        rate_path = _rate_path_for(config)
    if len(rate_path) != n_months:
        raise ValueError(f"rate_path length {len(rate_path)} != {n_months}")

    # Initial state
    L0 = config.property_value * config.ltv_fraction
    V0 = config.property_value
    insats = V0 - L0
    if config.initial_cash < insats - 1e-6:
        raise ValueError(
            f"initial_cash {config.initial_cash:,.0f} < required insats {insats:,.0f} "
            f"for LTV {config.ltv_fraction:.0%}"
        )
    L = L0
    V = V0
    # Excess cash beyond insats seeds the investment portfolio — this is
    # the lever the model exists to analyze.
    P = config.initial_cash - insats

    # Amortization basis: frozen at purchase V unless user opted in to
    # 5-year revaluation.
    amort_basis_V = V0
    amort_basis_L0 = L0  # annual mandatory amort is a % of this

    # Household cash-flow series that evolve yearly
    annual_income = config.annual_gross_income
    monthly_income = annual_income / 12
    monthly_living = config.monthly_living_cost
    annual_avgift_per_m2 = config.monthly_avgift_per_m2

    # Year-end bookkeeping
    interest_ytd = 0.0
    deposits_ytd = 0.0

    # Q1 opening for the kapitalunderlag formula is the start-of-year
    # balance — at t=0 that's the freed-cash seed.
    quarterly_openings = [P, 0.0, 0.0, 0.0]

    rows: list[dict] = []

    for t in range(n_months):
        year = t // 12
        month_in_year = t % 12 + 1

        # Current rate (possibly time-varying via rate_path)
        rate = rate_path[t]

        # Market LTV (for reporting)
        ltv_market = L / V if V > 0 else 0.0

        # Amortization tier uses basis-LTV (L_current / amort_basis_V)
        ltv_amort = L / amort_basis_V if amort_basis_V > 0 else 0.0
        amort_rate_annual = amortization_rate(ltv_amort)
        amort_m = amort_rate_annual * amort_basis_L0 / 12

        # Interest this month
        interest_m = L * rate / 12

        # Monthly avgift — grows once per year (in Jan = month_in_year==1)
        current_avgift = (
            annual_avgift_per_m2
            * config.living_area_m2
            * (1 + config.avgift_inflation) ** year
        )

        # Cash flow
        cash_flow = (
            monthly_income
            - monthly_living
            - interest_m
            - amort_m
            - current_avgift
        )
        infeasible = cash_flow < -config.liquidity_buffer

        # Apply: reduce loan, add savings to portfolio
        L = max(0.0, L - amort_m)
        savings = max(0.0, cash_flow)
        P += savings
        deposits_ytd += savings
        # Portfolio grows monthly
        P *= 1 + config.portfolio_return / 12

        # Track quarterly openings (at month 1, 4, 7, 10 — value BEFORE additions)
        # We approximate "opening" with balance at start of each quarter.
        if month_in_year in (4, 7, 10):
            q = (month_in_year - 1) // 3
            quarterly_openings[q] = P

        interest_ytd += interest_m

        # Appreciation compounds monthly
        V *= (1 + config.property_appreciation) ** (1 / 12)

        # Year-end reconciliation (December)
        if month_in_year == 12:
            # Ränteavdrag: skattereduktion refunded in the following year's
            # tax return. For cash-flow purposes we credit at year-end.
            credit = ranteavdrag(interest_ytd)
            P += credit

            # Investment account tax (schablonskatt or realized-gains)
            # Approximate realized gains as the year's net portfolio growth
            # minus deposits (used only for "other" account type).
            realized_gains_estimate = max(0.0, P - quarterly_openings[0] - deposits_ytd - credit)
            inv_tax = annual_investment_tax(
                account_type=config.account_type,
                quarterly_openings=quarterly_openings,
                annual_deposits=deposits_ytd,
                realized_gains=realized_gains_estimate,
                n_persons=config.n_persons_for_fribelopp,
                other_rate=config.other_account_tax_rate,
            )
            P = max(0.0, P - inv_tax)

            # Income growth takes effect at January
            annual_income *= 1 + config.income_growth
            monthly_income = annual_income / 12

            # 5-year revaluation (optional) — re-anchor amortization basis
            # to current market value. Only kicks in at end of year 5
            # (and 10, though that's our horizon).
            if config.allow_5y_revaluation and (year + 1) % 5 == 0:
                amort_basis_V = V
                amort_basis_L0 = L

            # Reset YTD trackers for next year
            interest_ytd = 0.0
            deposits_ytd = 0.0
            # Q1 opening of the *next* year is current P
            quarterly_openings = [P, 0.0, 0.0, 0.0]

        house_equity = V - L
        rows.append({
            "month": t + 1,
            "year": year + 1,
            "month_in_year": month_in_year,
            "loan": L,
            "property_value": V,
            "portfolio": P,
            "interest": interest_m,
            "amortization": amort_m,
            "avgift": current_avgift,
            "cash_flow": cash_flow,
            "savings": savings,
            "rate": rate,
            "ltv_amort": ltv_amort,
            "ltv_market": ltv_market,
            "house_equity": house_equity,
            "net_worth": house_equity + P,
            "infeasible": infeasible,
        })

    df = pd.DataFrame(rows)

    # Apply exit scenario at horizon end if requested
    if config.sell_at_end:
        last = df.iloc[-1]
        sale_price = last["property_value"]
        broker_fee = sale_price * config.broker_fee_fraction
        net_sale = sale_price - broker_fee - last["loan"]
        # Simplified: reavinst tax only on realized gain vs. purchase price.
        gain = max(0.0, sale_price - config.property_value)
        reavinst_tax = gain * 0.22
        exit_cash = net_sale - reavinst_tax
        df.loc[df.index[-1], "portfolio"] = last["portfolio"] + exit_cash
        df.loc[df.index[-1], "loan"] = 0.0
        df.loc[df.index[-1], "house_equity"] = 0.0
        df.loc[df.index[-1], "property_value"] = 0.0
        df.loc[df.index[-1], "net_worth"] = df.loc[df.index[-1], "portfolio"]

    return df


def terminal_net_worth(df: pd.DataFrame) -> float:
    return float(df["net_worth"].iloc[-1])


def incremental_irr(
    df_candidate: pd.DataFrame,
    df_baseline: pd.DataFrame,
    initial_insats_diff: float,
) -> float | None:
    """IRR on the cash-flow differential between two LTV choices.

    Models the decision "put more insats in now" as:
      t=0:  −(insats_cand − insats_base)   [extra cash out of portfolio]
      t=1..T:  (CF_cand − CF_base)         [ongoing monthly difference]
      t=T:  + (NW_cand − NW_base)          [terminal delta realized]

    Returns annualized IRR; None if no sign change makes IRR undefined.
    """
    cf_diff = (df_candidate["cash_flow"] - df_baseline["cash_flow"]).to_numpy()
    terminal_diff = (
        df_candidate["net_worth"].iloc[-1] - df_baseline["net_worth"].iloc[-1]
    )
    flows = np.concatenate([
        [-initial_insats_diff],
        cf_diff[:-1],
        [cf_diff[-1] + terminal_diff],
    ])

    # Simple IRR via bisection on NPV sign
    if np.all(flows >= 0) or np.all(flows <= 0):
        return None

    def npv(rate_monthly: float) -> float:
        t = np.arange(len(flows))
        return float(np.sum(flows / (1 + rate_monthly) ** t))

    lo, hi = -0.10, 0.10  # monthly rate bounds
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-2:
            break
        if npv(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    monthly = (lo + hi) / 2
    return (1 + monthly) ** 12 - 1


def ltv_sweep(
    base_config: SimulationConfig,
    ltv_values: list[float] | None = None,
) -> pd.DataFrame:
    """Run the simulation across a range of LTVs. Returns summary per LTV."""
    if ltv_values is None:
        ltv_values = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90]

    baseline = base_config.model_copy(update={"ltv_fraction": 0.90})
    baseline_df = simulate(baseline)
    baseline_insats = base_config.property_value * (1 - 0.90)

    rows = []
    for ltv in ltv_values:
        cfg = base_config.model_copy(update={"ltv_fraction": ltv})
        try:
            df = simulate(cfg)
        except ValueError:
            continue
        insats = base_config.property_value * (1 - ltv)
        rows.append({
            "ltv": ltv,
            "terminal_net_worth": terminal_net_worth(df),
            "infeasible_months": int(df["infeasible"].sum()),
            "final_loan": float(df["loan"].iloc[-1]),
            "final_portfolio": float(df["portfolio"].iloc[-1]),
            "incremental_irr_vs_90": incremental_irr(
                df, baseline_df, insats - baseline_insats
            ),
        })
    return pd.DataFrame(rows)
