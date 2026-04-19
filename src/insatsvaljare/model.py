"""Monthly simulation engine for multi-member household LTV optimization.

The engine takes a SimulationConfig with one or more household members
and returns a month-by-month DataFrame of aggregate balances. Per-member
portfolio state is tracked internally; only aggregate `portfolio` and
`net_worth` are exposed in the DataFrame.

Tax effects are applied at year-end (ränteavdrag refunded with
skattereduktion-cap per member, ISK / AF / sparkonto tax deducted
per bucket) to match how they actually land in cash-flow terms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from insatsvaljare.defaults import (
    CustomBucket,
    HouseholdMember,
    InvestmentStrategy,
    SimulationConfig,
    TaxModel,
)
from insatsvaljare.rates import RateScenario, amortization_rate, mortgage_rate
from insatsvaljare.tax import ISK_EFFECTIVE_RATE_2026, ISK_FRIBELOPP_2026
from insatsvaljare.tax_income import compute_net_income


# ----------------------------------------------------------------
# Internal runtime state
# ----------------------------------------------------------------

@dataclass
class _Bucket:
    """One portfolio slot inside a member's strategy."""
    value: float
    annual_return: float
    tax_model: TaxModel
    allocation_fraction: float  # share of saving inflow going here
    year_start_value: float = 0.0
    deposits_ytd: float = 0.0
    # Quarterly openings for ISK kapitalunderlag
    quarterly_openings: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


@dataclass
class _MemberRuntime:
    name: str
    brutto_income_annual: float
    personal_expenses_monthly: float
    buckets: list[_Bucket]
    interest_share_ytd: float = 0.0


def _materialize_buckets(member: HouseholdMember, initial_portfolio: float) -> list[_Bucket]:
    """Build the per-bucket runtime list from a member's strategy config."""
    if member.strategy == InvestmentStrategy.SPARKONTO:
        return [_Bucket(
            value=initial_portfolio,
            annual_return=member.sparkonto_return,
            tax_model=TaxModel.SPARKONTO,
            allocation_fraction=1.0,
            year_start_value=initial_portfolio,
            quarterly_openings=[initial_portfolio, 0.0, 0.0, 0.0],
        )]
    if member.strategy == InvestmentStrategy.RANTEFOND_ISK:
        return [_Bucket(
            value=initial_portfolio,
            annual_return=member.rantefond_isk_return,
            tax_model=TaxModel.ISK,
            allocation_fraction=1.0,
            year_start_value=initial_portfolio,
            quarterly_openings=[initial_portfolio, 0.0, 0.0, 0.0],
        )]
    # ANPASSAD: split initial_portfolio across custom_buckets per allocation.
    out: list[_Bucket] = []
    for cb in member.custom_buckets:
        v0 = initial_portfolio * cb.allocation_fraction
        out.append(_Bucket(
            value=v0,
            annual_return=cb.annual_return,
            tax_model=cb.tax_model,
            allocation_fraction=cb.allocation_fraction,
            year_start_value=v0,
            quarterly_openings=[v0, 0.0, 0.0, 0.0],
        ))
    return out


def _rate_path_for(config: SimulationConfig) -> np.ndarray:
    n_months = config.years * 12
    if config.rate_override is not None:
        return np.full(n_months, config.rate_override, dtype=float)
    r = mortgage_rate(
        config.ltv_fraction,
        config.rate_scenario,
        config.binding_months,
    )
    return np.full(n_months, r, dtype=float)


