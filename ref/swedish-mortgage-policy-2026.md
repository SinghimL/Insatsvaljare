---
title: 瑞典購屋貸款政策與利率參考資料（2026年4月1日新規）
last_updated: 2026-04-17 (§5.2 updated 2026-04-17 for ISK 300k fribelopp)
scope: Bostadsrätt 購買情境，10 年投資窗口建模
---

# 瑞典 Bostadsrätt 購屋貸款政策與利率參考（2026 年 4 月後）

> 本文件整理 2026-04-01 起生效的新貸款規則，以及 SBAB / Stabelo 的利率結構，供後續建模最優 `insats` 比例時查閱。所有百分比、閾值皆為公開政策或市場行情，最終簽約條件仍應以銀行報價為準。

---

## 1. 2026 年 4 月 1 日起新貸款規則（Finansinspektionen 調整）

### 1.1 核心變動摘要

| 項目 | 舊規 (≤ 2026-03-31) | 新規 (≥ 2026-04-01) |
|---|---|---|
| 購房貸款上限（bolånetak） | 85 % av bostadens värde | **90 %**（最低 insats 10 %） |
| 「加強版」amorteringskrav（skuldkvot > 4,5× bruttoinkomst） | 額外 +1 % / 年 | **取消** |
| 標準 amortering（依 belåningsgrad） | 0 / 1 / 2 % | **不變**（見 §2） |
| 加貸（tilläggslån）上限 | 85 % LTV | **80 %** LTV |
| 房產重新估值頻率 | 不限 | **每 5 年最多一次**（自購入或上次估值起算） |

### 1.2 對購屋者的直接影響

- **最低頭期款由 15 % → 10 %**，可在同等自有資金下購買更貴的房子，或保留更多現金做投資（此即建模策略的核心槓桿）。
- **高槓桿 + 高收入**族群（原先被 skärpta kravet 追加 1 % 強制攤銷者）單月現金流壓力下降，其剩餘資金可轉為投資。
- **加貸 / 提款（tilläggslån）受限更嚴**：未來若房價上漲想抽出現金，受 80 % LTV 與「5 年一估值」雙重限制，流動性變差 —— 建模時應將「原始貸款 LTV」與「後續加貸空間」視為不同變數。

### 1.3 留意事項（建模時）

- 新規適用 **新貸款**；既有貸款維持原條款（grandfathered）。
- Finansinspektionen 可依宏觀審慎考量再次調整，本表為 2026-04-01 公告版本。
- 利息支出之 30 % **ränteavdrag**（≤ 100 000 kr 利息）與 21 % (> 100 000 kr) 仍有效；是否受限於 kapitalinkomst 餘額需個案判斷。

---

## 2. Amorteringskrav（強制攤銷）檔位

### 2.1 標準規則（2026-04 起；與舊規相同，僅取消收入加碼）

| Belåningsgrad (LTV) | 年攤銷率（佔原始貸款金額） |
|---|---|
| 0 – 50 % | **0 %**（免攤銷） |
| 50 – 70 % | **1 %** |
| 70 – 90 %（含新上限） | **2 %** |

> Belåningsgrad = 貸款餘額 / 房產取得時估值。估值在 **購入起 5 年內固定**，即便房價上漲也無法立即降檔減少攤銷。

### 2.2 已取消的加強版規則（僅供對照舊規使用）

舊規：若家庭總貸款 > **4,5 × 家庭年稅前收入**，需在上表基礎上再 +1 %/年。
→ 自 2026-04-01 起**廢除**，高收入高槓桿者單月攤銷額大幅下降。

### 2.3 各 LTV 情境下的攤銷金額（以 bostad 估值 V 為基準）

設房產購入估值為 V，貸款額 L = LTV × V。

| LTV | L | 年攤銷額 | 月攤銷額 |
|---|---|---|---|
| 40 % | 0,40 V | 0 | 0 |
| 50 % | 0,50 V | 0 | 0 |
| 60 % | 0,60 V | 1 % × L = 0,006 V | 0,0005 V |
| 70 % | 0,70 V | 1 % × L = 0,007 V | ~0,000583 V |
| 75 % | 0,75 V | 2 % × L = 0,015 V | 0,00125 V |
| 80 % | 0,80 V | 2 % × L = 0,016 V | ~0,001333 V |
| 85 % | 0,85 V | 2 % × L = 0,017 V | ~0,001417 V |
| 90 %（新上限） | 0,90 V | 2 % × L = 0,018 V | 0,0015 V |

