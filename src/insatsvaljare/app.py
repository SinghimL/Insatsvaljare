"""Streamlit entry point for the Insatsväljare LTV model.

The UI is tri-lingual (Svenska / British English / 繁體中文). All
user-facing strings come from `insatsvaljare.i18n`. Swedish domain
terms are also translated in non-Swedish locales per the 2026-04
policy change. ISK / KF / LTV abbreviations are kept as internationally
recognised labels with glosses on first use.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insatsvaljare.defaults import (
    CustomBucket,
    HouseholdMember,
    InvestmentStrategy,
    SimulationConfig,
    TaxModel,
)
from insatsvaljare.i18n import DEFAULT_LANG, LANG_LABELS, SUPPORTED_LANGS, t
from insatsvaljare.kommunalskatt import (
    fetch_kommunalskatt_table,
    kommun_records,
    load_or_fetch,
    save_snapshot,
)
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
    load_or_fetch as stabelo_load_or_fetch,
    lookup_rate,
    save_snapshot as stabelo_save_snapshot,
)
from insatsvaljare.tax_income import compute_net_income

STABELO_SNAPSHOT = Path(__file__).resolve().parents[2] / "ref" / "stabelo_snapshot.json"
KOMMUN_SNAPSHOT = Path(__file__).resolve().parents[2] / "ref" / "kommunalskatt_snapshot.json"


def _horizon_dates(years: int) -> pd.DatetimeIndex:
    today = pd.Timestamp.today()
    start = pd.Timestamp(year=today.year, month=today.month, day=1)
    return pd.date_range(start=start, periods=years * 12, freq="ME")


# ----------------------------------------------------------------
# Language selector — must happen before any t() call for correct locale
# ----------------------------------------------------------------

# Lang must be available before st.set_page_config (which uses page_title).
# Initialise from session_state with fallback, but do the widget after the
# page config (minor: the page_title briefly uses DEFAULT_LANG until the
# user re-renders with a different selection).
if "lang" not in st.session_state:
    st.session_state.lang = DEFAULT_LANG

st.set_page_config(
    page_title=t("page.title"),
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
    total_cash = base.total_initial_cash

    insats_min = 0.10 * V
    insats_max = min(total_cash, V)

    insats_a = insats_max
    ltv_a = max(0.0, (V - insats_a) / V)
    insats_b = insats_min
    ltv_b = 0.90
    insats_c = max(insats_min, min(insats_max, float(user_insats_kr)))
    ltv_c = max(0.0, (V - insats_c) / V)

    out = {}
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
        return stabelo_load_or_fetch(STABELO_SNAPSHOT, force_refresh=False)
    except Exception as e:
        st.warning(t("err.stabelo_load").format(err=e))
        return []


@st.cache_resource(show_spinner=False)
def _load_kommun_snapshot():
    try:
        records = load_or_fetch(KOMMUN_SNAPSHOT)
        return kommun_records(records)
    except Exception as e:
        st.warning(t("err.kommun_load").format(err=e))
        return []


# ----------------------------------------------------------------
# Sidebar — language picker + shared/household-wide inputs
# ----------------------------------------------------------------

lang_labels_ordered = [LANG_LABELS[code] for code in SUPPORTED_LANGS]
current_lang_label = LANG_LABELS[st.session_state.lang]
chosen_label = st.sidebar.selectbox(
    t("sidebar.lang_label"),
    lang_labels_ordered,
    index=lang_labels_ordered.index(current_lang_label),
    key="lang_selector_label",
)
# Sync session state (label → code)
new_code = next(code for code, lbl in LANG_LABELS.items() if lbl == chosen_label)
if new_code != st.session_state.lang:
    st.session_state.lang = new_code
    st.rerun()

st.sidebar.title(t("sidebar.title"))
st.sidebar.caption(t("sidebar.caption"))

with st.sidebar.expander(t("sb.bostad.header"), expanded=True):
    property_value = money_input(
        t("sb.bostad.kopeskilling"),
        key="property_value_text",
        default=6_000_000,
        min_val=1_000_000,
        max_val=30_000_000,
    )
    monthly_avgift = money_input(
        t("sb.bostad.avgift"),
        key="monthly_avgift_text",
        default=3_300,
        min_val=0,
        max_val=50_000,
    )
    appreciation = st.slider(t("sb.bostad.appreciation"), -2.0, 10.0, 4.0, 0.25) / 100
    avgift_inflation = st.slider(t("sb.bostad.avgift_inflation"), 0.0, 8.0, 2.5, 0.25) / 100

with st.sidebar.expander(t("sb.horizon.header"), expanded=True):
    years = st.slider(t("sb.horizon.years"), 1, 30, 10, 1)

with st.sidebar.expander(t("sb.kommun.header"), expanded=True):
    kommun_list = _load_kommun_snapshot()
    if kommun_list:
        kommun_names = [r["name"] for r in kommun_list]
        default_idx = kommun_names.index("Stockholm") if "Stockholm" in kommun_names else 0
        chosen_name = st.selectbox(
            t("sb.kommun.select"),
            kommun_names,
            index=default_idx,
        )
        chosen_rec = next(r for r in kommun_list if r["name"] == chosen_name)
        kommunal_tax_rate = float(chosen_rec["rate"]) / 100.0
        st.caption(t("sb.kommun.rate_caption").format(rate=chosen_rec["rate"]))
    else:
        kommunal_tax_rate = st.slider(t("sb.kommun.manual_rate"), 28.0, 36.0, 30.55, 0.01) / 100
    if st.button(t("sb.kommun.refresh"), help=t("sb.kommun.refresh_help")):
        try:
            records = fetch_kommunalskatt_table(year=2026)
            save_snapshot(records, KOMMUN_SNAPSHOT)
            _load_kommun_snapshot.clear()
            st.success(t("sb.kommun.refresh_success").format(n=len(records)))
            st.rerun()
        except Exception as e:
            st.error(t("sb.kommun.refresh_fail").format(err=e))

with st.sidebar.expander(t("sb.amort.header"), expanded=False):
    allow_5y = st.checkbox(
        t("sb.amort.5y"),
        value=False,
        help=t("sb.amort.5y_help"),
    )

with st.sidebar.expander(t("sb.exit.header"), expanded=False):
    broker_fee = st.slider(t("sb.exit.broker_fee"), 0.0, 8.0, 4.0, 0.25) / 100
    st.caption(t("sb.exit.caption"))

with st.sidebar.expander(t("sb.other.header"), expanded=False):
    income_growth = st.slider(t("sb.other.income_growth"), 0.0, 8.0, 3.0, 0.25) / 100
    personal_expense_inflation = st.slider(
        t("sb.other.expense_inflation"),
        0.0, 6.0, 2.0, 0.25,
        help=t("sb.other.expense_inflation_help"),
    ) / 100
    liquidity_buffer = money_input(
        t("sb.other.liquidity_buffer"),
        key="liquidity_buffer_text",
        default=50_000,
        min_val=0,
        max_val=1_000_000,
    )


# ----------------------------------------------------------------
# Household panel — member tabs
# ----------------------------------------------------------------

st.title(t("app.title"))

TAX_MODEL_KEYS = {
    TaxModel.ISK: "tax.isk",
    TaxModel.KF: "tax.kf",
    TaxModel.AF: "tax.af",
    TaxModel.NONE: "tax.none",
}
STRATEGY_KEYS = {
    InvestmentStrategy.SPARKONTO: "strategy.sparkonto",
    InvestmentStrategy.RANTEFOND_ISK: "strategy.rantefond_isk",
    InvestmentStrategy.ANPASSAD: "strategy.anpassad",
}

if "n_members" not in st.session_state:
    st.session_state.n_members = 1


def _member_defaults(i: int) -> dict:
    if i == 0:
        return {
            "name": f"{t('hh.member_default_name')} 1",
            "initial_cash": 5_400_000,
            "annual_brutto_income": 900_000,
            "monthly_personal_expenses": 25_000,
        }
    return {
        "name": f"{t('hh.member_default_name')} {i + 1}",
        "initial_cash": 0,
        "annual_brutto_income": 400_000,
        "monthly_personal_expenses": 15_000,
    }


def _ensure_member_state(i: int) -> None:
    d = _member_defaults(i)
    st.session_state.setdefault(f"m{i}_name", d["name"])
    st.session_state.setdefault(f"m{i}_cash_text", format_money(d["initial_cash"]))
    st.session_state.setdefault(f"m{i}_brutto_text", format_money(d["annual_brutto_income"]))
    st.session_state.setdefault(
        f"m{i}_expenses_text", format_money(d["monthly_personal_expenses"])
    )
    st.session_state.setdefault(f"m{i}_strategy", InvestmentStrategy.RANTEFOND_ISK.value)
    st.session_state.setdefault(f"m{i}_sparkonto_return", 2.5)
    st.session_state.setdefault(f"m{i}_rantefond_return", 6.5)
    st.session_state.setdefault(f"m{i}_n_buckets", 1)
    st.session_state.setdefault(f"m{i}_b0_alloc", 100)
    st.session_state.setdefault(f"m{i}_b0_return", 6.5)
    st.session_state.setdefault(f"m{i}_b0_tax", TaxModel.ISK.value)


for i in range(st.session_state.n_members):
    _ensure_member_state(i)


with st.container(border=True):
    hdr_col1, hdr_col2, hdr_col3 = st.columns([3, 1, 1])
    hdr_col1.markdown(f"### {t('hh.header')}")
    if hdr_col2.button(t("hh.add_member"), use_container_width=True):
        i = st.session_state.n_members
        _ensure_member_state(i)
        st.session_state.n_members += 1
        st.rerun()
    if hdr_col3.button(
        t("hh.remove_last"),
        use_container_width=True,
        disabled=st.session_state.n_members <= 1,
    ):
        st.session_state.n_members -= 1
        st.rerun()

    tab_labels = [st.session_state[f"m{i}_name"] for i in range(st.session_state.n_members)]
    tabs = st.tabs(tab_labels)
    for i, tab in enumerate(tabs):
        with tab:
            c1, c2 = st.columns(2)
            c1.text_input(t("hh.tab.name"), key=f"m{i}_name")
            c2.selectbox(
                t("hh.tab.strategy"),
                [s.value for s in InvestmentStrategy],
                format_func=lambda v: t(STRATEGY_KEYS[InvestmentStrategy(v)]),
                key=f"m{i}_strategy",
            )

            c3, c4, c5 = st.columns(3)
            with c3:
                money_input(
                    t("hh.tab.cash"),
                    key=f"m{i}_cash_text",
                    default=5_400_000 if i == 0 else 0,
                    min_val=0,
                    max_val=50_000_000,
                )
            with c4:
                money_input(
                    t("hh.tab.brutto"),
                    key=f"m{i}_brutto_text",
                    default=900_000 if i == 0 else 400_000,
                    min_val=0,
                    max_val=20_000_000,
                )
            with c5:
                money_input(
                    t("hh.tab.expenses"),
                    key=f"m{i}_expenses_text",
                    default=25_000 if i == 0 else 15_000,
                    min_val=0,
                    max_val=500_000,
                    help=t("hh.tab.expenses_help"),
                )

            strategy_val = st.session_state[f"m{i}_strategy"]
            if strategy_val == InvestmentStrategy.SPARKONTO.value:
                st.slider(
                    t("strategy.sparkonto.rate_label"),
                    min_value=0.0, max_value=10.0, step=0.1,
                    key=f"m{i}_sparkonto_return",
                )
            elif strategy_val == InvestmentStrategy.RANTEFOND_ISK.value:
                st.slider(
                    t("strategy.isk.rate_label"),
                    min_value=0.0, max_value=15.0, step=0.25,
                    key=f"m{i}_rantefond_return",
                )
            else:  # ANPASSAD
                st.markdown(t("anpassad.heading"))
                bc1, bc2 = st.columns([1, 1])
                if bc1.button(t("anpassad.add"), key=f"m{i}_add_bucket"):
                    j = st.session_state[f"m{i}_n_buckets"]
                    st.session_state[f"m{i}_b{j}_alloc"] = 0
                    st.session_state[f"m{i}_b{j}_return"] = 5.0
                    st.session_state[f"m{i}_b{j}_tax"] = TaxModel.ISK.value
                    st.session_state[f"m{i}_n_buckets"] += 1
                    st.rerun()
                if bc2.button(
                    t("anpassad.remove"),
                    key=f"m{i}_remove_bucket",
                    disabled=st.session_state[f"m{i}_n_buckets"] <= 1,
                ):
                    st.session_state[f"m{i}_n_buckets"] -= 1
                    st.rerun()

                running_alloc = 0.0
                for j in range(st.session_state[f"m{i}_n_buckets"]):
                    bucket_cols = st.columns([1, 1, 2])
                    bucket_cols[0].number_input(
                        t("anpassad.alloc").format(j=j + 1),
                        min_value=0, max_value=100,
                        key=f"m{i}_b{j}_alloc",
                    )
                    bucket_cols[1].number_input(
                        t("anpassad.return"),
                        min_value=-50.0, max_value=50.0, step=0.25,
                        key=f"m{i}_b{j}_return",
                    )
                    bucket_cols[2].selectbox(
                        t("anpassad.tax_model"),
                        [tm.value for tm in (TaxModel.ISK, TaxModel.KF, TaxModel.AF, TaxModel.NONE)],
                        format_func=lambda v: t(TAX_MODEL_KEYS[TaxModel(v)]),
                        key=f"m{i}_b{j}_tax",
                    )
                    running_alloc += st.session_state[f"m{i}_b{j}_alloc"]
                if abs(running_alloc - 100) > 1e-4:
                    st.warning(t("anpassad.sum_warning").format(total=running_alloc))

            # Netto preview caption
            try:
                brutto_val = parse_money(st.session_state[f"m{i}_brutto_text"]) or 0
                netto_preview = compute_net_income(
                    brutto=brutto_val,
                    kommunal_rate=kommunal_tax_rate,
                    annual_interest=0,
                )
                st.caption(t("hh.tab.netto_preview").format(
                    brutto=format_money(netto_preview.brutto),
                    netto=format_money(netto_preview.netto),
                    netto_m=format_money(netto_preview.netto / 12),
                ))
            except Exception:
                pass


# ----------------------------------------------------------------
# Build members list from session_state
# ----------------------------------------------------------------

def _build_member_from_state(i: int) -> HouseholdMember:
    strategy_val = st.session_state[f"m{i}_strategy"]
    cash = parse_money(st.session_state[f"m{i}_cash_text"]) or 0
    brutto = parse_money(st.session_state[f"m{i}_brutto_text"]) or 0
    expenses = parse_money(st.session_state[f"m{i}_expenses_text"]) or 0
    custom_buckets: list[CustomBucket] = []
    if strategy_val == InvestmentStrategy.ANPASSAD.value:
        for j in range(st.session_state[f"m{i}_n_buckets"]):
            custom_buckets.append(CustomBucket(
                name=f"Bucket {j + 1}",
                allocation_fraction=st.session_state[f"m{i}_b{j}_alloc"] / 100.0,
                annual_return=st.session_state[f"m{i}_b{j}_return"] / 100.0,
                tax_model=TaxModel(st.session_state[f"m{i}_b{j}_tax"]),
            ))
    return HouseholdMember(
        name=st.session_state[f"m{i}_name"],
        initial_cash=float(cash),
        annual_brutto_income=float(brutto),
        monthly_personal_expenses=float(expenses),
        strategy=InvestmentStrategy(strategy_val),
        sparkonto_return=st.session_state[f"m{i}_sparkonto_return"] / 100.0,
        rantefond_isk_return=st.session_state[f"m{i}_rantefond_return"] / 100.0,
        custom_buckets=custom_buckets,
    )


try:
    members = [_build_member_from_state(i) for i in range(st.session_state.n_members)]
except ValueError as e:
    st.error(t("err.config_invalid").format(err=e))
    st.stop()


# ----------------------------------------------------------------
# Lån panel — insats / LTV bidirectional
# ----------------------------------------------------------------

V = float(property_value)
total_cash = float(sum(m.initial_cash for m in members))

insats_min_kr = int(round(0.10 * V))
insats_max_kr = int(round(min(total_cash, V)))
ltv_min_pct = max(0, int(round((V - insats_max_kr) / V * 100)))
ltv_max_pct = 90

if total_cash < insats_min_kr:
    st.error(t("loan.insufficient_cash").format(
        have=format_money(total_cash),
        need=format_money(insats_min_kr),
    ))
    st.stop()

bounds_key = f"{V:.0f}:{total_cash:.0f}"
if st.session_state.get("_bounds_key") != bounds_key:
    st.session_state._bounds_key = bounds_key
    default_insats = insats_max_kr
    st.session_state.insats_kr = default_insats
    st.session_state.insats_text = format_money(default_insats)
    st.session_state.insats_slider = default_insats
    st.session_state.ltv_pct = int(round((V - default_insats) / V * 100))
    st.session_state.ltv_text = str(st.session_state.ltv_pct)


def _sync_from_insats(insats: int) -> None:
    insats = max(insats_min_kr, min(insats_max_kr, insats))
    st.session_state.insats_kr = insats
    st.session_state.insats_text = format_money(insats)
    st.session_state.insats_slider = insats
    ltv = int(round((V - insats) / V * 100))
    st.session_state.ltv_pct = ltv
    st.session_state.ltv_text = str(ltv)


def _on_insats_change():
    parsed = parse_money(st.session_state.insats_text)
    if parsed is None:
        st.session_state.insats_text = format_money(st.session_state.insats_kr)
        return
    _sync_from_insats(parsed)


def _on_ltv_change():
    try:
        ltv = int(float(st.session_state.ltv_text.replace("%", "").strip()))
    except ValueError:
        st.session_state.ltv_text = str(st.session_state.ltv_pct)
        return
    ltv = max(ltv_min_pct, min(ltv_max_pct, ltv))
    _sync_from_insats(int(round(V * (100 - ltv) / 100)))


def _on_slider_change():
    _sync_from_insats(int(st.session_state.insats_slider))


with st.container(border=True):
    st.markdown(f"### {t('loan.header')}")

    col_i, col_l = st.columns(2)
    col_i.text_input(
        t("loan.insats_label").format(lo=format_money(insats_min_kr), hi=format_money(insats_max_kr)),
        key="insats_text",
        on_change=_on_insats_change,
    )
    col_l.text_input(
        t("loan.ltv_label").format(lo=ltv_min_pct, hi=ltv_max_pct),
        key="ltv_text",
        on_change=_on_ltv_change,
    )

    if insats_max_kr > insats_min_kr:
        slider_step = max(10_000, (insats_max_kr - insats_min_kr) // 200)
        st.slider(
            t("loan.slider_label"),
            min_value=insats_min_kr,
            max_value=insats_max_kr,
            step=slider_step,
            key="insats_slider",
            on_change=_on_slider_change,
            format="%d kr",
            label_visibility="collapsed",
        )
    else:
        st.caption(t("loan.slider_locked").format(amt=format_money(insats_min_kr)))

    col_b, col_s = st.columns(2)
    binding_label = col_b.selectbox(
        t("loan.binding"), list(FIXATION_MONTHS.keys()), index=0,
    )
    binding_months = FIXATION_MONTHS[binding_label]

    scenario_options = [
        (RateScenario.LOW, t("loan.scenario.low")),
        (RateScenario.BASE, t("loan.scenario.base")),
        (RateScenario.HIGH, t("loan.scenario.high")),
    ]
    scenario_label = col_s.selectbox(
        t("loan.scenario"),
        [lbl for _, lbl in scenario_options],
        index=1,
    )
    scenario = next(sc for sc, lbl in scenario_options if lbl == scenario_label)

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
        t("loan.stabelo_hit").format(rate=stabelo_rate)
        if stabelo_rate is not None
        else t("loan.stabelo_miss")
    )
    col_r2.caption(t("loan.scenario_rate").format(sc=scenario.value, rate=scenario_rate * 100))

    col_ch, col_btn = st.columns([3, 1])
    use_stabelo = col_ch.checkbox(
        t("loan.use_stabelo"),
        value=stabelo_rate is not None,
        disabled=stabelo_rate is None,
    )
    rate_override = (
        stabelo_rate / 100 if (use_stabelo and stabelo_rate is not None) else None
    )
    if col_btn.button(t("loan.refresh_stabelo")):
        try:
            new_records = fetch_rate_table()
            stabelo_save_snapshot(new_records, STABELO_SNAPSHOT)
            _load_stabelo_snapshot.clear()
            st.success(t("sb.kommun.refresh_success").format(n=len(new_records)))
            st.rerun()
        except Exception as e:
            st.error(t("sb.kommun.refresh_fail").format(err=e))


# ----------------------------------------------------------------
# Build config and run
# ----------------------------------------------------------------

config = SimulationConfig(
    property_value=float(property_value),
    monthly_avgift=float(monthly_avgift),
    property_appreciation=appreciation,
    avgift_inflation=avgift_inflation,
    ltv_fraction=user_ltv_pct / 100,
    binding_months=binding_months,
    rate_scenario=scenario,
    rate_override=rate_override,
    members=members,
    kommunal_tax_rate=kommunal_tax_rate,
    income_growth=income_growth,
    personal_expense_inflation=personal_expense_inflation,
    liquidity_buffer=float(liquidity_buffer),
    allow_5y_revaluation=allow_5y,
    sell_at_end=False,
    broker_fee_fraction=broker_fee,
    years=int(years),
)

scenarios = _run_three_scenarios(config.model_dump_json(), int(user_insats_kr))


# ----------------------------------------------------------------
# Metrics table
# ----------------------------------------------------------------

st.subheader(t("metrics.header"))

scenario_names = {
    "A": t("metrics.scenario_a").format(
        insats=format_money(scenarios["A"]["insats"]),
        ltv=scenarios["A"]["ltv"] * 100,
    ),
    "B": t("metrics.scenario_b").format(
        insats=format_money(scenarios["B"]["insats"]),
        ltv=scenarios["B"]["ltv"] * 100,
    ),
    "C": t("metrics.scenario_c").format(
        insats=format_money(scenarios["C"]["insats"]),
        ltv=scenarios["C"]["ltv"] * 100,
    ),
}

metric_rows = []
for key in ("A", "B", "C"):
    df_s = scenarios[key]["df"]
    last = df_s.iloc[-1]
    portfolio = float(last["portfolio"])
    prop = float(last["property_value"])
    loan = float(last["loan"])
    nw = portfolio + prop - loan
    # Terminal-year brutto salary (last year's average month × 12)
    terminal_brutto = float(df_s[df_s["year"] == df_s["year"].max()]["brutto_monthly"].mean()) * 12
    avg_savings = float(df_s["savings"].mean())
    cum_tax = float((df_s["tax_gross_monthly"] - df_s["ranteavdrag_monthly"]).sum())
    cum_ranteavdrag = float(df_s["ranteavdrag_monthly"].sum())
    metric_rows.append({
        t("metrics.col.scenario"): scenario_names[key],
        t("metrics.col.portfolio"): format_money(portfolio) + " kr",
        t("metrics.col.property"): format_money(prop) + " kr",
        t("metrics.col.loan"): format_money(loan) + " kr",
        t("metrics.col.net_worth"): format_money(nw) + " kr",
        t("metrics.col.terminal_brutto"): format_money(terminal_brutto) + " kr",
        t("metrics.col.avg_savings"): format_money(avg_savings) + " kr",
        t("metrics.col.cum_tax"): format_money(cum_tax) + " kr",
        t("metrics.col.cum_ranteavdrag"): format_money(cum_ranteavdrag) + " kr",
    })
# Transpose so scenarios are columns (3) and categories are rows (8) — easier
# to compare one category across scenarios.
metrics_df = pd.DataFrame(metric_rows).set_index(t("metrics.col.scenario")).T
st.table(metrics_df)

sell_bits = " · ".join(
    f"**{k}**: {format_money(scenarios[k]['net_worth_if_sold'])} kr"
    for k in ("A", "B", "C")
)
st.caption(t("metrics.sell_annotation").format(broker=broker_fee * 100, bits=sell_bits))

infeasible_any = any(scenarios[k]["infeasible_months"] > 0 for k in ("A", "B", "C"))
if infeasible_any:
    bits = " · ".join(
        f"{k}: {scenarios[k]['infeasible_months']}"
        for k in ("A", "B", "C") if scenarios[k]['infeasible_months'] > 0
    )
    st.warning(t("metrics.infeasible").format(bits=bits))


# ----------------------------------------------------------------
# Main chart
# ----------------------------------------------------------------

st.subheader(t("chart.title"))

colors = {"A": "#2e7d32", "B": "#c62828", "C": "#1976d2"}
dashes = {"A": "dash", "B": "dot", "C": "solid"}
legend_names = {
    "A": t("chart.legend.a").format(ltv=scenarios["A"]["ltv"] * 100),
    "B": t("chart.legend.b"),
    "C": t("chart.legend.c").format(ltv=scenarios["C"]["ltv"] * 100),
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
    xaxis_title=t("chart.xaxis"),
    yaxis_title=t("chart.yaxis"),
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.2),
    margin=dict(l=20, r=20, t=20, b=20),
)
fig.update_xaxes(dtick="M12", tickformat="%Y")
fig.update_yaxes(tickformat=",.0f")
st.plotly_chart(fig, width="stretch")


# ----------------------------------------------------------------
# LTV sweep
# ----------------------------------------------------------------

st.subheader(t("sweep.header"))
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
        "ltv": t("sweep.col.ltv"),
        "terminal_net_worth": t("sweep.col.terminal_nw"),
        "infeasible_months": t("sweep.col.infeasible"),
        "final_loan": t("sweep.col.final_loan"),
        "final_portfolio": t("sweep.col.final_portfolio"),
        "incremental_irr_vs_90": t("sweep.col.irr"),
    }),
    hide_index=True,
    width="stretch",
)

fig_sweep = px.bar(
    sweep, x="ltv", y="terminal_net_worth",
    labels={"ltv": t("sweep.chart.x"), "terminal_net_worth": t("sweep.chart.y")},
)
fig_sweep.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
fig_sweep.update_xaxes(tickformat=".0%")
fig_sweep.update_yaxes(tickformat=",.0f")
st.plotly_chart(fig_sweep, width="stretch")


# ----------------------------------------------------------------
# Expanders
# ----------------------------------------------------------------

with st.expander(t("flow.header"), expanded=False):
    df_c = scenarios["C"]["df"]

    # Year selector — use year numbers from df
    year_options = sorted(df_c["year"].unique().tolist())
    selected_year = st.selectbox(
        t("flow.year_select"),
        year_options,
        index=0,
        key="flow_year_select",
    )
    year_slice = df_c[df_c["year"] == selected_year]
    avg = year_slice.mean(numeric_only=True)

    brutto = float(avg["brutto_monthly"])
    tax_gross = float(avg["tax_gross_monthly"])
    interest_m = float(avg["interest"])
    amort_m = float(avg["amortization"])
    avgift_m = float(avg["avgift"])
    personal_m = float(avg["personal_expenses_monthly"])
    rant_m = float(avg["ranteavdrag_monthly"])
    savings_m = float(avg["savings"])
    to_portfolio_m = savings_m + rant_m

    def _row(label_key: str, amount: float, sign: str = "−") -> dict:
        return {
            t("flow.category"): f"{sign} {t(label_key)}" if sign else t(label_key),
            t("flow.amount"): format_money(amount) + " kr",
            t("flow.share"): f"{(amount / brutto * 100):.1f} %" if brutto > 0 else "—",
        }

    flow_rows = [
        {
            t("flow.category"): t("flow.cat.brutto"),
            t("flow.amount"): format_money(brutto) + " kr",
            t("flow.share"): "100.0 %" if brutto > 0 else "—",
        },
        _row("flow.cat.tax_gross", tax_gross),
        _row("flow.cat.interest", interest_m),
        _row("flow.cat.amortization", amort_m),
        _row("flow.cat.avgift", avgift_m),
        _row("flow.cat.personal", personal_m),
        _row("flow.cat.savings", savings_m, sign="="),
        _row("flow.cat.ranteavdrag", rant_m, sign="+"),
        _row("flow.cat.to_portfolio", to_portfolio_m, sign="="),
    ]
    st.table(pd.DataFrame(flow_rows).set_index(t("flow.category")))

    st.caption(t("flow.inflation_note").format(
        rate=personal_expense_inflation * 100,
        avg_rate=avgift_inflation * 100,
        inc_rate=income_growth * 100,
    ))

    # Stacked area chart by year (average month per year)
    st.markdown(f"**{t('flow.chart.header')}**")
    yearly = (
        df_c.groupby("year")
        .agg(
            brutto=("brutto_monthly", "mean"),
            tax=("tax_gross_monthly", "mean"),
            rant=("ranteavdrag_monthly", "mean"),
            interest=("interest", "mean"),
            amort=("amortization", "mean"),
            avgift=("avgift", "mean"),
            personal=("personal_expenses_monthly", "mean"),
            savings=("savings", "mean"),
        )
        .reset_index()
    )
    # Effective tax = gross - ranteavdrag refund; "to_portfolio" = savings + ranteavdrag
    yearly["eff_tax"] = yearly["tax"] - yearly["rant"]
    yearly["to_portfolio"] = yearly["savings"] + yearly["rant"]

    stack_df = pd.DataFrame({
        t("flow.chart.xaxis_year"): yearly["year"],
        t("flow.cat.tax_gross"): yearly["eff_tax"],
        t("flow.cat.interest"): yearly["interest"],
        t("flow.cat.amortization"): yearly["amort"],
        t("flow.cat.avgift"): yearly["avgift"],
        t("flow.cat.personal"): yearly["personal"],
        t("flow.cat.to_portfolio"): yearly["to_portfolio"],
    })
    stack_long = stack_df.melt(
        id_vars=t("flow.chart.xaxis_year"),
        var_name=t("flow.category"),
        value_name=t("flow.chart.y"),
    )
    fig_flow = px.area(
        stack_long,
        x=t("flow.chart.xaxis_year"),
        y=t("flow.chart.y"),
        color=t("flow.category"),
    )
    fig_flow.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", y=-0.2),
    )
    fig_flow.update_yaxes(tickformat=",.0f")
    st.plotly_chart(fig_flow, width="stretch")


with st.expander(t("exp.rate_sens"), expanded=False):
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
            t("exp.rate.shift"): f"{shock * 100:+.0f}",
            t("exp.rate.effective"): f"{test_cfg.rate_override * 100:.2f} %",
            t("exp.rate.terminal_nw"): format_money(terminal_net_worth(test_df)) + " kr",
            t("exp.rate.inf_months"): int(test_df["infeasible"].sum()),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


st.caption(t("footer.disclaimer"))