def _apply_year_end_portfolio_tax(member: _MemberRuntime) -> None:
    """Apply per-bucket year-end tax, then reset trackers.

    ISK / KF share ONE 300 000 kr fribelopp per member (aggregated across
    all their ISK+KF buckets). AF / SPARKONTO tax 30 % of annual gain
    per bucket. NONE: no tax.
    """
    # ---- ISK / KF aggregate with shared fribelopp ----
    isk_like_buckets = [
        b for b in member.buckets if b.tax_model in (TaxModel.ISK, TaxModel.KF)
    ]
    if isk_like_buckets:
        per_bucket_ku = [
            (sum(b.quarterly_openings) + b.deposits_ytd) / 4.0
            for b in isk_like_buckets
        ]
        total_ku = sum(per_bucket_ku)
        taxable = max(0.0, total_ku - ISK_FRIBELOPP_2026)
        if taxable > 0 and total_ku > 0:
            for b, b_ku in zip(isk_like_buckets, per_bucket_ku):
                share = b_ku / total_ku
                b_tax = ISK_EFFECTIVE_RATE_2026 * taxable * share
                b.value = max(0.0, b.value - b_tax)

    # ---- AF / SPARKONTO: 30 % on annual gain ----
    for b in member.buckets:
        if b.tax_model in (TaxModel.AF, TaxModel.SPARKONTO):
            gain = max(0.0, b.value - b.year_start_value - b.deposits_ytd)
            b.value = max(0.0, b.value - gain * 0.30)

    # ---- Reset per-year trackers (start-of-next-year state) ----
    for b in member.buckets:
        b.year_start_value = b.value
        b.deposits_ytd = 0.0
        b.quarterly_openings = [b.value, 0.0, 0.0, 0.0]