> 範例：V = 5 000 000 kr、LTV = 85 %，L = 4 250 000 kr → 年攤銷 85 000 kr，月 ≈ 7 083 kr。

### 2.4 跨檔降檔機制

由於「5 年估值凍結」新規，**主動加速攤銷** 使 LTV 穿過 70 %、50 % 檔位，是可自行操控的現金流槓桿。建模時可考慮：
- 初期 LTV = 85 %，第 N 年透過一次性還款把 LTV 壓到 70 %（年攤銷率從 2 % → 1 %）。
- 相對於「留錢投資」，機會成本 = 投資報酬率 − 省下的攤銷金額本身（但這部分是還本，不是費用，只是時間差）。

---

## 3. 利率（Ränta）結構

### 3.1 SBAB（2026-04 月份參考）

#### 列表利率（Listränta）— 銀行官方牌價

| Bindningstid | Listränta |
|---|---|
| 3 mån（rörlig） | **3,20 %** |
| 1 år | 3,62 % |
| 2 år | 3,84 % |
| 3 år | 3,99 % |
| 4 år | 4,09 % |
| 5 år | 4,19 % |
| 7 år | 4,38 % |
| 10 år | 4,59 % |

#### 平均利率（Snittränta）— 2026-03 實際成交

| Bindningstid | Snittränta |
|---|---|
| 3 mån | **2,63 %** |
| 1 år | 2,80 % |
| 2 år | 2,88 % |
| 3 år | 3,01 % |
| 5 år | 3,38 % |
| 7 år | 3,62 % |
| 10 år | 3,81 % |

> 差距 ≈ **0,4 – 0,6 個百分點**。建模時若用 listränta 會高估成本；建議以 snittränta 為基準（代表合理客戶能議到的水準）。

#### LTV 對利率的影響（SBAB）

- SBAB 官方宣稱利率由 `listränta − rabatt(LTV, lånebelopp, energiklass)` 決定。
- 公開資料顯示 **LTV 40 – 70 % 為最優惠區間**；LTV > 75 % 折扣明顯縮水，LTV > 85 % 折扣再減。
- 未公開詳細階梯表 → 建模時可用以下粗略模型：

| LTV 區間 | 對 snittränta 的加碼（估計） |
|---|---|
| < 50 % | −0,05 ~ −0,10 pp（可再優惠） |
| 50 – 70 % | 0 pp（基準） |
| 70 – 85 % | +0,05 ~ +0,15 pp |
| 85 – 90 % | +0,15 ~ +0,30 pp |

> 以上為市場觀察近似值（對照 Landshypotek 公開表：< 60 % LTV 折 0,50 pp；60 – 75 % 折 0,40 pp）。實際建模建議做敏感度分析 ±0,25 pp。

### 3.2 Stabelo（2026-04 月份參考）

Stabelo 主打「färdigprutad ränta」—— 列表即成交價，無議價空間，因此其 listränta 已接近其他銀行的 snittränta。

| Bindningstid | 近期利率 |
|---|---|
| 3 mån（rörlig，含一般折扣） | **2,70 – 2,90 %** |
| 1 år | 2,93 % |
| 5 år | 3,50 % |
| 10 år | 4,15 % |

#### Stabelo 官方參考計算（2026-04）

- 貸款額 2 500 000 kr、**LTV 65 %**、3 mån ränta **2,71 %**、effektiv 2,74 %。
- 月本金（30 年直線） + 利息 ≈ 7 729 kr。

#### Stabelo LTV / 產品條件

| 情境 | 最高 LTV |
|---|---|
| 新購（köp） | 90 % |
| 轉貸（byta bank，不增貸） | 90 % |
| 加貸（utökning） | 80 %（呼應新規） |
| 最低貸款額 | 500 000 kr |
| 最高貸款額 | 20 000 000 kr |

#### Stabelo 折扣項目

- Energiklass A/B：**−0,10 pp**
- Grön renovering：**−0,20 pp**
- LTV 越低折扣越好，但 Stabelo 不公開完整階梯；上述 2,71 % @ 65 % LTV 為參考錨點。

