"""Tri-lingual translation table for the Streamlit UI.

Supported languages:
    sv     — Svenska (default, native Swedish)
    en     — British English
    zh-TW  — 繁體中文（臺灣）

Swedish domain terms (insats, belåningsgrad, avgift, ISK, etc.) are
translated in en/zh-TW contexts rather than preserved verbatim, per
the 2026-04 policy change. ISK / KF / LTV abbreviations are kept as
internationally recognised labels, with glosses on first use.

Usage:
    from insatsvaljare.i18n import t, set_lang_from_session
    set_lang_from_session()
    st.title(t("app.title"))
    st.error(t("err.insufficient_cash").format(have=X, need=Y))
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

Lang = Literal["sv", "en", "zh-TW"]
DEFAULT_LANG: Lang = "sv"
SUPPORTED_LANGS: list[Lang] = ["sv", "en", "zh-TW"]

LANG_LABELS: dict[Lang, str] = {
    "sv": "Svenska 🇸🇪",
    "en": "English 🇬🇧",
    "zh-TW": "繁體中文 🇹🇼",
}


# ---------------------------------------------------------------------------
# Translation table — flat keyed dict, grouped by UI section in code order
# ---------------------------------------------------------------------------

TRANSLATIONS: dict[str, dict[str, str]] = {
    # ---- Page chrome ----
    "page.title": {
        "sv": "Insatsväljare för bostadsrätt",
        "en": "Down-Payment Optimiser for Swedish Condos",
        "zh-TW": "瑞典合作公寓頭期款模擬器",
    },
    "app.title": {
        "sv": "🏠 Insatsväljare",
        "en": "🏠 Down-Payment Optimiser",
        "zh-TW": "🏠 頭期款選擇器",
    },
    "sidebar.title": {
        "sv": "🏠 Insatsväljare för bostadsrätt",
        "en": "🏠 Down-Payment Optimiser",
        "zh-TW": "🏠 頭期款模擬器",
    },
    "sidebar.caption": {
        "sv": "Simulering av bostadsrättsköp under 2026 års bolåneregler",
        "en": "Simulation of Swedish condo (bostadsrätt) purchase under 2026 mortgage rules",
        "zh-TW": "依 2026 年瑞典房貸新規模擬合作公寓購屋",
    },
    "sidebar.lang_label": {
        "sv": "🌐 Språk",
        "en": "🌐 Language",
        "zh-TW": "🌐 語言",
    },

    # ---- Sidebar: Bostad (property) ----
    "sb.bostad.header": {
        "sv": "📍 Bostad",
        "en": "📍 Property",
        "zh-TW": "📍 房產",
    },
    "sb.bostad.kopeskilling": {
        "sv": "Köpeskilling (kr)",
        "en": "Purchase price (kr)",
        "zh-TW": "成交價（kr）",
    },
    "sb.bostad.avgift": {
        "sv": "Månadsavgift (kr/mån)",
        "en": "Monthly service charge (kr/month)",
        "zh-TW": "每月管理費（kr/月）",
    },
    "sb.bostad.appreciation": {
        "sv": "Värdeökning (%/år)",
        "en": "Property appreciation (%/year)",
        "zh-TW": "房價年增值（%/年）",
    },
    "sb.bostad.avgift_inflation": {
        "sv": "Avgiftsinflation (%/år)",
        "en": "Service charge inflation (%/year)",
        "zh-TW": "管理費年漲幅（%/年）",
    },

    # ---- Sidebar: Tidshorisont (horizon) ----
    "sb.horizon.header": {
        "sv": "⏱ Tidshorisont",
        "en": "⏱ Time horizon",
        "zh-TW": "⏱ 期間",
    },
    "sb.horizon.years": {
        "sv": "Innehavstid (år)",
        "en": "Holding period (years)",
        "zh-TW": "持有年數",
    },

    # ---- Sidebar: Kommun (municipality) ----
    "sb.kommun.header": {
        "sv": "📍 Kommun (för skatteberäkning)",
        "en": "📍 Municipality (for tax calculation)",
        "zh-TW": "📍 市政區（用於稅額計算）",
    },
    "sb.kommun.select": {
        "sv": "Välj kommun (stöder sökning)",
        "en": "Select municipality (searchable)",
        "zh-TW": "選擇市政區（支援搜尋）",
    },
    "sb.kommun.rate_caption": {
        "sv": "Total kommunalskatt (kommun + region): **{rate:.2f} %**",
        "en": "Total municipal tax (municipality + region): **{rate:.2f} %**",
        "zh-TW": "市政 + 區域稅合計：**{rate:.2f} %**",
    },
    "sb.kommun.refresh": {
        "sv": "🔄 Uppdatera kommunalskatt",
        "en": "🔄 Refresh municipal tax data",
        "zh-TW": "🔄 更新市政稅率",
    },
    "sb.kommun.refresh_help": {
        "sv": "Hämta senaste siffror från SCB",
        "en": "Fetch the latest figures from Statistics Sweden (SCB)",
        "zh-TW": "從瑞典統計局（SCB）擷取最新數據",
    },
    "sb.kommun.refresh_success": {
        "sv": "Uppdaterat ({n} poster)",
        "en": "Updated ({n} records)",
        "zh-TW": "已更新（{n} 筆資料）",
    },
    "sb.kommun.refresh_fail": {
        "sv": "Misslyckades: {err}",
        "en": "Failed: {err}",
        "zh-TW": "失敗：{err}",
    },
    "sb.kommun.manual_rate": {
        "sv": "Kommunalskatt (%)",
        "en": "Municipal tax rate (%)",
        "zh-TW": "市政稅率（%）",
    },

    # ---- Sidebar: Amortering ----
    "sb.amort.header": {
        "sv": "🏠 Amortering",
        "en": "🏠 Amortisation",
        "zh-TW": "🏠 本金攤還",
    },
    "sb.amort.5y": {
        "sv": "Tillåt omvärdering vart 5:e år",
        "en": "Allow property revaluation every 5 years",
        "zh-TW": "允許每 5 年重新估價房產",
    },
    "sb.amort.5y_help": {
        "sv": "Av: amorteringsgrund fryst. På: 5-års omvärdering till marknad.",
        "en": "Off: amortisation base is frozen. On: revalued to market every 5 years.",
        "zh-TW": "關閉：攤還基數固定。啟用：每 5 年以市價重新估算。",
    },

    # ---- Sidebar: Exit ----
    "sb.exit.header": {
        "sv": "🏁 Exit (annotering)",
        "en": "🏁 Exit (annotation)",
        "zh-TW": "🏁 出場（標註用）",
    },
    "sb.exit.broker_fee": {
        "sv": "Mäklararvode (%)",
        "en": "Estate agent fee (%)",
        "zh-TW": "仲介費（%）",
    },
    "sb.exit.caption": {
        "sv": (
            "Huvudvyn antar innehav till horisontens slut. "
            "Annoteringen under tabellen visar netto om du säljer."
        ),
        "en": (
            "The main view assumes the property is held to the end of the horizon. "
            "The annotation below the table shows net proceeds if sold."
        ),
        "zh-TW": (
            "主畫面假設持有至期末。"
            "下方註解顯示若現在賣房可實拿的淨額。"
        ),
    },

    # ---- Sidebar: Övriga inställningar ----
    "sb.other.header": {
        "sv": "⚙️ Övriga inställningar",
        "en": "⚙️ Other settings",
        "zh-TW": "⚙️ 其他設定",
    },
    "sb.other.income_growth": {
        "sv": "Inkomstökning (%/år)",
        "en": "Income growth (%/year)",
        "zh-TW": "薪資年成長（%/年）",
    },
    "sb.other.liquidity_buffer": {
        "sv": "Likviditetsbuffert (kr)",
        "en": "Liquidity buffer (kr)",
        "zh-TW": "流動性緩衝（kr）",
    },
    "sb.other.expense_inflation": {
        "sv": "Inflation på personliga utgifter (%/år)",
        "en": "Personal-expense inflation (%/year)",
        "zh-TW": "個人開銷年通脹（%/年）",
    },
    "sb.other.expense_inflation_help": {
        "sv": (
            "CPI-style ökning av personliga utgifter. Utan denna växer reallönen "
            "orealistiskt snabbt över horisonten."
        ),
        "en": (
            "CPI-style growth applied to personal expenses. Without it, real wages "
            "grow unrealistically fast over the horizon."
        ),
        "zh-TW": (
            "依 CPI 方式調升個人開銷。若未設定，實質薪資會不切實際地快速增長。"
        ),
    },

    # ---- Household panel ----
    "hh.header": {
        "sv": "👪 Hushåll",
        "en": "👪 Household",
        "zh-TW": "👪 家庭成員",
    },
    "hh.add_member": {
        "sv": "➕ Ny medlem",
        "en": "➕ Add member",
        "zh-TW": "➕ 新增成員",
    },
    "hh.remove_last": {
        "sv": "➖ Ta bort sist",
        "en": "➖ Remove last",
        "zh-TW": "➖ 移除最後一位",
    },
    "hh.member_default_name": {
        "sv": "Medlem",
        "en": "Member",
        "zh-TW": "成員",
    },
    "hh.tab.name": {
        "sv": "Namn",
        "en": "Name",
        "zh-TW": "姓名",
    },
    "hh.tab.strategy": {
        "sv": "Investeringsstrategi",
        "en": "Investment strategy",
        "zh-TW": "投資策略",
    },
    "hh.tab.cash": {
        "sv": "Startkapital (kr)",
        "en": "Starting capital (kr)",
        "zh-TW": "起始資金（kr）",
    },
    "hh.tab.brutto": {
        "sv": "Brutto lön (kr/år)",
        "en": "Gross salary (kr/year)",
        "zh-TW": "稅前年收入（kr/年）",
    },
    "hh.tab.expenses": {
        "sv": "Personliga utgifter (kr/mån)",
        "en": "Personal expenses (kr/month)",
        "zh-TW": "個人每月開銷（kr/月）",
    },
    "hh.tab.expenses_help": {
        "sv": (
            "Endast personlig konsumtion (mat, kläder, transport). "
            "Avgift + lån fördelas automatiskt proportionellt mot brutto."
        ),
        "en": (
            "Personal consumption only (food, clothes, transport). "
            "Service charge + loan costs are split proportionally to gross income."
        ),
        "zh-TW": (
            "僅包含個人消費（飲食、衣物、交通）。"
            "管理費與貸款支出依稅前收入比例自動分攤。"
        ),
    },
    "hh.tab.netto_preview": {
        "sv": (
            "Preview: brutto {brutto} kr/år → netto (före ränteavdrag) "
            "{netto} kr/år ≈ {netto_m} kr/mån"
        ),
        "en": (
            "Preview: gross {brutto} kr/year → net (before interest deduction) "
            "{netto} kr/year ≈ {netto_m} kr/month"
        ),
        "zh-TW": (
            "預覽：稅前 {brutto} kr/年 → 稅後（未扣房貸利息抵扣）"
            "{netto} kr/年 ≈ {netto_m} kr/月"
        ),
    },

    # ---- Strategy labels ----
    "strategy.sparkonto": {
        "sv": "💰 Sparkonto (bankränta)",
        "en": "💰 Savings account (bank interest)",
        "zh-TW": "💰 銀行活儲（定存利息）",
    },
    "strategy.rantefond_isk": {
        "sv": "📈 Räntefond ISK",
        "en": "📈 Bond fund via ISK (tax-advantaged account)",
        "zh-TW": "📈 債券基金 ISK（投資儲蓄帳戶）",
    },
    "strategy.anpassad": {
        "sv": "🛠 Anpassad (flera bucket)",
        "en": "🛠 Custom (multiple buckets)",
        "zh-TW": "🛠 自訂（多配置組合）",
    },

    "strategy.sparkonto.rate_label": {
        "sv": "Årsränta (%) — banksparkonto",
        "en": "Annual interest rate (%) — bank savings",
        "zh-TW": "銀行年利率（%）",
    },
    "strategy.isk.rate_label": {
        "sv": "Förväntad avkastning (%/år) — ISK-fond",
        "en": "Expected return (%/year) — ISK fund",
        "zh-TW": "預期年報酬（%/年）— ISK 基金",
    },

    # ---- Custom bucket ----
    "anpassad.heading": {
        "sv": "**Bucketer** (summan måste vara 100 %)",
        "en": "**Buckets** (must sum to 100 %)",
        "zh-TW": "**配置項**（總和須為 100 %）",
    },
    "anpassad.add": {
        "sv": "➕ Ny bucket",
        "en": "➕ Add bucket",
        "zh-TW": "➕ 新增配置",
    },
    "anpassad.remove": {
        "sv": "➖ Ta bort sist",
        "en": "➖ Remove last",
        "zh-TW": "➖ 移除最後",
    },
    "anpassad.alloc": {
        "sv": "Bucket {j} andel (%)",
        "en": "Bucket {j} allocation (%)",
        "zh-TW": "配置 {j} 占比（%）",
    },
    "anpassad.return": {
        "sv": "Avkastning (%/år)",
        "en": "Return (%/year)",
        "zh-TW": "年報酬（%/年）",
    },
    "anpassad.tax_model": {
        "sv": "Skattemodell",
        "en": "Tax treatment",
        "zh-TW": "稅務模型",
    },
    "anpassad.sum_warning": {
        "sv": "Summan av andelarna: **{total:.1f} %** — måste vara 100 %.",
        "en": "Total allocation: **{total:.1f} %** — must equal 100 %.",
        "zh-TW": "占比總和：**{total:.1f} %** — 須為 100 %。",
    },

    # ---- Tax model labels ----
    "tax.isk": {
        "sv": "ISK (1,065 % schablonskatt)",
        "en": "ISK (1.065 % flat-rate tax on capital base)",
        "zh-TW": "ISK 投資儲蓄帳戶（年税 1.065 %）",
    },
    "tax.kf": {
        "sv": "KF (1,065 % schablonskatt)",
        "en": "KF (1.065 % flat-rate tax on capital base)",
        "zh-TW": "KF 資本保險（年税 1.065 %）",
    },
    "tax.af": {
        "sv": "AF (30 % årlig realisation)",
        "en": "Taxable brokerage account (30 % on annual realised gains)",
        "zh-TW": "一般證券帳戶（年度實現收益課 30 %）",
    },
    "tax.none": {
        "sv": "Ingen skatt (0 %)",
        "en": "Tax-free (0 %)",
        "zh-TW": "免稅（0 %）",
    },

    # ---- Loan panel ----
    "loan.header": {
        "sv": "💰 Lån",
        "en": "💰 Loan",
        "zh-TW": "💰 房貸",
    },
    "loan.insufficient_cash": {
        "sv": (
            "Otillräcklig total kontantinsats: hushållet har {have} kr "
            "men behöver minst {need} kr (10 % av köpeskilling; "
            "bolånetaket 2026-04-01 är 90 %)."
        ),
        "en": (
            "Insufficient household cash: you have {have} kr but need at "
            "least {need} kr (10 % of purchase price; the loan-to-value "
            "ceiling from 2026-04-01 is 90 %)."
        ),
        "zh-TW": (
            "家庭現金不足：您有 {have} kr，但至少需要 {need} kr"
            "（成交價的 10 %；2026-04-01 後貸款上限為 90 %）。"
        ),
    },
    "loan.insats_label": {
        "sv": "Insats (kr) — {lo} – {hi}",
        "en": "Deposit (kr) — {lo} – {hi}",
        "zh-TW": "頭期款（kr） — {lo} – {hi}",
    },
    "loan.ltv_label": {
        "sv": "Belåningsgrad (%) — {lo} – {hi}",
        "en": "Loan-to-value (%) — {lo} – {hi}",
        "zh-TW": "貸款成數（%） — {lo} – {hi}",
    },
    "loan.slider_label": {
        "sv": "Dra för att justera insats",
        "en": "Drag to adjust deposit",
        "zh-TW": "拖曳以調整頭期款",
    },
    "loan.slider_locked": {
        "sv": "Insats låst till {amt} kr (endast möjliga värdet)",
        "en": "Deposit fixed at {amt} kr (only feasible value)",
        "zh-TW": "頭期款固定為 {amt} kr（僅此值可行）",
    },
    "loan.binding": {
        "sv": "Bindningstid",
        "en": "Fixation period",
        "zh-TW": "利率固定期",
    },
    "loan.scenario": {
        "sv": "Räntescenario",
        "en": "Rate scenario",
        "zh-TW": "利率情境",
    },
    "loan.scenario.low": {
        "sv": "LOW (låg)",
        "en": "LOW (low)",
        "zh-TW": "LOW（低）",
    },
    "loan.scenario.base": {
        "sv": "BASE (basscenario)",
        "en": "BASE (baseline)",
        "zh-TW": "BASE（基準）",
    },
    "loan.scenario.high": {
        "sv": "HIGH (hög)",
        "en": "HIGH (high)",
        "zh-TW": "HIGH（高）",
    },
    "loan.stabelo_hit": {
        "sv": "Stabelo snapshot: **{rate:.2f} %**",
        "en": "Stabelo snapshot: **{rate:.2f} %**",
        "zh-TW": "Stabelo 快照：**{rate:.2f} %**",
    },
    "loan.stabelo_miss": {
        "sv": "Stabelo: saknas för denna LTV/bindningstid",
        "en": "Stabelo: no quote for this LTV/fixation",
        "zh-TW": "Stabelo：此 LTV/利率固定期查無報價",
    },
    "loan.scenario_rate": {
        "sv": "Scenario ({sc}): **{rate:.2f} %**",
        "en": "Scenario ({sc}): **{rate:.2f} %**",
        "zh-TW": "情境 ({sc})：**{rate:.2f} %**",
    },
    "loan.use_stabelo": {
        "sv": "Använd Stabelo snapshot-ränta (gäller Ditt val, scenario C)",
        "en": "Use Stabelo snapshot rate (applies to your pick, scenario C)",
        "zh-TW": "使用 Stabelo 快照利率（僅套用於您選的情境 C）",
    },
    "loan.refresh_stabelo": {
        "sv": "🔄 Uppdatera Stabelo",
        "en": "🔄 Refresh Stabelo",
        "zh-TW": "🔄 更新 Stabelo",
    },

    # ---- Metrics table ----
    "metrics.header": {
        "sv": "Slutvärden (innehav till horisontens slut)",
        "en": "Terminal values (held to end of horizon)",
        "zh-TW": "期末數值（持有至期末）",
    },
    "metrics.scenario_a": {
        "sv": "A. Maximal insats — {insats} kr · LTV {ltv:.0f} %",
        "en": "A. Maximum deposit — {insats} kr · LTV {ltv:.0f} %",
        "zh-TW": "A. 最大頭期款 — {insats} kr · 貸款成數 {ltv:.0f} %",
    },
    "metrics.scenario_b": {
        "sv": "B. Minimal insats (10 %) — {insats} kr · LTV {ltv:.0f} %",
        "en": "B. Minimum deposit (10 %) — {insats} kr · LTV {ltv:.0f} %",
        "zh-TW": "B. 最小頭期款 (10 %) — {insats} kr · 貸款成數 {ltv:.0f} %",
    },
    "metrics.scenario_c": {
        "sv": "C. Ditt val — {insats} kr · LTV {ltv:.0f} %",
        "en": "C. Your pick — {insats} kr · LTV {ltv:.0f} %",
        "zh-TW": "C. 您的選擇 — {insats} kr · 貸款成數 {ltv:.0f} %",
    },
    "metrics.col.scenario": {
        "sv": "Scenario",
        "en": "Scenario",
        "zh-TW": "情境",
    },
    "metrics.col.portfolio": {
        "sv": "Portfölj (ex. bostad)",
        "en": "Portfolio (excl. property)",
        "zh-TW": "投資資產（不含房產）",
    },
    "metrics.col.property": {
        "sv": "Bostadsvärde",
        "en": "Property value",
        "zh-TW": "房產價值",
    },
    "metrics.col.loan": {
        "sv": "Kvarvarande lån",
        "en": "Outstanding loan",
        "zh-TW": "剩餘貸款",
    },
    "metrics.col.net_worth": {
        "sv": "Nettoförmögenhet",
        "en": "Net worth",
        "zh-TW": "淨資產",
    },
    "metrics.col.terminal_brutto": {
        "sv": "Slutlig brutto (kr/år)",
        "en": "Final gross salary (kr/year)",
        "zh-TW": "期末稅前年薪（kr/年）",
    },
    "metrics.col.avg_savings": {
        "sv": "Genomsnittligt sparande (kr/mån)",
        "en": "Average savings (kr/month)",
        "zh-TW": "平均每月儲蓄（kr/月）",
    },
    "metrics.col.cum_tax": {
        "sv": "Total skatt över horisonten",
        "en": "Cumulative tax over horizon",
        "zh-TW": "期間累計繳稅",
    },
    "metrics.col.cum_ranteavdrag": {
        "sv": "Total ränteavdrag-återbäring",
        "en": "Cumulative interest-deduction refund",
        "zh-TW": "期間累計房貸利息退稅",
    },

    # ---- Monthly cash flow overview ----
    "flow.header": {
        "sv": "📊 Månadsöversikt — var går pengarna?",
        "en": "📊 Monthly overview — where does the money go?",
        "zh-TW": "📊 月度總覽 — 錢都流向哪裡？",
    },
    "flow.year_select": {
        "sv": "Visa genomsnittlig månad för år",
        "en": "Show average month for year",
        "zh-TW": "顯示以下年度的平均月份",
    },
    "flow.category": {
        "sv": "Kategori",
        "en": "Category",
        "zh-TW": "類別",
    },
    "flow.amount": {
        "sv": "Belopp (kr/mån)",
        "en": "Amount (kr/month)",
        "zh-TW": "金額（kr/月）",
    },
    "flow.share": {
        "sv": "Andel av brutto",
        "en": "Share of gross",
        "zh-TW": "佔稅前比例",
    },
    "flow.cat.brutto": {
        "sv": "Brutto lön (hushåll)",
        "en": "Gross salary (household)",
        "zh-TW": "稅前收入（家庭合計）",
    },
    "flow.cat.tax_gross": {
        "sv": "Inkomstskatt (kommunal + statlig − jobbskatteavdrag)",
        "en": "Income tax (municipal + state − earned-income credit)",
        "zh-TW": "所得稅（市政稅 + 國稅 − 工作所得扣抵）",
    },
    "flow.cat.interest": {
        "sv": "Bolåneränta",
        "en": "Mortgage interest",
        "zh-TW": "房貸利息",
    },
    "flow.cat.amortization": {
        "sv": "Amortering",
        "en": "Amortisation",
        "zh-TW": "本金攤還",
    },
    "flow.cat.avgift": {
        "sv": "Månadsavgift till brf",
        "en": "Monthly service charge",
        "zh-TW": "每月管理費",
    },
    "flow.cat.personal": {
        "sv": "Personliga utgifter (inflationsjusterat)",
        "en": "Personal expenses (inflation-adjusted)",
        "zh-TW": "個人開銷（已計入通脹）",
    },
    "flow.cat.ranteavdrag": {
        "sv": "Ränteavdrag-återbäring (månadsgenomsnitt)",
        "en": "Interest-deduction refund (monthly average)",
        "zh-TW": "房貸利息退稅（月平均）",
    },
    "flow.cat.savings": {
        "sv": "Sparande från kassaflöde",
        "en": "Savings from cash flow",
        "zh-TW": "由現金流轉入投資",
    },
    "flow.cat.to_portfolio": {
        "sv": "Totalt till portfölj (= sparande + ränteavdrag)",
        "en": "Total to portfolio (= savings + interest deduction)",
        "zh-TW": "轉入投資合計（儲蓄 + 退稅）",
    },
    "flow.chart.header": {
        "sv": "Kategorifördelning över tid (genomsnittlig månad per år)",
        "en": "Category breakdown over time (average month per year)",
        "zh-TW": "類別結構隨時間變化（每年平均月份）",
    },
    "flow.chart.y": {
        "sv": "kr/mån",
        "en": "kr/month",
        "zh-TW": "kr/月",
    },
    "flow.chart.xaxis_year": {
        "sv": "År",
        "en": "Year",
        "zh-TW": "年度",
    },
    "flow.inflation_note": {
        "sv": (
            "Personliga utgifter växer {rate:.1f} %/år. Bolåneavgift växer "
            "{avg_rate:.1f} %/år. Brutto växer {inc_rate:.1f} %/år. Alla "
            "belopp är nominella (inte inflationsjusterade tillbaka till "
            "dagens kronor)."
        ),
        "en": (
            "Personal expenses grow at {rate:.1f} %/year; service charge at "
            "{avg_rate:.1f} %/year; gross income at {inc_rate:.1f} %/year. All "
            "amounts are nominal (not deflated back to today's kr)."
        ),
        "zh-TW": (
            "個人開銷年增 {rate:.1f} %；管理費年增 {avg_rate:.1f} %；"
            "稅前收入年增 {inc_rate:.1f} %。所有金額為名目值（未折算為今日 kr）。"
        ),
    },
    "metrics.sell_annotation": {
        "sv": (
            "Om du säljer bostaden vid horisontens slut "
            "(22 % reavinstskatt + {broker:.1f} % mäklararvode): {bits}"
        ),
        "en": (
            "If you sell the property at the end of the horizon "
            "(22 % capital-gains tax + {broker:.1f} % agent fee): {bits}"
        ),
        "zh-TW": (
            "若於期末賣出房產"
            "（22 % 資本利得稅 + {broker:.1f} % 仲介費）：{bits}"
        ),
    },
    "metrics.infeasible": {
        "sv": "⚠️ Månader med cash flow < −likviditetsbuffert: {bits}",
        "en": "⚠️ Months where cash flow < −liquidity buffer: {bits}",
        "zh-TW": "⚠️ 現金流 < −流動性緩衝 的月份：{bits}",
    },

    # ---- Main chart ----
    "chart.title": {
        "sv": "Nettoförmögenhet över tid",
        "en": "Net worth over time",
        "zh-TW": "淨資產隨時間變化",
    },
    "chart.legend.a": {
        "sv": "A: Max insats (LTV {ltv:.0f} %)",
        "en": "A: Max deposit (LTV {ltv:.0f} %)",
        "zh-TW": "A：最大頭期款（貸款成數 {ltv:.0f} %）",
    },
    "chart.legend.b": {
        "sv": "B: Min insats 10 % (LTV 90 %)",
        "en": "B: Min deposit 10 % (LTV 90 %)",
        "zh-TW": "B：最小頭期款 10 %（貸款成數 90 %）",
    },
    "chart.legend.c": {
        "sv": "C: Ditt val (LTV {ltv:.0f} %)",
        "en": "C: Your pick (LTV {ltv:.0f} %)",
        "zh-TW": "C：您的選擇（貸款成數 {ltv:.0f} %）",
    },
    "chart.xaxis": {
        "sv": "Månad",
        "en": "Month",
        "zh-TW": "月份",
    },
    "chart.yaxis": {
        "sv": "Nettoförmögenhet (kr)",
        "en": "Net worth (kr)",
        "zh-TW": "淨資產（kr）",
    },

    # ---- LTV sweep ----
    "sweep.header": {
        "sv": "Jämförelse över LTV-val (10-procentssteg)",
        "en": "Comparison across LTV choices (10 pp steps)",
        "zh-TW": "不同貸款成數比較（10 個百分點一階）",
    },
    "sweep.col.ltv": {
        "sv": "LTV",
        "en": "LTV",
        "zh-TW": "貸款成數",
    },
    "sweep.col.terminal_nw": {
        "sv": "Terminal NW (kr)",
        "en": "Terminal net worth (kr)",
        "zh-TW": "期末淨資產（kr）",
    },
    "sweep.col.infeasible": {
        "sv": "Inf. mån",
        "en": "Inf. mo.",
        "zh-TW": "不可行月數",
    },
    "sweep.col.final_loan": {
        "sv": "Slutlån (kr)",
        "en": "Ending loan (kr)",
        "zh-TW": "期末貸款（kr）",
    },
    "sweep.col.final_portfolio": {
        "sv": "Slutportfölj (kr)",
        "en": "Ending portfolio (kr)",
        "zh-TW": "期末投資資產（kr）",
    },
    "sweep.col.irr": {
        "sv": "Inkrementell IRR vs 90 %",
        "en": "Incremental IRR vs 90 %",
        "zh-TW": "相對 90 % 的邊際內部報酬率",
    },
    "sweep.chart.x": {
        "sv": "LTV",
        "en": "LTV",
        "zh-TW": "貸款成數",
    },
    "sweep.chart.y": {
        "sv": "Terminal nettoförmögenhet (kr)",
        "en": "Terminal net worth (kr)",
        "zh-TW": "期末淨資產（kr）",
    },

    # ---- Expanders ----
    "exp.cashflow": {
        "sv": "📊 Månadsvis kassaflöde (Ditt val)",
        "en": "📊 Monthly cash flow (your pick)",
        "zh-TW": "📊 每月現金流（您的選擇）",
    },
    "exp.cashflow.x": {
        "sv": "Månad",
        "en": "Month",
        "zh-TW": "月份",
    },
    "exp.cashflow.post": {
        "sv": "Post",
        "en": "Item",
        "zh-TW": "項目",
    },
    "exp.rate_sens": {
        "sv": "🔬 Räntekänslighet (±1 pp shock, Ditt val)",
        "en": "🔬 Rate sensitivity (±1 pp shock, your pick)",
        "zh-TW": "🔬 利率敏感度（±1 pp 衝擊，您的選擇）",
    },
    "exp.rate.shift": {
        "sv": "Skift (pp)",
        "en": "Shift (pp)",
        "zh-TW": "變動（pp）",
    },
    "exp.rate.effective": {
        "sv": "Effektiv ränta",
        "en": "Effective rate",
        "zh-TW": "實效利率",
    },
    "exp.rate.terminal_nw": {
        "sv": "Terminal NW",
        "en": "Terminal net worth",
        "zh-TW": "期末淨資產",
    },
    "exp.rate.inf_months": {
        "sv": "Inf. mån",
        "en": "Inf. mo.",
        "zh-TW": "不可行月數",
    },

    # ---- Footer ----
    "footer.disclaimer": {
        "sv": (
            "Modellregler: 2026-04-01 FI-reform (LTV-tak 90 %, amortering 0/1/2 %-trappa, "
            "avskaffat 4,5×-tillägg). ISK 2026: 300 000 kr fribelopp per person, "
            "1,065 % på överskott. Inkomstskatt: progressiv kommunal + 20 % statlig över "
            "skiktgränsen 643 000 kr; jobbskatteavdrag enligt Prop. 2025/26:32; "
            "ränteavdrag begränsas till det skattebelopp som återstår efter JSA. "
            "Se `ref/swedish-mortgage-policy-2026.md` och `ref/swedish-income-tax-2026.md`."
        ),
        "en": (
            "Model rules: 2026-04-01 Finansinspektionen reform (90 % LTV cap, "
            "0/1/2 % amortisation ladder, scrapped 4.5× income surcharge). "
            "ISK 2026: 300 000 kr tax-free allowance per person, 1.065 % flat rate above. "
            "Income tax: progressive municipal + 20 % state above the 643 000 kr bracket "
            "threshold; earned-income tax credit per Prop. 2025/26:32; "
            "mortgage-interest deduction capped at tax remaining after the credit. "
            "See `ref/swedish-mortgage-policy-2026.md` and `ref/swedish-income-tax-2026.md`."
        ),
        "zh-TW": (
            "模型依據：2026-04-01 瑞典金融監理局改制（貸款成數上限 90 %、"
            "攤還 0/1/2 % 階梯、取消 4.5× 收入加強攤銷規定）。"
            "ISK 2026：每人 300 000 kr 免稅額，超出部分課 1.065 %。"
            "所得稅：累進市政稅 + 國稅 20 %（課稅所得超過 643 000 kr 時適用）；"
            "工作所得扣抵依 Prop. 2025/26:32 規定；"
            "房貸利息扣抵上限為扣抵工作所得扣抵後剩餘的稅額。"
            "詳見 `ref/swedish-mortgage-policy-2026.md` 與 `ref/swedish-income-tax-2026.md`。"
        ),
    },

    # ---- Monte Carlo ----
    "mc.header": {
        "sv": "🎲 Monte Carlo stresstest",
        "en": "🎲 Monte Carlo stress test",
        "zh-TW": "🎲 Monte Carlo 壓力測試",
    },
    "mc.intro": {
        "sv": (
            "Simulera N stokastiska vägar med volatila marknader, räntor och "
            "bostadsvärde. Visar 10 / 50 / 90 percentiler istället för ett "
            "deterministiskt värde, vilket synliggör \"worst case\"-risken "
            "som det vanliga läget döljer."
        ),
        "en": (
            "Simulate N stochastic paths with volatile markets, interest rates "
            "and property value. Shows the 10th / 50th / 90th percentile "
            "instead of one deterministic number, which exposes the worst-case "
            "risk that the regular view hides."
        ),
        "zh-TW": (
            "模擬 N 條隨機路徑，投資報酬、利率與房價都帶有波動性。"
            "以 10 / 50 / 90 百分位取代確定性數值，"
            "讓一般視角隱藏的「最糟情況」風險顯現。"
        ),
    },
    "mc.n_paths": {
        "sv": "Antal vägar (fler = noggrannare, långsammare)",
        "en": "Number of paths (more = more accurate, slower)",
        "zh-TW": "路徑數量（越多越精準、越慢）",
    },
    "mc.portfolio_vol": {
        "sv": "Portföljvolatilitet (%/år, std.)",
        "en": "Portfolio volatility (%/year, std. dev.)",
        "zh-TW": "投資組合年波動率（%/年，標準差）",
    },
    "mc.rate_vol": {
        "sv": "Räntevolatilitet (pp/år, std.)",
        "en": "Rate volatility (pp/year, std. dev.)",
        "zh-TW": "利率年波動（pp/年，標準差）",
    },
    "mc.property_vol": {
        "sv": "Bostadsvärdevolatilitet (%/år, std.)",
        "en": "Property-value volatility (%/year, std. dev.)",
        "zh-TW": "房價年波動率（%/年，標準差）",
    },
    "mc.correlation": {
        "sv": "Korrelation ränta ↔ bostadspris",
        "en": "Correlation rate ↔ property",
        "zh-TW": "利率 ↔ 房價相關性",
    },
    "mc.correlation_help": {
        "sv": (
            "Negativ korrelation: höga räntor trycker ner bostadspriser. "
            "Historisk riktning i Sverige."
        ),
        "en": (
            "Negative correlation: high rates push property prices down. "
            "Historical direction in Sweden."
        ),
        "zh-TW": (
            "負相關：利率上升會壓抑房價。符合瑞典的歷史方向。"
        ),
    },
    "mc.run": {
        "sv": "▶️ Kör Monte Carlo",
        "en": "▶️ Run Monte Carlo",
        "zh-TW": "▶️ 執行 Monte Carlo",
    },
    "mc.running": {
        "sv": "Kör {n} vägar × 3 scenarier…",
        "en": "Running {n} paths × 3 scenarios…",
        "zh-TW": "執行 {n} 條路徑 × 3 種情境…",
    },
    "mc.chart_title": {
        "sv": "Nettoförmögenhet — P10 / P50 / P90 över {n} vägar",
        "en": "Net worth — P10 / P50 / P90 across {n} paths",
        "zh-TW": "淨資產 — 跨 {n} 條路徑的 P10 / P50 / P90",
    },
    "mc.scenario_median": {
        "sv": "{label} (P50)",
        "en": "{label} (P50)",
        "zh-TW": "{label}（P50）",
    },
    "mc.scenario_band": {
        "sv": "{label} P10–P90",
        "en": "{label} P10–P90",
        "zh-TW": "{label} P10–P90",
    },
    "mc.terminal_header": {
        "sv": "Terminal nettoförmögenhet över percentiler",
        "en": "Terminal net worth across percentiles",
        "zh-TW": "期末淨資產的百分位分布",
    },
    "mc.col.p10": {
        "sv": "P10 (sämre 10 %)",
        "en": "P10 (worse 10 %)",
        "zh-TW": "P10（較差的 10 %）",
    },
    "mc.col.p50": {
        "sv": "P50 (median)",
        "en": "P50 (median)",
        "zh-TW": "P50（中位數）",
    },
    "mc.col.p90": {
        "sv": "P90 (bättre 10 %)",
        "en": "P90 (better 10 %)",
        "zh-TW": "P90（較好的 10 %）",
    },
    "mc.col.p_infeasible": {
        "sv": "Sannolikhet infeasibility > 0",
        "en": "Probability of any infeasibility",
        "zh-TW": "出現不可行月份的機率",
    },
    "mc.risk_note": {
        "sv": (
            "Om P(infeasibility) är hög → strategin är flaskhals-känslig "
            "mot nedåtrisk (marknadsfall, räntechock, fallande bostadspris)."
        ),
        "en": (
            "If P(infeasibility) is high → the strategy is fragile to "
            "downside (market drawdown, rate shock, falling property)."
        ),
        "zh-TW": (
            "若 P(infeasibility) 偏高 → 此策略對下行風險"
            "（市場下跌、利率衝擊、房價下跌）較脆弱。"
        ),
    },

    # ---- Config errors ----
    "err.config_invalid": {
        "sv": "Hushållskonfiguration ogiltig: {err}",
        "en": "Household configuration invalid: {err}",
        "zh-TW": "家庭設定無效：{err}",
    },
    "err.stabelo_load": {
        "sv": "Kunde inte ladda Stabelo-snapshot: {err}",
        "en": "Could not load Stabelo snapshot: {err}",
        "zh-TW": "無法載入 Stabelo 快照：{err}",
    },
    "err.kommun_load": {
        "sv": "Kunde inte ladda kommunalskatt-snapshot: {err}",
        "en": "Could not load municipal-tax snapshot: {err}",
        "zh-TW": "無法載入市政稅快照：{err}",
    },
}


def current_lang() -> str:
    try:
        return st.session_state.get("lang", DEFAULT_LANG)
    except Exception:
        return DEFAULT_LANG


def t(key: str, lang: str | None = None) -> str:
    """Look up a translation key. Returns the raw key if missing."""
    lang = lang or current_lang()
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key
