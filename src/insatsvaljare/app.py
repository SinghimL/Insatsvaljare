"""Streamlit entry point for the Insatsväljare LTV model."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insatsvaljare.defaults import SimulationConfig
from insatsvaljare.model import (
    ltv_sweep,
    simulate,
    terminal_net_worth,
)
from insatsvaljare.rates import (
    RateScenario,
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


def _horizon_dates(years: int) -> pd.DatetimeIndex:
    """Month-end dates for each simulated month, starting from the current month."""
    today = pd.Timestamp.today()
    start = pd.Timestamp(year=today.year, month=today.month, day=1)
    return pd.date_range(start=start, periods=years * 12, freq="ME")

st.set_page_config(
    page_title="Insatsväljare för bostadsrätt",
    page_icon="🏠",
    layout="wide",
)


# ----------------------------------------------------------------
# Money formatting helpers
# ----------------------------------------------------------------

def format_money(value: float | int) -> str:
    return f"{int(round(float(value))):,}".replace(",", " ")


def parse_money(text: str) -> int | None:
    stripped = (
        text.replace(" ", "")
        .replace(",", "")
        .replace("kr", "")
        .replace("KR", "")
        .strip()
    )
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _reformat_money_key(key: str) -> None:
    parsed = parse_money(st.session_state[key])
    if parsed is not None:
        st.session_state[key] = format_money(parsed)


def money_input(
    label: str,
    key: str,
    default: int,
    min_val: int = 0,
    max_val: int | None = None,
    help: str | None = None,
) -> int:
    if key not in st.session_state:
        st.session_state[key] = format_money(default)
    st.text_input(
        label,
        key=key,
        help=help,
        on_change=_reformat_money_key,
        args=(key,),
    )
    parsed = parse_money(st.session_state[key])
    if parsed is None:
        return default
    if parsed < min_val:
        parsed = min_val
    if max_val is not None and parsed > max_val:
        parsed = max_val
    return parsed


# ----------------------------------------------------------------
# Cached helpers
# ----------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _run_three_scenarios(config_json: str, user_insats_kr: int):
    base = SimulationConfig.model_validate_json(config_json)
    V = base.property_value
    cash = base.initial_cash

    insats_min = 0.10 * V
    insats_max = min(cash, V)

    insats_a = insats_max
    ltv_a = max(0.0, (V - insats_a) / V)
    insats_b = insats_min
    ltv_b = 0.90
    insats_c = max(insats_min, min(insats_max, float(user_insats_kr)))
    ltv_c = max(0.0, (V - insats_c) / V)

    out = {}
    # Scenarios A and B use per-LTV scenario rate (not the user's Stabelo
    # override, which was priced for the user's chosen LTV tier only).
    # Scenario C keeps whatever rate_override the user configured.
    for key, ltv, insats, keep_override in [
        ("A", ltv_a, insats_a, False),
        ("B", ltv_b, insats_b, False),
        ("C", ltv_c, insats_c, True),
    ]:
        update = {"ltv_fraction": ltv, "sell_at_end": False}
        if not keep_override:
            update["rate_override"] = None
        cfg_hold = base.model_copy(update=update)
        df_hold = simulate(cfg_hold)
        cfg_sell = cfg_hold.model_copy(update={"sell_at_end": True})
        df_sell = simulate(cfg_sell)
        out[key] = {
            "df": df_hold,
            "ltv": ltv,
            "insats": insats,
            "net_worth_if_sold": float(df_sell["net_worth"].iloc[-1]),
            "infeasible_months": int(df_hold["infeasible"].sum()),
        }
    return out


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
# Sidebar — inputs (everything except Lån)
# ----------------------------------------------------------------

st.sidebar.title("🏠 Insatsväljare för bostadsrätt")
st.sidebar.caption("Simulering av bostadsrättsköp under 2026 års bolåneregler")

with st.sidebar.expander("📍 Bostad", expanded=True):
    property_value = money_input(
        "Köpeskilling (kr)",
        key="property_value_text",
        default=6_000_000,
        min_val=1_000_000,
        max_val=30_000_000,
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
    initial_cash = money_input(
        "Tillgänglig insats + investering (kr)",
        key="initial_cash_text",
        default=5_400_000,
        min_val=0,
        max_val=50_000_000,
        help=(
            "Total köpkraft. Måste räcka till insats (minst 10 % av "
            "köpeskilling). Överskott investeras — detta är modellens "
            "kärnmekanism."
        ),
    )
    annual_income = money_input(
        "Hushållsinkomst brutto (kr/år)",
        key="annual_income_text",
        default=900_000,
        min_val=0,
        max_val=20_000_000,
    )
    monthly_living = money_input(
        "Månadsutgift ex. boende (kr)",
        key="monthly_living_text",
        default=25_000,
        min_val=0,
        max_val=500_000,
    )
    income_growth = st.slider("Inkomstökning (%/år)", 0.0, 8.0, 3.0, 0.25) / 100
    liquidity_buffer = money_input(
        "Likviditetsbuffert (kr)",
        key="liquidity_buffer_text",
        default=50_000,
        min_val=0,
        max_val=1_000_000,
    )

with st.sidebar.expander("📈 Investering", expanded=True):
    portfolio_return = st.slider(
        "Förväntad portföljavkastning (%/år)", 0.0, 15.0, 6.5, 0.25
    ) / 100
    account_label = st.radio(
        "Kontotyp",
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
            f"Fribelopp: {format_money(n_persons * 300_000)} kr; "
            f"effektiv skatt 1,065 % på överskjutande"
        )
        other_rate = 0.30
    else:
        n_persons = 1
        other_rate = st.slider(
            "Realisationsvinstskatt (%)",
            0, 35, 30, 1,
        ) / 100

with st.sidebar.expander("🏁 Exit (annotering)", expanded=False):
    broker_fee = st.slider("Mäklararvode (%)", 0.0, 8.0, 4.0, 0.25) / 100
    st.caption(
        "Huvudvyn förutsätter innehav till horisontens slut. "
        "Annoteringen under tabellen visar netto om du säljer vid slutet "
        "(22 % reavinstskatt + mäklararvode)."
    )


# ----------------------------------------------------------------
# Top: Lån group (main decision panel)
# ----------------------------------------------------------------

st.title("🏠 Insatsväljare")

V = float(property_value)
cash = float(initial_cash)

insats_min_kr = int(round(0.10 * V))
insats_max_kr = int(round(min(cash, V)))
ltv_min_pct = max(0, int(round((V - insats_max_kr) / V * 100)))
ltv_max_pct = 90

if cash < insats_min_kr:
    st.error(
        f"Otillräcklig kontantinsats: du har {format_money(cash)} kr men "
        f"behöver minst {format_money(insats_min_kr)} kr (10 % av "
        f"köpeskilling; bolånetaket 2026-04-01 är 90 %)."
    )
    st.stop()

# Reset insats state when bounds change (V or cash).
bounds_key = f"{V:.0f}:{cash:.0f}"
if st.session_state.get("_bounds_key") != bounds_key:
    st.session_state._bounds_key = bounds_key
    default_insats = insats_max_kr
    st.session_state.insats_kr = default_insats
    st.session_state.insats_text = format_money(default_insats)
    st.session_state.ltv_pct = int(round((V - default_insats) / V * 100))
    st.session_state.ltv_text = str(st.session_state.ltv_pct)


def _on_insats_change():
    parsed = parse_money(st.session_state.insats_text)
    if parsed is None:
        st.session_state.insats_text = format_money(st.session_state.insats_kr)
        return
    parsed = max(insats_min_kr, min(insats_max_kr, parsed))
    st.session_state.insats_kr = parsed
    st.session_state.insats_text = format_money(parsed)
    ltv = int(round((V - parsed) / V * 100))
    st.session_state.ltv_pct = ltv
    st.session_state.ltv_text = str(ltv)


def _on_ltv_change():
    try:
        ltv = int(float(st.session_state.ltv_text.replace("%", "").strip()))
    except ValueError:
        st.session_state.ltv_text = str(st.session_state.ltv_pct)
        return
    ltv = max(ltv_min_pct, min(ltv_max_pct, ltv))
    insats = int(round(V * (100 - ltv) / 100))
    insats = max(insats_min_kr, min(insats_max_kr, insats))
    st.session_state.insats_kr = insats
    st.session_state.insats_text = format_money(insats)
    st.session_state.ltv_pct = int(round((V - insats) / V * 100))
    st.session_state.ltv_text = str(st.session_state.ltv_pct)


with st.container(border=True):
    st.markdown("### 💰 Lån")

    col_i, col_l = st.columns(2)
    col_i.text_input(
        f"Insats (kr) — {format_money(insats_min_kr)} – {format_money(insats_max_kr)}",
        key="insats_text",
        on_change=_on_insats_change,
    )
    col_l.text_input(
        f"Belåningsgrad (%) — {ltv_min_pct} – {ltv_max_pct}",
        key="ltv_text",
        on_change=_on_ltv_change,
    )

    col_b, col_s = st.columns(2)
    binding_label = col_b.selectbox(
        "Bindningstid",
        list(FIXATION_MONTHS.keys()),
        index=0,
    )
    binding_months = FIXATION_MONTHS[binding_label]
    scenario_label = col_s.selectbox(
        "Räntescenario",
        ["LOW (låg)", "BASE (basscenario)", "HIGH (hög)"],
        index=1,
    )
    scenario = RateScenario[scenario_label.split(" ")[0]]

    user_insats_kr = int(st.session_state.insats_kr)
    user_ltv_pct = int(st.session_state.ltv_pct)

    records = _load_stabelo_snapshot()
    stabelo_rate = None
    if records and user_ltv_pct > 0:
        stabelo_rate = lookup_rate(
            records,
            ltv_pct=user_ltv_pct,
            binding_months=binding_months,
            amount_kr=V * user_ltv_pct / 100,
        )
    scenario_rate = mortgage_rate(user_ltv_pct / 100, scenario, binding_months)

    col_r1, col_r2 = st.columns(2)
    col_r1.caption(
        f"Stabelo snapshot: **{stabelo_rate:.2f} %**"
        if stabelo_rate is not None
        else "Stabelo: saknas för denna LTV/bindningstid"
    )
    col_r2.caption(f"Scenario ({scenario.value}): **{scenario_rate * 100:.2f} %**")

    col_ch, col_btn = st.columns([3, 1])
    use_stabelo = col_ch.checkbox(
        "Använd Stabelo snapshot-ränta (gäller Ditt val, scenario C)",
        value=stabelo_rate is not None,
        disabled=stabelo_rate is None,
    )
    rate_override = (
        stabelo_rate / 100 if (use_stabelo and stabelo_rate is not None) else None
    )
    if col_btn.button("🔄 Uppdatera Stabelo"):
        try:
            new_records = fetch_rate_table()
            save_snapshot(new_records, SNAPSHOT_PATH)
            _load_stabelo_snapshot.clear()
            st.success(f"Uppdaterat ({len(new_records)} poster)")
            st.rerun()
        except Exception as e:
            st.error(f"Misslyckades: {e}")


# ----------------------------------------------------------------
# Build config
# ----------------------------------------------------------------

config = SimulationConfig(
    property_value=float(property_value),
    living_area_m2=float(living_area_m2),
    monthly_avgift_per_m2=float(avgift_per_m2),
    property_appreciation=appreciation,
    avgift_inflation=avgift_inflation,
    ltv_fraction=user_ltv_pct / 100,
    binding_months=binding_months,
    rate_scenario=scenario,
    rate_override=rate_override,
    initial_cash=float(initial_cash),
    allow_5y_revaluation=allow_5y,
    annual_gross_income=float(annual_income),
    monthly_living_cost=float(monthly_living),
    income_growth=income_growth,
    liquidity_buffer=float(liquidity_buffer),
    portfolio_return=portfolio_return,
    account_type=account_type,
    n_persons_for_fribelopp=int(n_persons),
    other_account_tax_rate=other_rate,
    sell_at_end=False,
    broker_fee_fraction=broker_fee,
    years=int(years),
)


# ----------------------------------------------------------------
# Run three scenarios (A, B, C)
# ----------------------------------------------------------------

scenarios = _run_three_scenarios(config.model_dump_json(), int(user_insats_kr))


# ----------------------------------------------------------------
# Terminal metrics table (3 × 4, held-to-end)
# ----------------------------------------------------------------

st.subheader("Slutvärden (innehav till horisontens slut)")

scenario_names = {
    "A": f"A. Maximal insats — {format_money(scenarios['A']['insats'])} kr · "
         f"LTV {scenarios['A']['ltv']*100:.0f} %",
    "B": f"B. Minimal insats (10 %) — {format_money(scenarios['B']['insats'])} kr · "
         f"LTV {scenarios['B']['ltv']*100:.0f} %",
    "C": f"C. Ditt val — {format_money(scenarios['C']['insats'])} kr · "
         f"LTV {scenarios['C']['ltv']*100:.0f} %",
}

metric_rows = []
for key in ("A", "B", "C"):
    last = scenarios[key]["df"].iloc[-1]
    portfolio = float(last["portfolio"])
    prop = float(last["property_value"])
    loan = float(last["loan"])
    nw = portfolio + prop - loan
    metric_rows.append({
        "Scenario": scenario_names[key],
        "Portfölj (ex. bostad)": format_money(portfolio) + " kr",
        "Bostadsvärde": format_money(prop) + " kr",
        "Kvarvarande lån": format_money(loan) + " kr",
        "Nettoförmögenhet": format_money(nw) + " kr",
    })
st.table(pd.DataFrame(metric_rows).set_index("Scenario"))

sell_bits = " · ".join(
    f"**{k}**: {format_money(scenarios[k]['net_worth_if_sold'])} kr"
    for k in ("A", "B", "C")
)
st.caption(
    f"Om du säljer bostaden vid horisontens slut "
    f"(22 % reavinstskatt + {broker_fee*100:.1f} % mäklararvode): {sell_bits}"
)

infeasible_any = any(scenarios[k]["infeasible_months"] > 0 for k in ("A", "B", "C"))
if infeasible_any:
    bits = " · ".join(
        f"{k}: {scenarios[k]['infeasible_months']}"
        for k in ("A", "B", "C") if scenarios[k]['infeasible_months'] > 0
    )
    st.warning(f"⚠️ Månader med cash flow < −likviditetsbuffert: {bits}")


# ----------------------------------------------------------------
# Main chart: 3 net_worth curves with real-year x-axis
# ----------------------------------------------------------------

st.subheader("Nettoförmögenhet över tid")

colors = {"A": "#2e7d32", "B": "#c62828", "C": "#1976d2"}
dashes = {"A": "dash", "B": "dot", "C": "solid"}
legend_names = {
    "A": f"A: Max insats (LTV {scenarios['A']['ltv']*100:.0f} %)",
    "B": "B: Min insats 10 % (LTV 90 %)",
    "C": f"C: Ditt val (LTV {scenarios['C']['ltv']*100:.0f} %)",
}

horizon_dates = _horizon_dates(years)

fig = go.Figure()
for key in ("A", "B", "C"):
    df_s = scenarios[key]["df"]
    fig.add_trace(go.Scatter(
        x=horizon_dates,
        y=df_s["net_worth"],
        name=legend_names[key],
        mode="lines",
        line=dict(color=colors[key], width=2.5, dash=dashes[key]),
        hovertemplate="%{x|%b %Y}: %{y:,.0f} kr<extra></extra>",
    ))

fig.update_layout(
    height=440,
    xaxis_title="Månad",
    yaxis_title="Nettoförmögenhet (kr)",
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.2),
    margin=dict(l=20, r=20, t=20, b=20),
)
fig.update_xaxes(dtick="M12", tickformat="%Y")
fig.update_yaxes(tickformat=",.0f")
st.plotly_chart(fig, width="stretch")


# ----------------------------------------------------------------
# LTV sweep comparison (retained)
# ----------------------------------------------------------------

st.subheader("Jämförelse över LTV-val (10-procentssteg)")
sweep = _run_sweep(config.model_dump_json())
sweep_display = sweep.copy()
sweep_display["ltv"] = (
    (sweep_display["ltv"] * 100).round(0).astype(int).astype(str) + " %"
)
sweep_display["terminal_net_worth"] = sweep_display["terminal_net_worth"].map(format_money)
sweep_display["final_loan"] = sweep_display["final_loan"].map(format_money)
sweep_display["final_portfolio"] = sweep_display["final_portfolio"].map(format_money)
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

fig_sweep = px.bar(
    sweep, x="ltv", y="terminal_net_worth",
    labels={"ltv": "LTV", "terminal_net_worth": "Terminal nettoförmögenhet (kr)"},
)
fig_sweep.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
fig_sweep.update_xaxes(tickformat=".0%")
fig_sweep.update_yaxes(tickformat=",.0f")
st.plotly_chart(fig_sweep, width="stretch")


# ----------------------------------------------------------------
# Expanders — monthly cash flow + rate sensitivity (scenario C)
# ----------------------------------------------------------------

with st.expander("📊 Månadsvis kassaflöde (Ditt val)", expanded=False):
    df_c = scenarios["C"]["df"]
    df_flow = df_c[["interest", "amortization", "avgift"]].copy()
    df_flow["datum"] = horizon_dates
    df_flow_long = df_flow.melt(
        id_vars="datum",
        value_vars=["interest", "amortization", "avgift"],
        var_name="Post",
        value_name="kr",
    )
    fig_flow = px.area(
        df_flow_long, x="datum", y="kr", color="Post",
        labels={"datum": "Månad"},
    )
    fig_flow.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
    fig_flow.update_xaxes(dtick="M12", tickformat="%Y")
    fig_flow.update_yaxes(tickformat=",.0f")
    st.plotly_chart(fig_flow, width="stretch")


with st.expander("🔬 Räntekänslighet (±1 pp shock, Ditt val)", expanded=False):
    rows = []
    base_rate = (
        rate_override if rate_override is not None
        else mortgage_rate(
            config.ltv_fraction, config.rate_scenario, config.binding_months,
        )
    )
    for shock in [-0.01, 0.0, 0.01]:
        test_cfg = config.model_copy(update={"rate_override": base_rate + shock})
        test_df = simulate(test_cfg)
        rows.append({
            "Skift (pp)": f"{shock * 100:+.0f}",
            "Effektiv ränta": f"{test_cfg.rate_override * 100:.2f} %",
            "Terminal NW": format_money(terminal_net_worth(test_df)) + " kr",
            "Inf. mån": int(test_df["infeasible"].sum()),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


st.caption(
    "Modellregler: 2026-04-01 FI-reform (LTV-tak 90 %, amortering 0/1/2 %-trappa, "
    "avskaffat 4,5×-tillägg). ISK 2026: 300 000 kr fribelopp, 1,065 % på överskott. "
    "Se `ref/swedish-mortgage-policy-2026.md` för källor."
)
