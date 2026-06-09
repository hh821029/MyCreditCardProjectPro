# SQL 查詢最佳實踐：事實表與維度表的使用時機與 WHERE 條件規劃 (SQL Query Best Practices & Fact-Dimension Query Planning)

在專案資料庫由本機 CSV 轉為 SQLite 關係型資料庫的過程中，如何妥善地撰寫 SQL 查詢（特別是 `SELECT *` 與 `WHERE` 條件的取捨）對於系統的效能、記憶體佔用以及未來的 Web API 擴充具有決定性的影響。

本文件旨在說明**交易事實表（Fact Table）**與**維度/規則表（Dimension Table）**在查詢設計上的根本差異、當前開發階段的折衷設計，以及未來網頁前端介面接入後，如何優雅地過渡至參數化條件查詢。

---

## 1. 交易事實表 vs 維度設定表：查詢策略的本質差異

在關係型資料庫架構中，我們的資料表可以清楚分為兩大類，它們的資料增長速度與查詢目的截然不同：

### 📊 交易事實表 (Fact Table)
* **代表資料表**：`all_transactions`（原始交易事實明細）
* **資料特性**：
  * **持續且快速增長**：每一次消費、每一筆對帳單匯入，都會持續寫入事實表，資料量沒有上限。
  * **體積龐大**：使用幾年後，事實表可能積累數萬至數百萬筆紀錄。
* **查詢最佳實踐 (Mandatory Rules)**：
  * **❌ 嚴禁在生產環境使用無條件 `SELECT *`**：無條件讀取整張事實表會導致資料表溢出（Out of Memory）、網路頻寬阻塞以及資料庫磁碟 I/O 飆升。
  * **✅ 必須搭配限制條件 (`WHERE`) 與分頁 (`LIMIT`)**：查詢時必須根據「時間區間 (Date Range)」、「特定卡片 (Card Type)」或「使用者 ID」等維度進行嚴格篩選。

### ⚙️ 維度設定與規則表 (Dimension Table)
* **代表資料表**：`dim_cards`、`bridge_reward_rules`、`bridge_cube_selections` 等
* **資料特性**：
  * **資料量極小且相對靜態**：這類表主要存放「卡片基礎資訊」、「回饋計畫定義」與「瀑布式回饋匹配規則」。除非發行新卡或銀行更改權益，否則資料不會增加。
  * **通常在幾十筆到幾百筆以內**。
* **查詢最佳實踐 (Best Practices)**：
  * **✅ 允許並推薦使用 `SELECT *` 全量載入**：由於維度表體積非常小，全量讀入記憶體（作為 Python Pandas DataFrame 快取）能極大地簡化瀑布流規則引擎的運算邏輯，避免在迴圈中頻繁查詢資料庫，效能反而更好。

---

## 2. 當前開發階段的設計折衷 (Current Development Stage)

> [!NOTE]
> **為什麼我們目前在事實表查詢中依然看到了 `SELECT *`？**
> 
> 目前專案的 `transaction_service.py` 內在提取事實表時，暫時使用了無條件的 `SELECT *`。這是一個**開發階段的故意折衷（Trade-off）**：
> 1. **尚未與前端 API 聯動**：當前網頁控制台（位於 `web/index.html` 與 `api/server.py`）仍在建置階段，尚未正式將使用者的篩選輸入（例如：特定的日期區間、特定的消費地點）封裝成參數傳入後端服務。
> 2. **本機偵錯便利性**：在瀑布流回饋引擎（Rewards Engine）開發與精確度對照期間，全量讀出交易明細，有助於完整產出「對照除錯表（`reward_calculation_detailed.csv`）」，以驗證新舊邏輯是否 100% 完全一致。

此折衷在**單機本機開發（開發者資料量少於萬筆）**時是安全的，但必須在網頁端正式上線前被替換掉，以防止生產環境溢出。

---

## 3. 未來與網頁前端聯動後的參數化 WHERE 條件規劃 (Transition Roadmap)

伴隨著前端控制台的功能擴充，當使用者在網頁介面選擇了「查詢起迄日期」、「消費地點」或「特定卡片」並點擊「執行計算」時，後端服務必須立即從 `SELECT *` 更改為動態 `WHERE` 條件查詢。

### 🛠️ 技術實作對照 (Before vs. After)

#### 舊有的全量載入邏輯（僅適用於開發期）：
```python
# 缺點：將全量資料一次性塞入記憶體，極易隨時間推移崩潰
def get_transactions_legacy():
    conn = sqlite3.connect("TransactionsBills.db")
    df = pd.read_sql_query("SELECT * FROM all_transactions", conn)
    conn.close()
    return df
```

#### 新的動態參數化查詢設計（Web 聯動期）：
```python
def get_transactions_templated(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    card_type: Optional[str] = None,
    merchant_location: Optional[str] = None
) -> pd.DataFrame:
    """
    依據前端傳入的變數，動態產生 SQL WHERE 條件，防止資料溢出與 SQL Injection
    """
    import sqlite3
    import pandas as pd
    
    query = "SELECT * FROM all_transactions WHERE 1=1"
    params = []
    
    # 1. 動態拼接時間條件
    if start_date:
        query += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= ?"
        params.append(end_date)
        
    # 2. 動態拼接特定卡片條件
    if card_type and card_type.strip() != "":
        query += " AND card_type = ?"
        params.append(card_type)
        
    # 3. 動態拼接消費地點條件
    if merchant_location and merchant_location.strip() != "":
        query += " AND merchant_location = ?"
        params.append(merchant_location)
        
    # 執行安全查詢
    with sqlite3.connect("TransactionsBills.db") as conn:
        df = pd.read_sql_query(query, conn, params=params)
        
    return df
```

> [!WARNING]
> **安全與防毒警示 (SQL Injection Prevention)**：
> 拼接 SQL 條件時，**絕對不能**直接使用 Python 的字串格式化（如 `f"AND card_type = '{card_type}'"`）。
> 這會帶來極其嚴重的 SQL 注入漏洞。我們必須統一使用預編譯預留位置 `?`（在 PostgreSQL/MySQL 中為 `%s`），並將變數以元組（Tuple/List）形式傳入 `params` 參數中，由 SQLite 底層進行防禦性轉義。

---

## 4. 結語與文件維護建議

本設計準則將作為專案後續重構事實表查詢時的 SSOT（單一事實來源）。在進行前端與後端資料結構改善（Backlog 已列項目）時，應以此設計模式為範本，將過濾參數從網頁前端路由（API Endpoints）一路向下傳遞至 `transaction_service.py` 與 `config_service.py` 的資料提取端，確保整個 Data Pipeline 具備生產環境等級的穩定性與極佳的效能表現。
