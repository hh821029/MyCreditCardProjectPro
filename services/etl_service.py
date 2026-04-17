import os
import pandas as pd
import logging
from typing import List, Optional

# 1. 引入核心配置
import const

# 2. 引入各家銀行的 Parser
try:
    from parsers.sinopac import SinopacBillParser
    from parsers.esun import EsunParser
    from parsers.cathay import CubeParser
    from parsers.CTBC import CTBCParser
    from parsers.hncb import HNCBParser
except ImportError as e:
    logging.error(f"⚠️ 模組載入不完全: {e}")

# 3. 引入清洗處理器
try:
    from processors.refiner import DataRefiner
except ImportError:
    logging.warning("⚠️ 尚未建立 processors.refiner，將跳過清洗步驟")
    DataRefiner = None

# 4. 引入資料庫載入器
try:
    from loaders.sqlite_loader import SQLiteLoader
except ImportError:
    logging.warning("⚠️ 尚未建立 loaders.sqlite_loader，將跳過資料庫載入步驟")
    SQLiteLoader = None

# 5. [新加入] 引入配置載入器
try:
    from loaders.config_loader import ConfigLoader
except ImportError:
    logging.warning("⚠️ 尚未建立 loaders.config_loader，Config 載入將維持舊邏輯")
    ConfigLoader = None


# ==========================================
# 設定日誌 (Logging)
# ==========================================
# 在服務層中，我們不直接呼叫 basicConfig，因為這應該由調用者（main.py 或 api server）決定
logger = logging.getLogger(__name__)

# ==========================================
# 核心路徑設定 (引用自 const.py)
# ==========================================
DATA_DIR = const.DATA_DIR          # 輸入區
OUTPUT_DIR = const.OUTPUT_DIR      # 輸出區
CONFIG_DIR = const.CONFIG_DIR      # 規則設定檔區

# 確保輸出目錄存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# Factory: Parser 分派邏輯
# ==========================================
def get_parser(filename: str):
    """
    根據檔名特徵，回傳對應的 Parser 實例
    """
    filename_lower = filename.lower()
    
    # 1. 永豐 (PDF)
    if '永豐' in filename_lower or 'daway' in filename_lower:
        if filename_lower.endswith('.pdf'):
            return SinopacBillParser()
            
    # 2. 玉山 (CSV)
    if '玉山' in filename_lower and filename_lower.endswith('.csv'):
        return EsunParser()

    # 3. 國泰 (CSV)
    if ('國泰' in filename_lower or 'cube' in filename_lower) and filename_lower.endswith('.csv'):
        return CubeParser()

    # 4. 中信 (CSV)
    if ('中國信託' in filename_lower or 'ctbc' in filename_lower) and filename_lower.endswith('.csv'):
        return CTBCParser()

    # 5. 華南 (HTML/XLS)
    if '華南' in filename_lower and (filename_lower.endswith('.xls') or filename_lower.endswith('.html')):
        return HNCBParser()

    return None

# ==========================================
# 異常處理與診斷 (Anomaly Reporting)
# ==========================================
def save_anomaly_report(df: pd.DataFrame, filename: str, message: str):
    """
    將異常或未定義的交易資料匯出至 output 資料夾，供使用者檢查。
    """
    try:
        if df is None or df.empty:
            return
        
        report_path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(report_path, index=False, encoding='utf-8-sig')
        logger.warning(f"⚠️ {message}，已將診斷資料匯出至: {report_path}")
    except Exception as e:
        logger.error(f"❌ 無法匯出異常報告: {e}")

