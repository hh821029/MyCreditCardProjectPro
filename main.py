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
    print(f"⚠️ 模組載入不完全: {e}")

# 3. 引入清洗處理器
try:
    from processors.refiner import DataRefiner
except ImportError:
    print("⚠️ 尚未建立 processors.refiner，將跳過清洗步驟")
    DataRefiner = None

# 4. 引入資料庫載入器
try:
    from loaders.sqlite_loader import SQLiteLoader
except ImportError:
    print("⚠️ 尚未建立 loaders.sqlite_loader，將跳過資料庫載入步驟")
    SQLiteLoader = None


# ==========================================
# 設定日誌 (Logging)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# 核心路徑設定
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')          # 輸入區
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')      # 輸出區
CONFIG_DIR = os.path.join(BASE_DIR, 'configs')     # 規則設定檔區

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
# 主流程 (ETL Controller)
# ==========================================
def run_etl_pipeline():
    logger.info("🚀 ETL 流程啟動...")
    
    all_raw_dfs: List[pd.DataFrame] = []
    
    # --- STEP 1: Extract (讀取與解析) ---
    if not os.path.exists(DATA_DIR):
        logger.error(f"❌ 找不到資料目錄: {DATA_DIR}")
        return

    files = [f for f in os.listdir(DATA_DIR) if not f.startswith('.')]
    logger.info(f"📂 掃描到 {len(files)} 個檔案")

    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        
        # 取得對應的 Parser
        parser = get_parser(filename)
        
        if parser:
            try:
                logger.info(f"處理中: {filename} ...")
                # 執行解析 (Parser 內部會參照 const.py 進行欄位映射)
                df = parser.parse(filepath)
                
                if not df.empty:
                    logger.info(f"  ✅ 成功解析 {len(df)} 筆交易")
                    all_raw_dfs.append(df)
                else:
                    logger.warning(f"  ⚠️ 解析成功但無資料: {filename}")
            except Exception as e:
                logger.error(f"  ❌ 解析失敗 {filename}: {str(e)}")
        else:
            logger.debug(f"  ⏭️ 跳過不支援或未定義 Parser 的檔案: {filename}")

    # --- STEP 2: Merge (合併) ---
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
            # 初始化 Refiner (傳入設定檔路徑)
            refiner = DataRefiner(config_dir=CONFIG_DIR)
            
            # 執行清洗
            final_df = refiner.process(merged_df)
            logger.info("✨ 資料清洗完成")
        except Exception as e:
            logger.error(f"❌ Refiner 清洗過程發生錯誤: {e}")
            # 發生錯誤時，至少保留原始合併資料
            final_df = merged_df
    
    # --- STEP 4: Filter & Sort (最終整理) ---
    # 只保留 const 定義的標準欄位
    available_cols = [c for c in const.STANDARD_COLUMNS if c in final_df.columns]
    final_df = final_df[available_cols]
    
    # 依照交易日排序
    if const.COL_TXN_DATE in final_df.columns:
        try:
            final_df = final_df.sort_values(by=const.COL_TXN_DATE)
        except TypeError as e:
            logger.error(f"❌ 排序失敗，可能有 Parser 沒有正確轉型日期: {e}")

    # --- STEP 5: Load (存檔) & 寫入資料庫---

    try:
        csv_output_path = os.path.join(OUTPUT_DIR, 'result_final.csv')
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        final_df.to_csv(csv_output_path, index=False, encoding='utf-8-sig')
        logger.info(f"✅ 清洗完成，已輸出至 {csv_output_path}")

 
        logger.info("📦 準備載入資料庫...")
        loader = SQLiteLoader(output_dir=OUTPUT_DIR)
        loader.load(final_df, mode='replace') # 使用 replace 模式覆蓋
    except Exception as e:
        logger.error(f"❌ 存檔失敗: {e}")

if __name__ == "__main__":
    run_etl_pipeline()