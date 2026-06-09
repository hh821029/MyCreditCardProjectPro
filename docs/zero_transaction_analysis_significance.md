# 零消費（空資料）在信用卡行為分析中的商業價值與設計規範

本文件旨在記錄 `MyCreditCardProjectPro` 專案在時間事實維度與消費交易事實進行關聯分析時，對於「無交易月份」或「空交易資料」之商業價值探討，以及對應的系統架構設計規範。

---

## 一、 商業分析價值與背景意義

在信用卡記帳與個人財務行為分析中，某張信用卡在特定月份「無消費交易明細」（即資料庫中查無該卡在該月的事實紀錄）並非代表「無用數據」或「無分析價值」，相反地，「零消費（Zero Transaction）」在商業智慧（BI）與行為分析中具備極高價值的分析特徵：

### 1. RFM 模型中 Recency (近遲度) 的時間連續性
- **商業痛點**：若分析引擎僅以「有交易的月份」做為時間基準，當某張卡片在 `2025-01` 刷了最後一筆，隨後便處於閒置狀態，到 `2025-06` 進行分析時，如果無法選取 `2025-06` 作為基準月份，系統便無法計算出該卡片「已閒置 5 個月」這一關鍵特徵。
- **分析價值**：透過完整保留時間維度，分析模型可以精確計算出每張信用卡的閒置天數（Recency），作為使用者是否應調整卡片組合的依據。

### 2. 睡眠戶與卡片流失預警 (Dormant & Churn Detection)
- **商業概念**：
  - **流通卡 (Issued Cards)**：持有的所有卡片。
  - **有效卡 (Active Cards)**：最近 6 個月內有消費紀錄的卡。
- **分析價值**：當一張信用卡從每個月均有消費，突然過渡到「連續數個月零消費（空資料表）」，在金融分析中代表該卡已進入**「睡眠卡」**或**「流失戶」**狀態。系統可藉此識別並警示使用者：此卡是否已被冷落。

### 3. 持有成本與免年費規則控管
- **商業痛點**：許多信用卡設有「年消費需滿 N 次」或「年消費需滿 N 元」否則將被收取年費的減免條件。
- **分析價值**：透過將「零交易月份」與卡片的免年費規則相結合，系統可在卡片連續數月無交易時，主動提醒使用者該卡片存在「潛在持有成本（年費風險）」，避免因疏忽而繳納年費。

---

## 二、 系統架構與資料提取規範

為了能在分析中保留「零交易」的商業價值，本專案的資料庫查詢與引擎計算應遵循以下設計規範：

### 1. 時間事実框架的單一事實源 (SSOT)
- **時間維度**應一律自 **`TransactionConfigs.db` 的 `dim_billing_history`**（或日曆事實表）提取，而非從交易明細表 `all_transactions` 提取。
- **原因**：`dim_billing_history` 記錄了使用者持有卡片期間內的所有「帳單月份對帳歷史」，即使該月沒有消費，對帳單歷史依然存在，可作為時間框架的骨架。

### 2. 利用 Outer Join (外連接) 進行資料補齊
在進行卡片使用率、RFM 分析或回饋率計算時，SQL 查詢應以設定表/時間事實表為基準，採用 `LEFT JOIN` 連接交易明細，以確保「無交易」的卡片與月份能以 `NULL` 形式被保留：

```sql
SELECT 
    b.bank_name,
    b.card_type,
    b.statement_month,
    COALESCE(SUM(t.payment_amount), 0) AS monthly_spending,
    CASE 
        WHEN SUM(t.payment_amount) IS NULL OR SUM(t.payment_amount) = 0 THEN 'Dormant (靜止)'
        ELSE 'Active (活躍)'
    END AS card_status
FROM dim_billing_history b
LEFT JOIN all_transactions t 
    ON b.bank_name = t.bank_name 
   AND b.card_type = t.card_type 
   AND b.statement_month = t.statement_month
GROUP BY b.bank_name, b.card_type, b.statement_month;
```

### 3. 聚合計算的防呆 (Handling NULLs)
- **回饋金計算**：對於交易量為空（NULL）的月份，計算引擎應產出回饋金額為 `0` 的事實，而非直接跳過或忽略該月份，以保持分析報表的月份連續性。
- **活卡率計算**：
  $$\text{活卡率} = \frac{\text{當月有消費紀錄的卡片數量}}{\text{目前持有的總卡片數量 (來自 dim_cards)}} \times 100\%$$
  此計算分母必須依賴 `dim_cards`，而非從交易明細中去計算卡片數。
