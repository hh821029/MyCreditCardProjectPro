# 信用卡記帳專案資料庫架構與未來擴充規劃 (Database Architecture & Expansion Roadmap)

本文件旨在說明 `MyCreditCardProjectPro` 專案當前的「多 SQLite 獨立資料庫架構」設計決策、背後的技術考量、目前的架構限制，以及未來的異質資料庫（MySQL/PostgreSQL）擴充與遷移方案。

---

## 1. 當前架構：多 SQLite 獨立資料庫設計 (Multi-SQLite Architecture)

目前專案採用了「**三庫獨立、職責分離**」的架構，將資料依據業務屬性拆分到三個不同的 SQLite 實體檔案中（定義於 `const.py`）：

```mermaid
graph TD
    subgraph "資料庫層 (SQLite Files)"
        A[(TransactionsBills.db)]
        B[(TransactionsConfigs.db)]
        C[(TransactionsAnalysis.db)]
    end

    subgraph "業務邏輯與服務層"
        T[transaction_service.py] -->|讀取交易明細| A
        C_S[config_service.py] -->|載入回饋設定| B
        R_S[rewards_service.py] -->|呼叫| C_S
        R_S -->|呼叫| T
        R_S -->|執行計算並寫入結果| C
    end
```

### 為什麼選擇這個設計？（設計考量）
1. **開發者最熟悉、上手成本最低 (Developer Familiarity)**：
   * 這是最重要的原因。在軟體開發中，選用開發者最熟悉且最具信心的技術（SQLite），能確保開發資源專注在複雜的「回饋計算引擎（瀑布流優先級匹配）」業務邏輯上，避免在初期被資料庫的維運、連線池配置、網絡延遲等非核心工程分心。
2. **零配置、攜帶方便 (Zero-Configuration & Portability)**：
   * SQLite 無需啟動 any 背景服務（Service）或伺服器（Daemon），資料庫就是一個簡單的本機檔案。整個專案目錄打包即可在任何安裝有 Python 的環境直接運作。
3. **本機讀寫極速 (High Performance Local I/O)**：
   * SQLite 本質上是 C 語言庫，讀寫直接在本機硬碟與記憶體間進行，免去了 TCP/IP 網路通訊的開銷，在執行批量資料讀取時，其速度通常高於 MySQL。
4. **極佳的業務解耦 (Business Decoupling)**：
   * 交易流水、回饋設定與計算結果被切分到獨立的 `.db` 檔案中，可以避免單一資料庫檔案過大。同時，若未來設定檔有 Schema 異動，完全不會污染或干擾交易明細的主表。

---

## 2. 當前架構的技術限制 (Current Limitations & Constraints)

在享受 SQLite 輕量優勢的同時，我們也必須正視以下伴隨而來的技術限制（這些將會是未來系統升級的驅動力）：

### 1️⃣ 連線生命週期管理的複雜度
* **限制**：因為三個資料庫是獨立的檔案，我們無法用一個全域的資料庫 Connection 同時存取三個庫（除非使用複雜的 `ATTACH` 掛載）。
* **對應方案**：我們在 Service 層採用了「**局部即開即關 (with sqlite3.connect)**」的無狀態設計。這符合 SQLite 輕量的本質（開關微秒級），但在跨庫寫入出錯時，無法進行原生資料庫層面的分散式交易復原（Distributed Rollback）。

### 2️⃣ 併發寫入限制 (Concurrency Limit)
* **限制**：SQLite 採用的是「檔案級鎖（File-level Lock）」。雖然支援無數個 client 同時進行讀取（Shared Lock），但在同一時間**只能有一個 process 進行寫入**（Exclusive Lock）。
* **場景影響**：當專案目前是單機 CLI 或單一 Web 控制台使用時沒有問題。但如果未來演進為多人同時在線上網頁版記帳，併發寫入將會頻繁遭遇 `database is locked` 的衝突。

### 3️⃣ 類型系統的缺失 (Loose Typing System)
* **限制**：SQLite 缺乏原生的「日期（Date/Timestamp）」與「布林值（Boolean）」類型，通常會以 `TEXT` (字串) 或 `INTEGER` 儲存。
* **場景影響**：這導致資料讀出後，如果沒有經過 Enforcer 強制轉型（例如轉為 `datetime64[ns]`），計算引擎在進行日期交集或區間比對時就會崩潰。