### 3.3 兩家銀行對照（rörlig 3 mån，LTV = 65 % 情境）

| 銀行 | Listränta | 實際成交 ≈ |
|---|---|---|
| SBAB | 3,20 % | **2,60 – 2,70 %**（snittränta） |
| Stabelo | — | **2,70 – 2,90 %**（無議價） |

→ SBAB 對可議價的客戶偏低；Stabelo 對懶得議價的客戶簡單透明。建模時可取兩者較低值 ~2,65 % 作基準情境。

---

## 4. 利率預測（未來 10 年建模用）

市場存在兩派預測，建議同時跑：

### 4.1 Stabelo Boränteindikator（偏高）
- 3 mån snittränta 預計 2026 底 ≈ **3,8 %**
- 2028 底 ≈ **4,1 %**
- 長期中性利率假設 ≈ 4 %

### 4.2 大行共識（SBAB / Swedbank / Handelsbanken / Länsförsäkringar，偏低）
- 2026-12 三月利率區間 **2,60 – 2,70 %**
- 與 Riksbanken 寬鬆週期尾聲假設一致

### 4.3 建議建模情境

| 情境 | 3m rörlig 平均（未來 10 年） | 說明 |
|---|---|---|
| 低利率 | 2,50 % | 大行預測延伸 |
| 基準 | 3,25 % | 兩派中位 |
| 高利率 | 4,25 % | Stabelo 高位 + buffer |

> 建議以蒙地卡羅或情境樹跑這三組，觀察最優 LTV 在不同利率路徑下的變化。

---

## 5. 稅務要點（影響 insats vs. 投資決策）

### 5.1 Ränteavdrag（利息扣除）
- 年度利息支出 **≤ 100 000 kr**：**30 %** 稅額抵扣
- 超過 100 000 kr 部分：**21 %** 稅額抵扣
- 前提是有足夠 kapitalinkomst / 勞務所得可抵扣
- **實效利率** = 名目利率 × (1 − ränteavdrag%)
  - 例：3 % 名目 × (1 − 0,30) = **2,10 %** 實效（在 100k 以內區間）

### 5.2 投資替代方案（剩餘資金去處）

#### ISK / KF（2026 年新規）
- **Fribelopp：300 000 kr / 人**（ISK + KF 合併計算），以下完全免稅。
- **超額部分 effektiv skatt = 1,065 %**（2026 年；= (SLR + 1 pp) × 30 %，與舊版相比基數加了 1 pp）。
- Kapitalunderlag 公式：`(Q1 ingående + Q2 ingående + Q3 ingående + Q4 ingående + 當年度總 insättningar) / 4`。
- 雙人家庭（兩人各開一個 ISK）→ fribelopp 實際為 600 000 kr。
- 2026 年改變雖提高稅率，對 sparande ≤ ~1 Mkr 者實際稅負仍下降（fribelopp 效果）。

#### Vanlig depå / 其他帳戶
- **30 % realisationsvinstskatt**（實現時）。
- 海外 / 法人 / 親屬名下帳戶稅率依該主體課稅規則，建模時當可配置參數。
- 無 fribelopp、無 schablonskatt。

#### KF vs ISK 差別（次要）
- 稅率、fribelopp 相同。
- KF 可掛法人或家屬名下，適合遺產規劃或特定所得結構。
- v1 建模兩者等價處理。

### 5.3 建模公式（核心）

對每一 LTV 情境：

```
年度淨成本 = L × ränta × (1 − ränteavdrag%) + amorteringsrat
年度投資收益 = (insats差額 + 月結餘) × (portföljavkastning − ISK_schablonskatt)
```

最優 LTV = argmax{ 10 年末淨資產（房產 equity + 投資組合） | 現金流可持續 }

---

## 6. 利率資料源抓取可行度（建模整合用）

主流 bolån 供應商的計算器中，**只有 Stabelo 可直接用匿名 HTTP 拉到完整 LTV × 綁定期的結構化利率表**。其他家或需 BankID 登入，或僅公開聚合平均值。

### 6.1 可行度矩陣

