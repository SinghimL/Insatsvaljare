---
title: 瑞典個人所得稅與 skattereduktion 規則（2026 年度）
last_updated: 2026-04-19
scope: Insatsväljare 模型的 brutto → netto 轉換、ränteavdrag cap、jobbskatteavdrag
---

# 瑞典個人所得稅參考（2026 年）

> 本文件收斂建模 Insatsväljare 時所需的 2026 年個人所得稅規則：從 **brutto 工資** 推出 **netto 現金流**、決定 **ränteavdrag 可抵扣額上限**、以及 kommun 與收入層級如何影響 insats strategy 的實際報酬。所有數值皆為 Skatteverket、SCB、Riksdagen 公告的 2026 年數字。適用對象：**未滿 66 歲、領薪工作者**。66+ 及 pensionärer 規則不同，本文不涵蓋。

---

## 1. 為什麼這份文件對 Insats 建模很重要

CLAUDE.md §2 的核心 thesis：*降低 insats → 省下的錢投資 → 比較 10 年後淨資產*。

這個比較只有在「月現金流」與「ränteavdrag 實得」**對稅後收入正確建模**時才有意義。否則模型會：

1. **高估低薪家庭的高-LTV 優勢**：無條件給滿額 ränteavdrag，但低薪家庭繳的稅可能根本吸收不了。
2. **把 brutto 當 netto 算 cash flow**：高估可支配現金，讓「高 LTV + 高利息」看起來比實際更可行。
3. **忽略 kommun 差異**：Stockholm (30.55 %) vs Dorotea (35.65 %) 的 kommunalskatt 差 5 個百分點，對月 netto 的影響比利率變動更大。

這三個效應**是 strategy-differential**（在不同 insats 之間不等價影響），所以必須建模。

---

## 2. 2026 基礎常數

| 常數 | 值 | 用途 |
|---|---|---|
| **Prisbasbelopp (PBB)** | **59 200 kr** | Grundavdrag、jobbskatteavdrag 公式的基準 |
| **Förhöjt prisbasbelopp** | 60 500 kr | 退休金相關（本模型不用） |
| **Inkomstbasbelopp (IBB)** | 83 400 kr | 社會保險基礎（本模型不用） |
| **Skiktgräns (statlig skatt)** | **643 000 kr** | 稅基（已扣 grundavdrag 後的 FFI）超過此線的部分課 20 % |
| **Brytpunkt (statlig skatt)**（< 66 歲） | **660 400 kr** | 毛薪超過此線才需繳 statlig skatt ≈ 55 033 kr/mån |
| **Statlig skattesats** | **20 %** | 對超過 skiktgräns 的 taxable income |
| **Kapitalinkomstskatt** | 30 % | 資本所得一律 30 %（ränteavdrag 是此率的反向） |
| **Average kommunalskatt 2026** | 32.38 % | 全國加權平均（SCB） |

> 🚨 **同步警告**：若 Skatteverket 公告 2027 年數字，需同步更新此表與 `src/insatsvaljare/tax_income.py` 的常數。本文件與代碼常數必須一致。

---

## 3. Kommunalskatt 2026（kommun + region 合計）

本模型允許使用者選擇 kommun 或直接輸入稅率。以下是有代表性的樣本：

| Kommun | Kommunalskatt 2026 | 備註 |
|---|---|---|
| **Österåker** | 28.93 % | 全國最低（連續 8 年） |
| **Solna** | 29.70 % | Stockholms län 低稅區 |
| **Täby** | 29.88 % | — |
| **Lidingö** | 29.67 % | — |
| **Nacka** | 30.11 % | — |
| **Sollentuna** | 30.45 % | — |
| **Stockholm** | **30.55 %** | 首都（預設值） |
| **Danderyd** | 30.58 % | — |
| **Malmö / Lund** | 32.42 % | Skåne |
| **Göteborg** | 32.60 % | Västra Götaland |
| **Uppsala** | 32.85 % | — |
| **Dorotea** | 35.65 % | 全國最高 |
| **全國平均（加權）** | 32.38 % | SCB |

Kommunalskatt = kommun-del + region-del。兩者合計用在：
- 所得稅計算：`taxable_income × KS`
- Jobbskatteavdrag 金額：`(bracket_formula) × KS`
- **注意**：KS 越高 → kommunalskatt 越高 → jobbskatteavdrag 金額**也越高**（因為 JSA 乘以 KS）。高 KS 不等於淨稅負更高，要看 brutto 級距。

---