# ==========================================
# 主流程 (ETL Controller)
# ==========================================
def run_etl_pipeline():
    logger.info("🚀 ETL 流程啟動...")
    
    all_raw_dfs: List[pd.DataFrame] = []
    
    # --- STEP 1: Extract (讀取與解析) ---
    try:
        if not os.path.exists(DATA_DIR):
            logger.error(f"❌ 找不到資料目錄: {DATA_DIR}")
            return

        files = [f for f in os.listdir(DATA_DIR) if not f.startswith('.')]
        logger.info(f"📂 掃描到 {len(files)} 個檔案")

        for filename in files:
            filepath = os.path.join(DATA_DIR, filename)
            parser = get_parser(filename)
            
            if parser:
                try:
                    logger.info(f"處理中: {filename} ...")
                    df = parser.parse(filepath)
                    if not df.empty:
                        all_raw_dfs.append(df)
                    else:
                        logger.warning(f"  ⚠️ 解析成功但無資料: {filename}")
                except Exception as e:
                    logger.error(f"  ❌ 解析失敗 {filename}: {str(e)}")
            else:
                logger.debug(f"  ⏭️ 跳過不支援或未定義 Parser 的檔案: {filename}")

        if not all_raw_dfs:
            logger.warning("🚫 本次執行未取得任何有效資料，流程結束。")
            return

        merged_df = pd.concat(all_raw_dfs, ignore_index=True)
        logger.info(f"🔗 合併完成，共 {len(merged_df)} 筆原始資料")

        # --- STEP 3: Transform (清洗與商業邏輯) ---
        final_df = merged_df
        
        if DataRefiner:
            try:
                logger.info("🔧 啟動 Refiner 進行商業邏輯清洗...")
                if ConfigLoader:
                    configs = {
                        'merchants': ConfigLoader.load_config(CONFIG_DIR, 'dim_merchants', strategy='append'),
                        'cards': ConfigLoader.load_config(CONFIG_DIR, 'dim_cards', strategy='replace'),
                        'gateways': ConfigLoader.load_config(CONFIG_DIR, 'dim_payment_gateway', strategy='append'),
                        'txn_types': ConfigLoader.load_yaml(CONFIG_DIR, 'transaction_types.yaml')
                    }
                    refiner = DataRefiner(config_dir=CONFIG_DIR, configs=configs)
                else:
                    refiner = DataRefiner(config_dir=CONFIG_DIR)
                
                final_df = refiner.process(merged_df)
                
                # [關鍵檢查]：找出「未分類」或「未定義」的異常資料
                # 假設 Transaction_Type 為 '未分類' 或是卡片映射失敗
                if 'transaction_type' in final_df.columns:
                    anomalies = final_df[final_df['transaction_type'].isin(['未分類', 'Unknown', '', None])]
                    if not anomalies.empty:
                        save_anomaly_report(anomalies, 'anomaly_uncategorized.csv', f"發現 {len(anomalies)} 筆未分類交易")

                logger.info("✨ 資料清洗完成")
            except Exception as e:
                logger.error(f"❌ Refiner 清洗過程發生嚴重錯誤: {e}")
                save_anomaly_report(merged_df, 'crash_dump_refiner.csv', "清洗過程發生崩潰，已備份原始合併資料")
                final_df = merged_df
        
        # --- STEP 4: Filter & Sort (最終整理) ---
        available_cols = [c for c in const.STANDARD_COLUMNS if c in final_df.columns]
        final_df = final_df[available_cols]
        
        if const.COL_TXN_DATE in final_df.columns:
            try:
                final_df = final_df.sort_values(by=const.COL_TXN_DATE)
            except Exception as e:
                logger.error(f"❌ 排序失敗: {e}")

        # --- STEP 5: Load (存檔) & 寫入資料庫 ---
        csv_output_path = os.path.join(OUTPUT_DIR, 'result_final.csv')
        final_df.to_csv(csv_output_path, index=False, encoding='utf-8-sig')
        logger.info(f"✅ 清洗完成，已輸出至 {csv_output_path}")

        logger.info("📦 準備載入資料庫...")
        loader = SQLiteLoader(output_dir=OUTPUT_DIR)
        loader.load(final_df, mode='replace')
        
    except Exception as e:
        logger.error(f"🚨 ETL 流程發生未預期嚴重錯誤: {e}")
        # 全域崩潰時，嘗試拯救已合併的資料
        if 'merged_df' in locals():
            save_anomaly_report(merged_df, 'crash_dump_global.csv', "全域流程崩潰，已嘗試救援資料")
