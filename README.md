# 💳 Credit Card Transaction ETL Pipeline

> **Automated Financial Data Engineering**
> *From "Garbage In" to "Actionable Insights" — A Privacy-First Approach.*
> *從雜亂帳單到精準決策：一個隱私優先的自動化資料管線。*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-ETL-150458?logo=pandas&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite&logoColor=white)
![Privacy](https://img.shields.io/badge/Privacy-Local--First-green)

## 📖 專案背景 (Project Context)

在個人財務分析中，跨銀行帳單整合常面臨 **非結構化數據 (Unstructured Data)** 與 **隱私安全** 的雙重挑戰。
傳統的手動記帳或 Excel 公式維護存在以下痛點：

* **Data Consistency:** 商家名稱混亂（如 `7-ELEVEN`, `7-11`），導致消費類別難以歸戶。
* **Scalability:** 隨著帳戶增加，手動校對回饋係數與格式的時間成本呈指數級上升。
* **Privacy Risks:** 依賴雲端記帳軟體可能導致財務隱私外洩。

本專案構建了一個 **Local-First ETL Pipeline**，將原始 CSV 帳單清洗並標準化，存入本地 SQLite 資料庫以支援 **RFM 模型** 與 **回饋最佳化** 分析。

---

### 流程
   1. Extract (提取)：main.py 掃描 data/ 資料夾，利用 get_parser 自動識別銀行，透過 parsers/ 將 PDF/CSV 轉為一致的 STANDARD_COLUMNS 格式。
   2. Transform (清洗)：
       * classifier.py 根據 configs/ 中的規則自動判斷交易類型。
       * 移除支付前綴（如 LINEPAY*），還原乾淨的商家名稱以利後續分析。
   3. Load (儲存)：sqlite_loader.py 將乾淨的交易紀錄寫入 output/Bills.db。
   4. Analyze (分析)：analytics/ 模組讀取資料庫，產出：
       * 商家 RFM：哪些店是你最常去且花最多的？
       * 信用卡 RFM：哪張卡是你的主力消費卡？
       * 消費矩陣：視覺化不同時間維度的消費分佈。
       * 回饋計算：計算卡片回饋，並計算C/P值和消費難易度分析。

---

## 🛠️ 開發方法論 (Development Methodology)

本專案採用 **AI 輔助開發 (AI-Assisted Development)** 模式，結合人類架構師的邏輯與 LLM 的算力。

* **Architecture (人類主導):** 定義資料流 (Data Flow)、Schema 設計、隱私邊界與商業目標。
* **Implementation (AI 加速):** 利用 Vibe Coding 模式快速生成繁瑣的 Regex 規則與 Pandas 語法。本專案使用Gemini Pro模型生成。
* **Verification (嚴格審查):** 所有生成代碼皆經過人工 Code Review，並通過真實數據的邏輯驗證。透過提示詞要求變數命名不可任意變動。

---

## 📂 檔案結構 (File Structure)

```text
.
My-Credit-Card-ETL/
│
├── .gitignore                  #
├── README.md                   # 介紹文件
├── requirements.txt            # [環境] 專案相依套件清單
├── main.py                     # [入口點] 核心 ETL 流程控制器
├── const.py                    # [規範] 全域欄位定義與資料型態 (Single Source of Truth)
│   
├── parsers/                    # [解析層] 負責各銀行原始帳單轉為標準 DataFrame
│   ├── base.py                 # Parser 基類，定義統一介面
│   ├── cathay.py               # 國泰世華 (csv) 解析邏輯
│   ├── esun.py                 # 玉山銀行 (csv) 解析邏輯
│   ├── CTBC.py                 # 中國信託 (csv) 解析邏輯
│   ├── sinopac.py              # 永豐銀行 (PDF) 解析邏輯
│   └── hncb.py                 # 華南銀行 (格式偽裝) 解析邏輯
│
├── processors/                 # [處理層] 負責資料清洗、分類與商家對齊
│   ├── refiner.py              # 清洗總指揮，協調各子處理器
│   ├── classifier.py           # 自動標記交易類別 (一般、國外、退刷、繳款)
│   ├── merchant.py             # 商家名稱清洗與正規化
│   └── mapper.py               # 欄位對應處理
│
├── loaders/                    # [載入層] 負責資料儲存、載入設定檔資料
│   ├──sqlite_loader.py         # 將清洗後的資料匯入 SQLite (Bills.db) 
│   └──config_loader.py         # 將相關的設定資料匯入主程式執行
│
├── analytics/                  # [分析層] 負責進階數據建模
│   ├── main_rfm.py             # RFM 分析主流程
│   ├── rfm_modules.py          # RFM 計算引擎 (Merchant/Payment/Card)
│   └── rewards_calculator.py   # (設置中) 回饋金計算邏輯
│
├── configs/                        # [設定檔資料夾] 
│   ├── dim_cards.csv                   # [設定檔] 真實卡號放置地點(已在 .gitignore)
│   ├── transaction_types.yaml          # [設定檔] 銀行交易類別，排除持卡人跟銀行的交易像繳款、折抵/回饋、費用(手續費/服務費)(公開)
│   ├── dim_merchants.csv               # [設定檔] 真實交易地點，使用Regex(正則表達式)-Replacement來清洗消費明細(已在 .gitignore)
│   ├── dim_payment_gateway.csv         # [設定檔] 電子支付平台，使用Regex(正則表達式)-Replacement來整理支付通路(公開)
│   ├── dim_card_rewards_base.csv       # [設定檔] 基本回饋設定(已在 .gitignore )
│   ├── dim_card_rewards_campaigns.csv  # [設定檔] 消費活動回饋設定(已在 .gitignore)
│   ├── bridge_reward_rules.csv         # [設定檔] 基本回饋設定橋接表(已在 .gitignore)
│   └── bridge_cube_selections.csv      # [設定檔] Cube權益切換橋接表(已在 .gitignore)
│
├── data/                       # [帳單csv放置處] 真實的 CSV 帳單放這邊。
│   └── (各銀行帳單)
└── output/                     # [輸出區] 存放 Bills.db 與 分析報表 (已在 .gitignore)

```

---

## 🚀 專案路線圖與待辦 (Roadmap)

目前的開發重點在於擴充支援的銀行數量與優化 Regex 準確度。
以及各種輸入方式的改良。

### 支援銀行擴充
- [x] **玉山銀行**：已完整支援 (含 e.Point 折抵處理、多卡號歸戶邏輯)
- [x] **國泰世華**：已完整支援 (含 Cube 卡多卡號歸戶邏輯)
- [x] **中國信託**：已完整支援 
- [x] **華南銀行**：已完整支援 (含 副檔名偽裝、多卡號歸戶邏輯)
- [X] **永豐銀行**：已完整支援
- [ ] **台新銀行**：徵求 CSV 格式樣本 (Help Wanted)
- [ ] **台北富邦**：徵求 CSV 格式樣本 (Help Wanted)

## 📅 開發日記 (Dev Log)

* **2026-03-12**
   * 行為準則建立：完成 GEMINI.md，定義編碼規範、架構完整性保護，以及最核心的「核心變更驗證規範 (Refactoring Protocol)」。
   * 配置載入器實作：建立 loaders/config_loader.py，支援多重編碼嘗試 (UTF-8 → Big5 → cp950) 與 Append/Replace 讀取策略。
   * 核心架構解耦：
       * 重構 main.py：將設定檔讀取邏輯從處理器移至進入點。
       * 重構 processors/ (merchant.py, classifier.py, refiner.py)：改為注入式規則架構，不再內部讀檔。
   * 穩定性驗證：透過 A/B 測試比對 result_old.csv 與 result_new.csv，確認重構前後處理結果 100% 完全一致。

* **2026-03-07**
    * 大幅度調整專案架構，撤下Mock Data Generator (generate_mock.py) 與隱私分流架構 (Himitsu.py)。
    * 重構專案檔案命名因應調整專案架構 (parser資料夾，和資料夾內的所有檔名) 。
    * 開始撰寫回饋計算邏輯

* **2026-02-07**
    * 建立 Mock Data Generator (generate_mock.py) 與隱私分流架構 (Himitsu.py)。
    * 重構專案檔案命名 (merchants.csv, payment_gateway.csv) 以符合工程慣例。
    * RFM記錄邏輯上傳。
    * 支付規則(Regex)上傳，整理商家規則(Regex)中。

* **2026-02-02**
    * 開始分離EXCEL回饋紀錄邏輯跟跟RFM紀錄邏輯

* **2026-02-01**
    * 完成 `refine.py` 第一版。
    * 完成 自動降級機制（找不到真實檔時自動讀取範本）。

* **2026-01-28**
    * 重構了 `refine.py` 的邏輯。遇到一個 Bug：有些卡號末四碼會重複，後來決定加入「卡片名稱」作為第二鍵值來解決。
    * 新增了國泰 Cube 卡的雙號自動歸戶功能。
    * 消費明細關鍵字表(Regex)定稿

* **2026-01-20**
    * 專案初始化。完成第一版 ETL 架構 (`etl.py`)。
    * 變更資料流處理模式，從原本寫在Excel的回饋相關資料跟RFM關資料開始形成專案。