## 4. Grundavdrag 公式（< 66 歲，2026）

Grundavdrag 是從 **fastställd förvärvsinkomst (FFI)** 扣除的基本免稅額。公式為分段函數，**每個 kommun 都一樣**（國定）。

令 PBB = 59 200 kr，FFI 為年度毛薪（簡化下等於 arbetsinkomst）：

| FFI 級距 | Grundavdrag 公式 |
|---|---|
| FFI ≤ 0.99 × PBB ≈ **58 608** | GA = FFI |
| 0.99 < FFI/PBB ≤ 2.72（≈ **58 608 – 161 024**） | GA = 0.423 × PBB + 0.2 × (FFI − 0.99 × PBB) |
| 2.72 < FFI/PBB ≤ 3.11（≈ **161 024 – 184 112**） | GA = 0.77 × PBB = **45 584 kr** ← **最大值** |
| 3.11 < FFI/PBB ≤ 7.88（≈ **184 112 – 466 496**） | GA = 0.77 × PBB − 0.1 × (FFI − 3.11 × PBB) |
| FFI > 7.88 × PBB ≈ **466 496** | GA = 0.293 × PBB = **17 346 kr** ← **最小值** |

**整數化**：Skatteverket 將結果 **進位到整百**（avrundas uppåt till jämna 100 kronor）。模型可保留原值不進位（誤差 < 100 kr/年）。

**Skatteverket 公告值**（與公式一致，已進位）：min **17 400**、max **45 600**、低收入底線 **25 100**。

---

## 5. Jobbskatteavdrag 公式（< 66 歲，2026 新規）

Jobbskatteavdrag (JSA) 是一種 **skattereduktion**（減稅），**只對 arbetsinkomst**（薪資、自由業收入等主動所得，不含資本所得、退休金）。2026-01-01 起生效的強化（Prop. 2025/26:32）在 3.24–8.08 PBB 這一段**提高了減稅**，目標族群是月薪 16–40 kkr 的正職工作者。

**2025 年起已廢除高收入 phase-out**，高收入 JSA 維持最大值不下降。

令 AI = arbetsinkomst（≈ brutto 年薪）、GA = grundavdrag(AI)、PBB = 59 200、KS = kommunalskattesats（decimal）：

| AI 級距 | JSA 公式（減稅額） |
|---|---|
| AI ≤ 0.91 × PBB ≈ **53 872** | JSA = (AI − GA) × KS |
| 0.91 < AI/PBB ≤ 3.24（≈ **53 872 – 191 808**） | JSA = (0.91 × PBB + 0.3874 × (AI − 0.91 × PBB) − GA) × KS |
| 3.24 < AI/PBB ≤ 8.08（≈ **191 808 – 478 336**）🆕 **2026 強化區間** | JSA = (1.813 × PBB + 0.251 × (AI − 3.24 × PBB) − GA) × KS |
| AI > 8.08 × PBB ≈ **478 336** | JSA = (3.027 × PBB − GA) × KS |

**最大 JSA**（AI ≥ 8.08 PBB）：
- 以 KS = 30.55 %（Stockholm）：JSA_max = (3.027 × 59 200 − 17 346) × 0.3055 ≈ **49 440 kr/år**（≈ 4 120 kr/mån）
- 以 KS = 32.38 %（riksavg）：JSA_max ≈ **52 400 kr/år**（≈ 4 366 kr/mån ← Skatteverket 公告值 ✓）
- 以 KS = 35.65 %（Dorotea）：JSA_max ≈ **57 700 kr/år**（≈ 4 810 kr/mån）

**建模註**：AI 與 FFI 在本模型簡化下 **視為相等**（忽略 allmän pensionsavgift，因為該 avgift 有對應的 skattereduktion 完全抵銷，淨效應為零）。嚴格定義 FFI = AI − allmän_pensionsavgift_reduktion_base。

---

## 6. Statlig inkomstskatt

在 taxable income（= FFI − GA）超過 **skiktgräns = 643 000 kr** 的部分，課 **20 %**。

公式：
```
statlig_skatt = 0.20 × max(0, (FFI − GA) − 643 000)
```

同等地，以毛薪 brytpunkt 表達：當 AI > 660 400 kr 時開始有 statlig skatt。

---

## 7. Ränteavdrag 與 skattereduktion 上限（**新機制，本模型必補**）

Ränteavdrag 本質是 **skattereduktion på negativ kapitalinkomst**：

```
ränteavdrag_theoretical = 0.30 × min(interest, 100 000) + 0.21 × max(0, interest − 100 000)
```