---

## 3. 未來擴充與升級路線圖 (Future Scaling Roadmap)

當系統未來需要升級為多人協同、高併發寫入、或是需要有行動端 App 遠端同步時，我們可以採取以下兩條漸進式的升級路線：

### 🚀 路線 A：全量遷移至雲端關係型資料庫 (MySQL / PostgreSQL)
當系統朝向「多人線上 Web 記帳系統」發展時，最徹底的作法是將這三個獨立的 SQLite 資料庫合併，並遷移至單一的雲端 MySQL / PostgreSQL 資料庫中。

```mermaid
graph TD
    subgraph "本機開發/輕量版 (SQLite)"
        S1[(Bills.db)]
        S2[(Configs.db)]
        S3[(Analysis.db)]
    end

    subgraph "雲端/多人線上版 (Single MySQL)"
        M[(MySQL Database)]
        M_B[Table: transactions]
        M_C[Table: bridge_reward_rules / dim_rewards]
        M_A[Table: analysis_rewards]
    end

    S1 -->|遷移/ETL| M_B
    S2 -->|遷移/ETL| M_C
    S3 -->|遷移/ETL| M_A
```

#### 遷移的技術優勢：
1. **行級鎖 (Row-level Locking)**：MySQL 支援高度併發的寫入，多人同時記帳也不會發生資料庫鎖死。
2. **原生日期與布林值支援**：在定義 Schema 時，可以直接指定 `DATETIME` 與 `BOOLEAN` 欄位，讀出後 Pandas 會自動識別為正確類型，完全消除了「型態轉換防護」的安全隱憂。
3. **單一連線共享**：遷移到單一資料庫後，不同的資料表（交易、設定、分析）皆可共享同一個資料庫連線（Connection），可以使用標準的 `JOIN` 進行跨表查詢，甚至可以使用資料庫交易（Transaction）來確保計算寫入的 ACID 原子性。

#### 遷移實作範例 (使用 Python 順暢過渡)：
因為我們的程式碼完全使用 `pandas` 作為中介，未來遷移時，Service 層的程式碼變動極小：

```python
# 僅需將 Connection 替換為 MySQL Engine，其餘的 pandas 邏輯 100% 保持不變！
from sqlalchemy import create_engine

# 舊的 SQLite 讀取：
# import sqlite3
# conn = sqlite3.connect("TransactionsConfigs.db")
# df = pd.read_sql("SELECT * FROM bridge_reward_rules", conn)

# 新的 MySQL 讀取：
engine = create_engine("mysql+pymysql://user:password@cloud-server:3306/credit_card_system")
df = pd.read_sql("SELECT * FROM bridge_reward_rules", engine)
```

---

### 🚀 路線 B：異質資料庫混用模式 (SQLite 本機快取 + MySQL 雲端同步)
如果想保留 SQLite 本機計算的超高速度與「離線記帳可用性」，又需要雲端的協同能力，可以採用此架構：

1. **雲端 MySQL**：做為「唯一事實來源（Single Source of Truth, SSOT）」，儲存所有使用者的流水帳。
2. **本機 SQLite**：做為「局部快取（Local Cache）與個人化設定」。
3. **交互機制**：每次啟動回饋計算前，Python 腳本會先向 MySQL 伺服器發送增量請求（Incremental Request），將最新的交易流水「拉取（Pull）」並快取至本機 SQLite 的 `TransactionsBills.db`。隨後，所有運算完全在本機 SQLite 中離線執行，計算完畢後再將分析結果非同步同步回雲端。

---

## 4. 結語：尊重現狀、為未來留白

「**熟悉自己使用的工具，是寫出高品質代碼的第一步。**」

現階段堅持使用 SQLite 是極其明智且實用的工程決策。這不僅能大幅縮短您的開發週期，還能消除繁瑣的環境建置成本。

這份架構規劃檔案將作為本專案的「未來備忘錄」。我們在目前的 Python 程式碼撰寫中，將會**嚴格保持 Service 服務層的介面純粹性與 pandas DataFrame 的中介資料流設計**。這樣，不論未來是明天還是兩年後，當您決定要擁抱 MySQL 時，只需將連線部分替換，即可在幾分鐘內完成整套系統的無縫遷移與擴充！
