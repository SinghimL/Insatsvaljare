"""Streamlit entry point for the Insatsväljare LTV model."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insatsvaljare.defaults import SimulationConfig
from insatsvaljare.model import (
    incremental_irr,
    ltv_sweep,
    simulate,
    terminal_net_worth,
)
from insatsvaljare.rates import (
    RateScenario,
    amortization_rate,
    mortgage_rate,
)
from insatsvaljare.stabelo import (
    FIXATION_MONTHS,
    fetch_rate_table,
    load_or_fetch,
    lookup_rate,
    save_snapshot,
)
from insatsvaljare.tax import AccountType

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "ref" / "stabelo_snapshot.json"

st.set_page_config(
    page_title="Insatsväljare för bostadsrätt",
    page_icon="🏠",
    layout="wide",
)


# ----------------------------------------------------------------
# Cached helpers
# ----------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _run_sim(config_json: str):
    cfg = SimulationConfig.model_validate_json(config_json)
    return simulate(cfg)


@st.cache_data(show_spinner=False)
def _run_sweep(config_json: str):
    cfg = SimulationConfig.model_validate_json(config_json)
    return ltv_sweep(cfg)


@st.cache_resource(show_spinner=False)
def _load_stabelo_snapshot():
    try:
        return load_or_fetch(SNAPSHOT_PATH, force_refresh=False)
    except Exception as e:
        st.warning(f"Kunde inte ladda Stabelo-snapshot: {e}")
        return []


# ----------------------------------------------------------------
# Sidebar — inputs
# ----------------------------------------------------------------

st.sidebar.title("🏠 Insatsväljare för bostadsrätt")
st.sidebar.caption("Simulering av bostadsrättsköp under 2026 års bolåneregler")

with st.sidebar.expander("📍 Bostad", expanded=True):
    property_value = st.number_input(
        "Köpeskilling (kr)",
        min_value=1_000_000,
        max_value=30_000_000,
        value=6_000_000,
        step=100_000,
    )
    living_area_m2 = st.number_input("Boarea (m²)", 20, 300, 55, 1)
    avgift_per_m2 = st.number_input(
        "Månadsavgift (kr/m²/mån)", 10.0, 200.0, 60.0, 1.0
    )
    appreciation = st.slider(
        "Värdeökning (%/år)", -2.0, 10.0, 4.0, 0.25
    ) / 100
    avgift_inflation = st.slider(
        "Avgiftsinflation (%/år)", 0.0, 8.0, 2.5, 0.25
    ) / 100

with st.sidebar.expander("⏱ Tidshorisont", expanded=True):
    years = st.slider(
        "Innehavstid (år)",
        min_value=1,
        max_value=30,
        value=10,
        step=1,
        help=(
            "Simuleringens längd. Amortering, ISK schablonskatt och "
            "värdeökning räknas månadsvis över hela horisonten."
        ),
    )

with st.sidebar.expander("💰 Lån", expanded=True):
    ltv_pct = st.slider("Belåningsgrad (%)", 10, 90, 85, 5)
    binding_label = st.selectbox(
        "Bindningstid",
        list(FIXATION_MONTHS.keys()),
        index=0,
    )
    binding_months = FIXATION_MONTHS[binding_label]
    scenario_label = st.selectbox(
        "Räntescenario",
        ["LOW (låg)", "BASE (basscenario)", "HIGH (hög)"],
        index=1,
    )
    scenario = RateScenario[scenario_label.split(" ")[0]]

    # Stabelo live lookup
    records = _load_stabelo_snapshot()
    stabelo_rate = None
    if records:
        stabelo_rate = lookup_rate(
            records,
            ltv_pct=ltv_pct,
            binding_months=binding_months,
            amount_kr=property_value * ltv_pct / 100,
        )
    scenario_rate = mortgage_rate(ltv_pct / 100, scenario, binding_months)
    st.caption(
        f"Stabelo snapshot: **{stabelo_rate:.2f} %**"
        if stabelo_rate is not None
        else "Stabelo: saknas för denna LTV/bindningstid"
    )
    st.caption(f"Scenario ({scenario.value}): **{scenario_rate * 100:.2f} %**")

    use_stabelo = st.checkbox(
        "Använd Stabelo snapshot-ränta",
        value=stabelo_rate is not None,
        disabled=stabelo_rate is None,
    )
    rate_override = (
        stabelo_rate / 100 if (use_stabelo and stabelo_rate is not None) else None
    )
    if st.button("🔄 Uppdatera Stabelo-räntor"):
        try:
            new_records = fetch_rate_table()
            save_snapshot(new_records, SNAPSHOT_PATH)
            _load_stabelo_snapshot.clear()
            st.success(f"Uppdaterat ({len(new_records)} poster)")
            st.rerun()
        except Exception as e:
            st.error(f"Misslyckades: {e}")

with st.sidebar.expander("🏠 Amortering", expanded=False):
    allow_5y = st.checkbox(
        "Tillåt omvärdering vart 5:e år",
        value=False,
        help=(
            "Av: amorteringsgrund (V₀) fryst under hela horisonten. "
            "På: vart femte år omvärderas bostaden till aktuellt "
            "marknadsvärde, vilket kan sänka amortering."
        ),
    )

with st.sidebar.expander("👤 Hushåll", expanded=True):
    initial_cash_m = st.number_input(
        "Tillgänglig insats + investering (Mkr)",
        0.5,
        30.0,
        5.4,
        0.1,
        help=(
            "Total köpkraft. Måste räcka till insats vid vald LTV. "
            "Överskott investeras — detta är modellens kärnmekanism."
        ),
    )
    initial_cash = initial_cash_m * 1_000_000
    annual_income_kkr = st.number_input(
        "Hushållsinkomst brutto (tkr/år)",
        100,
        10_000,
        900,
        10,
    )
    monthly_living = st.number_input(
        "Månadsutgift ex. boende (kr)",
        5_000,
        200_000,
        25_000,
        1_000,
    )
    income_growth = st.slider("Inkomstökning (%/år)", 0.0, 8.0, 3.0, 0.25) / 100
    liquidity_buffer = st.number_input(
        "Likviditets­buffert (kr)", 0, 500_000, 50_000, 10_000
    )

with st.sidebar.expander("📈 Investering", expanded=True):
    portfolio_return = st.slider(
        "Förväntad portföljavkastning (%/år)", 0.0, 15.0, 6.5, 0.25
    ) / 100
    account_label = st.radio(
        "Konto­typ",
        ["ISK", "KF", "Övrigt (anpassad skatt)"],
        index=0,
        horizontal=True,
    )
    if account_label == "ISK":
        account_type = AccountType.ISK
    elif account_label == "KF":
        account_type = AccountType.KF
    else:
        account_type = AccountType.OTHER

    if account_type in (AccountType.ISK, AccountType.KF):
        n_persons = st.radio(
            "Antal personer (för fribelopp)",
            [1, 2],
            index=0,
            horizontal=True,
        )
        st.caption(
            f"Fribelopp: {n_persons * 300_000:,} kr; "
            f"effektiv skatt 1,065 % på överskjutande"
        )
        other_rate = 0.30  # unused
    else:
        n_persons = 1
        other_rate = st.slider(
            "Realisationsvinstskatt (%)",
            0, 35, 30, 1,
        ) / 100

with st.sidebar.expander("🏁 Exit vid horisontens slut", expanded=False):
    sell_at_end = st.checkbox(
        f"Sälj bostaden år {years}", value=False
    )
    broker_fee = st.slider("Mäklararvode (%)", 0.0, 8.0, 4.0, 0.25) / 100


config = SimulationConfig(
    property_value=float(property_value),
    living_area_m2=float(living_area_m2),
    monthly_avgift_per_m2=float(avgift_per_m2),
    property_appreciation=appreciation,
    avgift_inflation=avgift_inflation,
    ltv_fraction=ltv_pct / 100,
    binding_months=binding_months,
    rate_scenario=scenario,
    rate_override=rate_override,
    initial_cash=initial_cash,
    allow_5y_revaluation=allow_5y,
    annual_gross_income=annual_income_kkr * 1_000,
    monthly_living_cost=float(monthly_living),
    income_growth=income_growth,
    liquidity_buffer=float(liquidity_buffer),
    portfolio_return=portfolio_return,
    account_type=account_type,
    n_persons_for_fribelopp=int(n_persons),
    other_account_tax_rate=other_rate,
    sell_at_end=sell_at_end,
    broker_fee_fraction=broker_fee,
    years=int(years),
)

# Feasibility check upfront
required_insats = config.property_value * (1 - config.ltv_fraction)
if config.initial_cash < required_insats:
    st.error(
        f"Otillräcklig insats: du har {config.initial_cash:,.0f} kr men behöver "
        f"{required_insats:,.0f} kr för LTV {ltv_pct} %."
    )
    st.stop()


# ----------------------------------------------------------------
# Main body
# ----------------------------------------------------------------

df = _run_sim(config.model_dump_json())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Terminal nettoförmögenhet", f"{terminal_net_worth(df):,.0f} kr")
col2.metric("Slutligt bolån", f"{df['loan'].iloc[-1]:,.0f} kr")
col3.metric("Slutlig portfölj", f"{df['portfolio'].iloc[-1]:,.0f} kr")
col4.metric(
    "Infeasible månader",
    int(df["infeasible"].sum()),
    delta_color="inverse",
    help="Antal månader där cash_flow < −likviditetsbuffert (budgeten gick i kras)",
)

# Main chart: net worth decomposition over time
st.subheader("Förmögenhet över tid")
df_plot = df.assign(
    år=df["month"] / 12,
)
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_plot["år"], y=df_plot["house_equity"],
    name="Bostad (equity)", stackgroup="one",
    line=dict(color="#2e7d32"),
))
fig.add_trace(go.Scatter(
    x=df_plot["år"], y=df_plot["portfolio"],
    name="Portfölj", stackgroup="one",
    line=dict(color="#1976d2"),
))
fig.add_trace(go.Scatter(
    x=df_plot["år"], y=df_plot["net_worth"],
    name="Netto (total)",
    line=dict(color="#333", width=3, dash="dash"),
))
fig.update_layout(
    height=400,
    xaxis_title="År",
    yaxis_title="kr",
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.15),
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig, width="stretch")


# LTV sweep comparison
st.subheader("Jämförelse över LTV-val")
sweep = _run_sweep(config.model_dump_json())
sweep_display = sweep.copy()
sweep_display["ltv"] = (sweep_display["ltv"] * 100).round(0).astype(int).astype(str) + " %"
sweep_display["terminal_net_worth"] = sweep_display["terminal_net_worth"].map(lambda x: f"{x:,.0f}")
sweep_display["final_loan"] = sweep_display["final_loan"].map(lambda x: f"{x:,.0f}")
sweep_display["final_portfolio"] = sweep_display["final_portfolio"].map(lambda x: f"{x:,.0f}")
sweep_display["incremental_irr_vs_90"] = sweep_display["incremental_irr_vs_90"].map(
    lambda x: f"{x * 100:.2f} %" if pd.notna(x) else "—"
)
st.dataframe(
    sweep_display.rename(columns={
        "ltv": "LTV",
        "terminal_net_worth": "Terminal NW (kr)",
        "infeasible_months": "Inf. mån",
        "final_loan": "Slutlån (kr)",
        "final_portfolio": "Slutportfölj (kr)",
        "incremental_irr_vs_90": "Inkrementell IRR vs 90 %",
    }),
    hide_index=True,
    width="stretch",
)

# LTV sweep chart
fig_sweep = px.bar(
    sweep, x="ltv", y="terminal_net_worth",
    labels={"ltv": "LTV", "terminal_net_worth": "Terminal nettoförmögenhet (kr)"},
)
fig_sweep.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
fig_sweep.update_xaxes(tickformat=".0%")
st.plotly_chart(fig_sweep, width="stretch")


# Monthly cash flow breakdown
with st.expander("📊 Månadsvis kassaflöde (detalj)", expanded=False):
    flow_cols = ["interest", "amortization", "avgift"]
    df_flow = df_plot[["år"] + flow_cols].copy()
    df_flow_long = df_flow.melt(id_vars="år", var_name="Post", value_name="kr")
    fig_flow = px.area(
        df_flow_long, x="år", y="kr", color="Post",
        labels={"år": "År"},
    )
    fig_flow.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_flow, width="stretch")


with st.expander("🔬 Räntekänslighet (±1 pp shock)", expanded=False):
    rows = []
    for shock in [-0.01, 0.0, 0.01]:
        test_cfg = config.model_copy(update={
            "rate_override": (
                (rate_override if rate_override is not None else mortgage_rate(
                    config.ltv_fraction, config.rate_scenario, config.binding_months,
                )) + shock
            ),
        })
        test_df = simulate(test_cfg)
        rows.append({
            "Skift (pp)": f"{shock * 100:+.0f}",
            "Effektiv ränta": f"{test_cfg.rate_override * 100:.2f} %",
            "Terminal NW": f"{terminal_net_worth(test_df):,.0f} kr",
            "Inf. mån": int(test_df["infeasible"].sum()),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


st.caption(
    "Modellregler: 2026-04-01 FI-reform (LTV-tak 90 %, amortering 0/1/2 %-trappa, "
    "avskaffat 4,5×-tillägg). ISK 2026: 300 000 kr fribelopp, 1,065 % på överskott. "
    "Se `ref/swedish-mortgage-policy-2026.md` för källor."
)