| 供應商 | 有計算器？ | 匿名可抓？ | 顆粒度 | 實作難度 |
|---|---|---|---|---|
| **Stabelo** | ✅ iframe widget | ✅ **完全開放** | LTV × 綁定期 × EPC 的完整矩陣 | **低**（已驗證） |
| Hypoteket | ✅ 公開 | ⚠️ API 存在但需找 endpoint | LTV + 貸款額 → 利率 | 中（需 DevTools 抓包） |
| Skandia | ✅ 「無需議價」 | ⚠️ 有獨立 widget | LTV + 貸款額 → 利率 | 中（需 DevTools 抓包） |
| SBAB | ✅ 公開計算器 | 🟡 只能拉公告 list/snittränta | fixed-term 總平均 | 低（靜態頁） |
| Avanza Super Bolån | ✅ | ❌ React SPA + BankID auth | — | 高 |
| Swedbank / Nordea / SEB / Handelsbanken | ✅ 均有 | ❌ 計算器吐「可借金額/月費」，不吐 LTV-rate 函數 | fixed-term 總平均 | 低（靜態頁） |
| Danske Bank | ✅ | ❌ 同上 | fixed-term 總平均 | 低 |
| Länsförsäkringar | ✅ | ❌ 利率個別設定 | — | — |

> 結論：建模可用 **Stabelo API 作實時校準源**，大行用 **Finansvalp 聚合頁或各行利率公告頁** 作市場基準。

### 6.2 Stabelo API（已驗證端點）

**端點**
```
GET https://api.stabelo.se/rate-table.data
Accept: text/x-script
```

**特性**
- 完全公開，無需 cookie / session / CSRF / referer。
- 回傳 ~300 KB Remix turbo-stream 格式（扁平陣列 + index pointer，不是純 JSON）。
- 包含完整 `rateTable.interest_rate_items[]` 矩陣：每一項 = `{ epc_classification: "A"|"B", ltv, product_amount, rate_fixation: {months, rate_string}, ... }`。
- 涵蓋所有綁定期（3 mån、1、2、3、5、10 年）與 EPC 能源折扣檔。

**實作**（Python 範例）
```python
import httpx, re

def fetch_stabelo_rates() -> dict:
    r = httpx.get(
        "https://api.stabelo.se/rate-table.data",
        headers={"Accept": "text/x-script", "User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    r.raise_for_status()
    text = r.text
    # Parse turbo-stream: 提取 rate_fixation 條目 {360,"3,60 %"}
    items = re.findall(r'\{"_2323":(\d+),"_2311":(\d+),"_2313":\d+\}', text)
    # months_token_id, rate_string_token_id → 還需交叉查主表
    # 建議用簡易 turbo-stream parser（見下方 tooling 節）
    ...
```

> 由於 turbo-stream 是 Remix 特有格式，建議封裝 parser 獨立成一個模組。格式規範：https://github.com/jacob-ebey/turbo-stream

**建模整合建議**
1. 每天 cron 拉一次 `rate-table.data`，存成本地 parquet/jsonl。
2. 建 `stabelo_rate(ltv_pct, binding_months, epc="B") → float` 查表函數。
3. 蒙地卡羅情境以此為「當前市場基準」，對未來 10 年加利率 shock（見 §4 情境）。

### 6.3 Hypoteket（API 存在，endpoint 待確認）

- API 根：`https://api.hypoteket.com/api/v1/`（ping 有回應）。
- SSR HTML 不含具體端點；其 Vue/Nuxt SPA 在瀏覽器端組請求。
- **取得方式**：Chrome → https://www.hypoteket.com/rantor → DevTools Network → Fetch/XHR → 調整計算器參數觀察觸發的 XHR → 右鍵 Copy as cURL。
- 一旦拿到端點，結構應為 `GET /api/v1/<path>?loan=...&propertyValue=...` 回 JSON。

### 6.4 Skandia / SBAB（同 Hypoteket 路徑）

- Skandia widget JS：`mortgageInterestCalculatorBlock-CuFNmoBi.esm.js`，內含計算邏輯或 API 呼叫。
- SBAB 提到 `api.sbab.se`，公開計算器可能透過它。
- **一樣需要 DevTools 抓包** 才能拿到準確 endpoint 與 payload schema。

### 6.5 不適合抓的（大行）