但**必須有足夠的 skatt 可以被減**。實際可抵扣額 = min(理論值, 可用稅額)。

### 7.1 Skattereduktion 套用順序（2026 年度）

依 Inkomstskattelagen 67 kap 2 §，順序為：

1. **Allmän pensionsavgift** skattereduktion（等於 pensionsavgift 全抵，淨零）
2. **Sjöinkomst** skattereduktion（罕見，略過）
3. **Jobbskatteavdrag** (JSA)
4. **Sjuk- och aktivitetsersättning** reduktion（不適用於領薪者）
5. **Grön teknik / RUT / ROT** hushållsavdrag（不建模）
6. **Underskott av kapital**（含 **ränteavdrag**）
7. 其他（mikroproduktion 等，略過）

### 7.2 本模型簡化算法

```
tax_before_jsa = kommunal_skatt + statlig_skatt       # 對 taxable förvärvsinkomst
tax_after_jsa  = max(0, tax_before_jsa − jobbskatteavdrag)
tax_after_rant = max(0, tax_after_jsa − ränteavdrag_theoretical)
ränteavdrag_actual = tax_after_jsa − tax_after_rant   # 實得，受 cap 限制
```

等價寫法：`ränteavdrag_actual = min(ränteavdrag_theoretical, tax_after_jsa)`

### 7.3 什麼時候 cap 會咬到？

以 Stockholm KS = 30.55 %、單身、無其他收入為例：

| Brutto AI (kr/år) | Kommunal+Statlig | JSA | 餘下可吸收 ränteavdrag |
|---|---|---|---|
| 200 000 | ≈ 52 000 | ≈ 22 000 | ≈ 30 000 |
| 400 000 | ≈ 114 000 | ≈ 49 000 | ≈ 65 000 |
| 600 000 | ≈ 175 000 | ≈ 49 000 | ≈ 126 000 |
| 800 000 | ≈ 244 000 | ≈ 49 000 | ≈ 195 000 |

若利息 150 kkr（例：3.6M 貸款 × 4 %）→ 理論 ränteavdrag = 30k + 10.5k = **40.5k**：
- AI 200k：cap 30k → **只能抵 30k，損失 10.5k**
- AI 400k 以上：cap 不咬到，全額 40.5k 可抵

**這就是低薪族 × 高 LTV 的稅務劣勢來源**，必須建入模型。

### 7.4 Sambeskattning（雙人家庭）

瑞典**無家庭共同申報**；夫妻/同居人**各自**計算所得稅與 skattereduktion。**Ränteavdrag 同樣各自申報**：

- 貸款共同簽名（medlåntagare）→ 利息可按比例在雙方之間分配，常見 50/50。
- 模型中 `n_persons` 僅用於 ISK fribelopp（§2 ISK 規則）。**不自動把 income/ränteavdrag 翻倍**。
- 若使用者選 2 人家庭，模型建議：
  - `brutto_income` 仍為**家庭合計** brutto（使用者輸入）
  - 但內部 **拆半**，各自套一套稅算、最後把兩人 netto 加回
  - Ränteavdrag 的 cap 也是各自算後相加（比單人算更寬鬆，因為 JSA 各算一次）

這是 2026 版本合理的簡化。嚴格正確需要雙方各自 AI、各自 kommun（可不同）、各自 pension 狀態。V1 用「brutto 對半」作為合理預設。

---

## 8. 完整 netto 計算流程

輸入：`AI`（brutto 年薪）、`kommunalskatt`（KS, decimal）、`annual_interest`（貸款年度利息）

```
# Step 1: 基礎稅額
GA = grundavdrag(AI)                             # §4 公式
taxable = max(0, AI - GA)                        # 課稅所得
kommunal = taxable × KS                          # 市政 + 區域稅
statlig  = 0.20 × max(0, taxable - 643_000)      # §6

# Step 2: Skattereduktioner
JSA = jobbskatteavdrag(AI, GA, KS)               # §5 公式
tax_after_jsa = max(0, kommunal + statlig - JSA)

rant_theoretical = 0.30 × min(interest, 100_000) + 0.21 × max(0, interest - 100_000)
rant_actual = min(rant_theoretical, tax_after_jsa)   # §7.2 cap

# Step 3: 最終稅負
final_tax = tax_after_jsa - rant_actual
netto_income = AI - final_tax
```

