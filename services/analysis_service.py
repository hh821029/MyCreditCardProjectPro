# services/analysis_service.py
import sqlite3
import pandas as pd
import os
import logging
from typing import Optional, List
import re
import const
from analytics import rfm_modules
import services.transaction_service as ts

# ==========================================
# 設定日誌 (Logging)
# ==========================================
logger = logging.getLogger(__name__)

# ==========================================
# rfm 分析與路徑設定 (引用自 const.py)
# ==========================================
OUTPUT_DIR = const.OUTPUT_DIR
DB_PATH = const.DB_PATH
MATRIX_DIR = os.path.join(OUTPUT_DIR, 'matrix')
CONFIG_DIR = const.CONFIG_DIR

os.makedirs(MATRIX_DIR, exist_ok=True)

RFM_WINDOWS = const.TimeWindow.to_legacy_list()

MATRIX_WINDOWS = const.TimeWindow.to_list()


# ==========================================
# 前處理函式：拔除支付前綴
# ==========================================
def clean_merchant_prefix(df: pd.DataFrame, config_dir: str) -> pd.DataFrame:
    """
    讀取 dim_payment_process.csv，將 merchant_name 欄位中的前綴詞拔除
    """
    process_file = os.path.join(config_dir, 'dim_payment_process.csv')
    if not os.path.exists(process_file):
        logger.warning(f"⚠️ 找不到 {process_file}，略過前綴拔除處理。")
        return df
        
    try:
        process_df = pd.read_csv(process_file)
        # 過濾空值並去除頭尾空白 (對應新欄位 process_prefix)
        prefixes = pd.Series(dtype=str)
        if 'process_prefix' in process_df.columns:
            series_val = process_df['process_prefix']
            if isinstance(series_val, pd.Series):
                prefixes = series_val.dropna().astype(str).str.strip()
        
        prefixes = prefixes[prefixes != '']
        
        if isinstance(prefixes, pd.Series):
            if prefixes.empty:
                return df
                
            # 組裝 Regex (使用 re.escape 保護特殊字元)
            escaped_prefixes = [re.escape(str(p)) for p in prefixes]
            pattern = r'^(' + r'|'.join(escaped_prefixes) + r')'
            
            # 執行 Regex 替換並去除可能留下的空白
            df['merchant_display'] = df['merchant_display'].str.replace(pattern, '', regex=True).str.strip()
            logger.info("🧹 已成功拔除 merchant_display 中的支付/處理前綴詞。")
        
    except Exception as e:
        logger.error(f"❌ 拔除商家前綴詞失敗: {e}", exc_info=True)
        
    return df


def run_analytics(
    banks: Optional[List[str]] = None,
    cards: Optional[List[str]] = None,
    payments: Optional[List[str]] = None,
    time_window: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location: Optional[str] = None
):
    logger.info("🚀 [Analytics Pipeline] 開始執行全方位 RFM 分析...")

    # 若有傳入任何篩選條件，採用動態 SQL 查詢；否則使用預設之全歷史
    if any([banks, cards, payments, time_window, start_date, end_date, location]):
        logger.info("⚙️ 偵測到篩選參數，將採用動態 SQL 篩選交易資料進行分析...")
        df_raw = ts.query_transactions_modular(
            banks=banks,
            cards=cards,
            payments=payments,
            time_window=time_window,
            start_date=start_date,
            end_date=end_date,
            location=location
        )
    else:
        df_raw = ts.get_transactions(window=const.TimeWindow.LIFETIME)

    if df_raw.empty:
        logger.error("❌ 資料庫無資料，終止程序。")
        return

    # 基礎型態轉換
    df_raw['transaction_date'] = pd.to_datetime(df_raw['transaction_date'])
    amount_series = pd.to_numeric(df_raw['payment_amount'], errors='coerce')
    if isinstance(amount_series, pd.Series):
        df_raw['payment_amount'] = amount_series.fillna(0)
    else:
        df_raw['payment_amount'] = pd.Series(amount_series).fillna(0)
    
    # [關鍵安插點]：在進行 Category Mapping 之前，先還原乾淨的商家名稱
    df_raw = clean_merchant_prefix(df_raw, CONFIG_DIR)

    # [動態補回 Category] 
    merchants_config_path = os.path.join(CONFIG_DIR, 'dim_merchants.csv')
    if os.path.exists(merchants_config_path):
        df_merchants = pd.read_csv(merchants_config_path, dtype=str)
        # 修正：使用 snake_case 的 'merchant_display' 與 'category'
        category_map = dict(zip(df_merchants['merchant_display'], df_merchants['category']))
        df_raw['category'] = df_raw['merchant_display'].map(category_map).fillna('未分類')
    else:
        logger.warning("⚠️ 找不到 dim_merchants.csv，所有交易將標記為 '未分類'")
        df_raw['category'] = '未分類'

    logger.info(f"✅ 成功載入 {len(df_raw)} 筆交易資料，並已動態掛載分類。")

    # ==========================================
    # 3. 分發與計算 (Transform)
    # ==========================================
    logger.info("⚙️ 執行各分析模組...")
    
    # A. 商家 RFM
    df_merchant = rfm_modules.calculate_merchant_rfm(df_raw, RFM_WINDOWS)
    logger.info(f"   -> Merchant RFM: {len(df_merchant)} 筆商家")
    
    # B. 支付 RFM
    df_payment = rfm_modules.calculate_payment_rfm(df_raw, RFM_WINDOWS)
    logger.info(f"   -> Payment RFM: {len(df_payment)} 種支付方式")
    
    # C. 信用卡 RFM
    df_card = rfm_modules.calculate_card_rfm(df_raw, RFM_WINDOWS)
    logger.info(f"   -> Card RFM: {len(df_card)} 張信用卡")
    
    # D. 消費矩陣 (CSV Report)
    matrix_results = rfm_modules.generate_spending_matrix(df_raw, MATRIX_WINDOWS)
    logger.info(f"   -> Matrix: 產出 {len(matrix_results)} 份消費矩陣報表")

    # ==========================================
    # 4. 寫入結果 (Load)
    # ==========================================
    logger.info("💾 儲存分析結果...")
    
    try:
        # 僅產出 Matrix CSVs 報表，不再回灌資料庫 (遵循變更方向)
        for filename, df_matrix in matrix_results:
            csv_path = os.path.join(MATRIX_DIR, filename)
            df_matrix.round(2).to_csv(csv_path, encoding='utf-8-sig')
            logger.info(f"   ✅ [CSV] 報表已儲存: {csv_path}")
            
    except Exception as e:
        logger.error(f"❌ 寫入過程發生錯誤: {e}", exc_info=True)