def simulate(
    config: SimulationConfig,
    rate_path: np.ndarray | None = None,
    portfolio_monthly_returns: dict[tuple[int, int], np.ndarray] | None = None,
    property_monthly_return: np.ndarray | None = None,
) -> pd.DataFrame:
    """Run the monthly multi-member simulation.

    Returns a DataFrame indexed by month. Aggregate columns:
        year, month_in_year, month, rate
        loan, property_value, interest, amortization, avgift
        portfolio (= Σ members' portfolios)
        cash_flow (= Σ members' cash flows)
        savings  (= Σ members' savings inflows)
        house_equity, net_worth
        ltv_amort, ltv_market
        infeasible (True if any member's monthly cash_flow < −liquidity_buffer)

    Optional Monte Carlo overrides:
        rate_path — length-N monthly rate array, replaces the deterministic
                    scenario+LTV-penalty path.
        portfolio_monthly_returns — dict keyed (member_idx, bucket_idx) to
                    length-N arrays of monthly decimal returns for that
                    bucket. Missing keys fall back to the bucket's
                    deterministic annual_return / 12.
        property_monthly_return — length-N monthly decimal appreciation
                    array, replaces the deterministic compounded rate.
    """
    n_months = config.years * 12
    if rate_path is None:
        rate_path = _rate_path_for(config)
    if len(rate_path) != n_months:
        raise ValueError(f"rate_path length {len(rate_path)} != {n_months}")
    if (
        property_monthly_return is not None
        and len(property_monthly_return) != n_months
    ):
        raise ValueError(
            f"property_monthly_return length {len(property_monthly_return)} != {n_months}"
        )

    if not config.members:
        raise ValueError("SimulationConfig must have at least one household member")

    V0 = config.property_value
    L0 = V0 * config.ltv_fraction
    insats_total = V0 - L0
    total_cash = config.total_initial_cash

    if total_cash < insats_total - 1e-6:
        raise ValueError(
            f"total initial_cash {total_cash:,.0f} < required insats {insats_total:,.0f} "
            f"for LTV {config.ltv_fraction:.0%}"
        )

    # Split insats proportionally to each member's cash; portfolio seed = residual.
    members: list[_MemberRuntime] = []
    for m in config.members:
        share = (m.initial_cash / total_cash) if total_cash > 0 else 0.0
        member_insats = insats_total * share
        member_portfolio_seed = max(0.0, m.initial_cash - member_insats)
        members.append(_MemberRuntime(
            name=m.name,
            brutto_income_annual=m.annual_brutto_income,
            personal_expenses_monthly=m.monthly_personal_expenses,
            buckets=_materialize_buckets(m, member_portfolio_seed),
        ))

    # Shared state
    L = L0
    V = V0
    amort_basis_V = V0
    amort_basis_L0 = L0

    # Year-end reconciliation trackers (aggregate)
    interest_ytd_total = 0.0
    base_monthly_avgift = config.monthly_avgift

    # Per-year monthly-income table (brutto → netto-before-ranteavdrag), indexed by member
    def _member_monthly_netto_for_year(brutto: float) -> float:
        """Netto before ranteavdrag: brutto − kommunal − statlig + JSA, then /12."""
        br = compute_net_income(
            brutto=brutto,
            kommunal_rate=config.kommunal_tax_rate,
            annual_interest=0.0,  # interest treatment at year-end
        )
        return br.netto / 12.0

    monthly_netto = [
        _member_monthly_netto_for_year(m.brutto_income_annual) for m in members
    ]

    # Estimate each year's ränteavdrag refund for UI display (amortised across 12 months).
    # Actual year-end reconciliation uses the precise interest_share_ytd; this estimate
    # is just a forward-looking figure so the monthly-overview chart has a value to show.
    def _estimate_ranteavdrag_monthly(loan_now: float, rate_now: float) -> float:
        total_brutto = sum(m.brutto_income_annual for m in members)
        total = 0.0
        for m in members:
            share = (
                m.brutto_income_annual / total_brutto
                if total_brutto > 0
                else 1.0 / len(members)
            )
            est_interest = loan_now * rate_now * share
            br = compute_net_income(
                brutto=m.brutto_income_annual,
                kommunal_rate=config.kommunal_tax_rate,
                annual_interest=est_interest,
            )
            total += br.ranteavdrag_actual
        return total / 12.0

    ranteavdrag_monthly_est = _estimate_ranteavdrag_monthly(L, rate_path[0])

    rows: list[dict] = []

    for t in range(n_months):
        year = t // 12
        month_in_year = t % 12 + 1
        rate = rate_path[t]

        ltv_market = L / V if V > 0 else 0.0
        ltv_amort = L / amort_basis_V if amort_basis_V > 0 else 0.0
        amort_rate_annual = amortization_rate(ltv_amort)
        amort_m = amort_rate_annual * amort_basis_L0 / 12

        interest_m = L * rate / 12
        current_avgift = (
            base_monthly_avgift * (1 + config.avgift_inflation) ** year
        )

        # Shared costs split proportionally to brutto income.
        total_brutto_this_year = sum(m.brutto_income_annual for m in members)
        shared_cost_total = interest_m + amort_m + current_avgift

        # Apply amort (shared)
        L = max(0.0, L - amort_m)
        interest_ytd_total += interest_m

        household_cash_flow = 0.0
        household_savings = 0.0
        household_brutto_m = 0.0
        household_netto_before_rant_m = 0.0
        household_personal_m = 0.0
        any_infeasible = False
        personal_inflation_factor = (1 + config.personal_expense_inflation) ** year

        for i, mr in enumerate(members):
            brutto_share = (
                mr.brutto_income_annual / total_brutto_this_year
                if total_brutto_this_year > 0
                else 1.0 / len(members)
            )
            shared_cost_share = shared_cost_total * brutto_share
            mr.interest_share_ytd += interest_m * brutto_share

            income_m = monthly_netto[i]
            current_personal = mr.personal_expenses_monthly * personal_inflation_factor
            cash_flow = (
                income_m
                - current_personal
                - shared_cost_share
            )
            if cash_flow < -config.liquidity_buffer:
                any_infeasible = True
            household_cash_flow += cash_flow
            household_brutto_m += mr.brutto_income_annual / 12.0
            household_netto_before_rant_m += income_m
            household_personal_m += current_personal

            savings = max(0.0, cash_flow)
            household_savings += savings

            # Route savings into buckets per strategy allocation_fraction.
            for b_idx, b in enumerate(mr.buckets):
                contribution = savings * b.allocation_fraction
                b.value += contribution
                b.deposits_ytd += contribution
                # Monthly compound growth — stochastic override wins when supplied
                if portfolio_monthly_returns is not None and (i, b_idx) in portfolio_monthly_returns:
                    monthly_r = float(portfolio_monthly_returns[(i, b_idx)][t])
                else:
                    monthly_r = b.annual_return / 12.0
                b.value *= 1 + monthly_r

            # Track quarterly openings at start of Q2/Q3/Q4
            if month_in_year in (4, 7, 10):
                q = (month_in_year - 1) // 3
                for b in mr.buckets:
                    mr_bucket_val_before_q = b.value
                    b.quarterly_openings[q] = mr_bucket_val_before_q

        # Property appreciation (shared) — stochastic override wins when supplied
        if property_monthly_return is not None:
            V *= 1 + float(property_monthly_return[t])
        else:
            V *= (1 + config.property_appreciation) ** (1 / 12)

        # Year-end reconciliation (December)
        if month_in_year == 12:
            for i, mr in enumerate(members):
                # Per-member ränteavdrag with cap
                br = compute_net_income(
                    brutto=mr.brutto_income_annual,
                    kommunal_rate=config.kommunal_tax_rate,
                    annual_interest=mr.interest_share_ytd,
                )
                # monthly_netto already excluded ranteavdrag; credit only the actual
                rant_refund = br.ranteavdrag_actual
                if mr.buckets:
                    # Drop the refund into the first bucket (rough approx;
                    # the refund isn't strictly "invested" but it lands in the
                    # household's capital pool)
                    mr.buckets[0].value += rant_refund
                    mr.buckets[0].deposits_ytd += rant_refund

                # Portfolio-level taxes per bucket (ISK / AF / SPARKONTO / NONE)
                _apply_year_end_portfolio_tax(mr)

                # Reset per-year tracker
                mr.interest_share_ytd = 0.0

            # Income growth for next year (same growth for all members)
            for j in range(len(members)):
                members[j].brutto_income_annual *= 1 + config.income_growth
                monthly_netto[j] = _member_monthly_netto_for_year(
                    members[j].brutto_income_annual
                )

            # 5-year revaluation of amortization basis
            if config.allow_5y_revaluation and (year + 1) % 5 == 0:
                amort_basis_V = V
                amort_basis_L0 = L

            # Refresh the display estimate with the new year's loan + rate
            next_rate = rate_path[min(t + 1, n_months - 1)]
            ranteavdrag_monthly_est = _estimate_ranteavdrag_monthly(L, next_rate)

            # Reset annual tracker
            interest_ytd_total = 0.0

        portfolio_total = sum(b.value for mr in members for b in mr.buckets)
        house_equity = V - L
        tax_gross_m = household_brutto_m - household_netto_before_rant_m
        rows.append({
            "month": t + 1,
            "year": year + 1,
            "month_in_year": month_in_year,
            "loan": L,
            "property_value": V,
            "portfolio": portfolio_total,
            "interest": interest_m,
            "amortization": amort_m,
            "avgift": current_avgift,
            "cash_flow": household_cash_flow,
            "savings": household_savings,
            "rate": rate,
            "brutto_monthly": household_brutto_m,
            "tax_gross_monthly": tax_gross_m,
            "ranteavdrag_monthly": ranteavdrag_monthly_est,
            "personal_expenses_monthly": household_personal_m,
            "ltv_amort": ltv_amort,
            "ltv_market": ltv_market,
            "house_equity": house_equity,
            "net_worth": house_equity + portfolio_total,
            "infeasible": any_infeasible,
        })

    df = pd.DataFrame(rows)

    # Apply exit scenario at horizon end if requested
    if config.sell_at_end:
        last = df.iloc[-1]
        sale_price = last["property_value"]
        broker_fee = sale_price * config.broker_fee_fraction
        net_sale = sale_price - broker_fee - last["loan"]
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
    """IRR on the cash-flow differential between two LTV choices."""
    cf_diff = (df_candidate["cash_flow"] - df_baseline["cash_flow"]).to_numpy()
    terminal_diff = (
        df_candidate["net_worth"].iloc[-1] - df_baseline["net_worth"].iloc[-1]
    )
    flows = np.concatenate([
        [-initial_insats_diff],
        cf_diff[:-1],
        [cf_diff[-1] + terminal_diff],
    ])

    if np.all(flows >= 0) or np.all(flows <= 0):
        return None

    def npv(rate_monthly: float) -> float:
        t = np.arange(len(flows))
        return float(np.sum(flows / (1 + rate_monthly) ** t))

    lo, hi = -0.10, 0.10
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