**注意**：ISK schablonskatt **不在此流程**。ISK 的稅以獨立的 skattereduktion 被 ranteavdrag 抵銷（技術上屬 kapitalinkomstskatt），本模型既有處理（見 `tax.py::isk_schablonskatt`）維持不變。Jobbskatteavdrag 與 ränteavdrag 只減 förvärvsinkomst 稅，不減 ISK。

---

## 9. 建模關鍵要點（for code）

1. **輸入改為 brutto**：`annual_gross_income` 重新命名對齊語意，UI 標示「brutto kr/år」。
2. **加入 kommun 選擇**：`kommunalskatt_rate: float`（預設 0.3055 = Stockholm）。可提供下拉選單或直接數值輸入。
3. **新模組 `tax_income.py`**：封裝 §4–§7 公式；常數集中在檔頭；以 `prisbasbelopp: float = 59_200` 作為參數方便未來更新。
4. **模型每月現金流改用 netto**：
   - 年初計算該年 netto = `compute_net_income(brutto, ks, interest_ytd_estimate)`
   - `monthly_income = netto / 12` 代入 cash_flow
   - 年度 reconciliation 時重算 actual ränteavdrag（使用實際利息），差額沖銷當年 cash flow
5. **Ränteavdrag cap 生效**：`tax.ranteavdrag()` 保留理論值，但 simulate() 年末對帳時套 cap，使用 `tax_after_jsa` 當上限。
6. **收入成長**：`income_growth` 對 brutto 成長，每年重算 netto；同時 `prisbasbelopp` 一般也會成長 → 暫固定 2026 值，避免過度建模（V1 scope）。

---

## 10. 單元測試必備案例

建議 `tests/test_tax_income.py` 至少涵蓋：

| Case | 檢查 |
|---|---|
| AI=0, KS=0.30 | netto=0, JSA=0, GA=0 |
| AI=400k, KS=0.3055, interest=0 | netto ≈ 315k（Skatteverket 公告值對照） |
| AI=660 400, KS=0.3055 | brytpunkt 邊界，statlig_skatt = 0 恰好 |
| AI=800k, KS=0.3055, interest=200k | full ränteavdrag（cap 不咬） |
| AI=200k, KS=0.3055, interest=150k | ränteavdrag 被 cap 截（損失） |
| Grundavdrag boundary | FFI = 0.99 PBB ± 1、FFI = 3.11 PBB ± 1 等分段端點 |
| JSA boundary | AI = 0.91/3.24/8.08 PBB 各臨界點 |

---

## 11. 資料來源

- [Skatteverket — Belopp och procent inkomstår 2026](https://www.skatteverket.se/privat/skatter/beloppochprocent/2026.4.1522bf3f19aea8075ba21.html)
- [Skatteverket — Teknisk beskrivning SKV 433 (2026 utgåva 36)](https://www.skatteverket.se/download/18.1522bf3f19aea8075ba55c/1766385913260/teknisk-beskrivning-skv-433-2026-utgava-36.pdf)
- [Riksdagen — Proposition 2025/26:32 "Sänkt skatt på arbetsinkomster, pension och sjuk- och aktivitetsersättning"](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/proposition/sankt-skatt-pa-arbetsinkomster-pension-och-sjuk-_hd0332/html/)
- [SCB — Totala kommunala skattesatser 2026, kommunvis](https://www.scb.se/hitta-statistik/statistik-efter-amne/offentlig-ekonomi/finanser-for-den-kommunala-sektorn/kommunalskatterna/pong/tabell-och-diagram/totala-kommunala-skattesatser-2026-kommunvis/)
- [Skatteverket — Skattesatser kommuner 2026 (XLSX)](https://skatteverket.se/download/18.1522bf3f19aea8075ba429/1765179297305/skattesatser-kommuner-2026.xlsx)
- [Skatteverket — Grundavdrag](https://skatteverket.se/privat/skatter/arbeteochinkomst/askattsedelochskattetabeller/grundavdrag.4.6d02084411db6e252fe80009078.html)
- [Skatteverket — Jobbskatteavdrag](https://www.skatteverket.se/privat/skatter/arbeteochinkomst/skattereduktioner/jobbskatteavdrag.4.6fdde64a12cc4eee2308000107.html)
- Wikipedia — Grundavdrag: [sv.wikipedia.org/wiki/Grundavdrag](https://sv.wikipedia.org/wiki/Grundavdrag)（分段公式歷史記錄）
- Wikipedia — Jobbskatteavdrag: [sv.wikipedia.org/wiki/Jobbskatteavdrag](https://sv.wikipedia.org/wiki/Jobbskatteavdrag)