Swedbank / Nordea / SEB / Handelsbanken / Danske 的公開計算器並不以 LTV 為輸入產生利率，只回覆「你可借 X、月費 Y」。它們的 LTV 折扣表是內部定價（業務員議價），沒有公開函數可抓。**建模時這幾家只能用 snittränta 聚合值當代表**。

### 6.6 抓取注意事項

- **頻率**：Stabelo 目前未見限流，但建議 ≤ 每日一次以免被識別為爬蟲。
- **變動風險**：Remix 回傳的 `_NNNN` token 編號每次部署可能變；parser 不要 hardcode，改用鍵名（`rateTable`、`interest_rate_items`、`rate_fixation`）做 lookup。
- **合規**：純讀取公開頁面的資料，依瑞典法無特別限制；但若做商業產品建議聯繫銀行取得資料授權。
- **備援**：每次抓取後保存原始回應，解析失敗可 fallback 到上次成功的快照。

---

## 7. 資料來源

### 政策與新規
- [Handelsbanken — Amorteringskrav 2026 nya regler](https://www.handelsbanken.se/sv/ekonomi-i-livet/privatekonomi/boendeekonomi/for-hushall/nya-amorteringskrav)
- [Swedbank — Nya bolåneregler 2026](https://www.swedbank.se/privat/boende-och-bolan/rakna-pa-ditt-bolan/amortering-och-amorteringskrav/nya-amorteringsregler---sa-paverkas-du.html)
- [SEB — 2026 bolåneregler](https://seb.se/privat/livet/ekonominyheter/aktuellt/nytt-forslag-om-andrat-amorteringskrav-och-bolanetak)
- [Nordea — Nya bolåneregler 2026](https://www.nordea.se/privat/produkter/bolan/nya-bolaneregler.html)
- [HSB — Nya bolåneregler från 1 april 2026](https://www.hsb.se/nyheter-och-tips/nyheter/2026/nya-bolaneregler-fran-1-april-2026--sa-paverkas-du-som-vill-kopa-bostad/)
- [SBAB — Regeringens förslag om ändrade bolåneregler](https://www.sbab.se/1/privat/tips_och_kunskap/nyheter/artiklar/2025-12-19_det_betyder_regeringens_forslag_om_andrade_bolaneregler.html)
- [Ekonomifakta — Nya bolåneregler 2026](https://www.ekonomifakta.se/sakomraden/finansiell-ekonomi/nya-bolaneregler-2026_1249330.html)
- [SVT Nyheter — Nya bolåneregler från den 1 april](https://www.svt.se/nyheter/ekonomi/nya-bolaneregler-fran-den-1-april)

### 利率與產品
- [SBAB — Bolåneräntor](https://www.sbab.se/1/privat/vara_rantor.html)
- [Stabelo — Bolåneräntor](https://www.stabelo.se/bolanerantor)
- [Stabelo — Räkneexempel](https://www.stabelo.se/rakneexempel-for-bolan)
- [Stabelo — Belåningsgrad](https://www.stabelo.se/bolaneguiden/belaningsgrad)
- [Stabelo — Boränteindikator / Prognos 2026–2028](https://www.stabelo.se/stabelos-boranteindikator)
- [Finansvalp — Listräntor bolån april 2026](https://finansvalp.se/lana-pengar/bolan/listrantor)
- [Lånekoll — SBAB aktuella bolåneräntor](https://www.lanekoll.se/bolan/sbab)
- [Ekonomifokus — Ränterabatt på bolån 2026](https://www.ekonomifokus.se/bostad/finansiera/rabatt-pa-bolan-ranterabatt)

---

## 8. 建模待辦 / 開放問題

- [ ] 確認 Stabelo 完整 LTV 階梯（目前僅有 65 % 錨點）—— 可能需直接聯繫或從申請流程反推
- [ ] 向 SBAB 取得個人化報價以校準 LTV 折扣表
- [ ] 確認 2026 年最新 **SLR**（statslåneränta）以計算 ISK schablonskatt
- [ ] 納入 **Pantbrev + lagfart** 成本（購屋一次性 ~2 % av köpeskilling，但 bostadsrätt 通常免 lagfart，只需 uppläggningsavgift，建模時應分 villa / brf）
- [ ] 考慮 **driftkostnad / avgift till föreningen** 對現金流建模的敏感度（與 LTV 選擇無關但影響絕對值）
