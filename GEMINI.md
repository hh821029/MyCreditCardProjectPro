# MyCreditCardProjectPro 專案執行指令集 (GEMINI.md)

## 1. 編碼處理規範 (Encoding)
- **讀取階段**：處理台灣銀行之 CSV 或 PDF 匯出檔時，依序嘗試使用`UTF-8`→`Big5`→`cp950` 編碼，並在讀取到亂碼時更換指定的編碼。
- **寫入階段**：所有輸出的結果檔案（CSV、JSON 等）與專案內的設定檔更新，統一使用 `UTF-8` 編碼（含 BOM 或不含，視具體需求而定，預設不含）。

## 2. 架構維護與資料流程原則 (Architectural Integrity)
- **服務化架構 (Service-Oriented)**：核心邏輯應封裝於 `services/` 資料夾中（如 `etl_service.py`, `analysis_service.py`），以供 CLI 與 API 共同呼叫。
- **禁止隨意變更資料流程**：維持現有 `main.py` -> `etl_service` -> `processors/` 之間的調用邏輯。
- **變數命名保護**：變數命名時應注意後續處理的一致性。
- **特定邏輯保護**：嚴禁將 `etl_service.py` 中與 `refiner.py` 相關的處理程式碼移除或重構至其他模組。
- **檔案編碼設定**：所有附檔名是.py跟特定資料夾(如output、configs)內的csv檔案，編碼均使用 `UTF-8` 編碼（預設不含BOM）。

## 3. 當前執行重點 (In-Progress Tasks)
- **簡易前端控制台已建置**：
    - 使用者可透過 `python -m api.server` 啟動 Web 介面。
    - 前端位於 `web/index.html`，後端 API 位於 `api/server.py`。
- **職責分離優化**：
    - `main.py` 與 `analytics/run_rfm.py` 已轉化為呼叫 `services/` 層的薄包裝。



## 4. Git 操作前置檢查 (Git Push Checklist)
- [ ] 檢查編碼：確保沒有意外將 `UTF-8` 的設定檔轉存為其他編碼。
- [ ] 驗證設定：確保 `configs/` 內的規則檔在分離後仍能被正確讀取。
- [ ] 流程測試：執行 `main.py` 確保 `refiner` 邏輯運作正常且未被破壞。
- [ ] 排除敏感資訊：確保 `data/` 或 `output/` 目錄下的個人帳單資訊未被列入 stage。
    - 注意：`configs/` 目錄下包含個人資料的檔案（如 `dim_cards.csv`）應已被 `.gitignore` 排除，請再次確認。

## 5. 待辦與待改善項目 (Backlog)
- [ ] 整理日後待更新的解析器 (Parsers) 清單。
- [ ] 優化 `analytics/` 模組中的獎勵計算邏輯。
- [ ] 建立自動化單元測試以覆蓋 `Append/Replace` 讀取邏輯。
- [ ] 簡易的前端頁面設置
- [ ] 資料夾架構調整成符合前後端的流程設置。
- [ ] main.py 本身承載了過多的職責（包含環境設定、資料流程控制與最終寫入），因應前端介面設置的需求需要切割。
- [ ] analytics/run_rfm.py 既是工具也是執行腳本，需要切分相關職責到對應的腳本。

## 6. 核心變更驗證規範 (Refactoring Protocol)
針對影響資料處理流程（Data Pipeline）的核心更動（如：重構、配置分離、Parser 邏輯更新），必須遵循以下「雙軌驗證」流程：
1. **並行實作**：新邏輯應先以「註解狀態」加入 `main.py` 或核心模組，保持舊邏輯為 Active。
2. **基準測試 (Baseline)**：執行舊邏輯，記錄或備份輸出結果（如 `result_old.csv`）。
3. **對比測試 (Comparison)**：交換註解狀態，讓新邏輯 Activebing 並執行，記錄結果（如 `result_new.csv`）。
4. **內容比對**：使用比對工具（如 PowerShell `Compare-Object` 或內容雜湊值）確認兩份結果是否 100% 完全相同。
5. **決策原則**：
    - **完全一致**：正式移除舊邏輯與註解，完成變更。
    - **不一致**：重複進行修正與比對測試。
    - **中斷討論**：若嘗試 **3-5 次** 後仍無法達成完全一致，必須立即停止操作，保留現狀並回報問題進行討論。


## 7. README.md規範 (README.md)
1. **修改權限**：整個README.md的修改要事先詢問，並且僅提供文字跟修改建議。

