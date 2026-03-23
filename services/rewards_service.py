# services/rewards_service.py
import os
import pandas as pd
import logging
import sqlite3
from typing import Dict, Optional
from processors.rewards import RewardsCalculator
from loaders.config_loader import ConfigLoader

# ==========================================
# 設定日誌 (Logging)
# ==========================================
logger = logging.getLogger(__name__)

# ==========================================
# 核心路徑設定
# ==========================================
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SERVICE_DIR)

OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
DB_PATH = os.path.join(OUTPUT_DIR, 'Bills.db')
CONFIG_DIR = os.path.join(BASE_DIR, 'configs')

def run_rewards_calculation():
    """
    執行回饋計算服務：讀取資料庫 -> 載入規則 -> 計算 -> 回寫資料庫
    """
    logger.info("💰 啟動回饋計算服務...")

    # 1. 讀取交易資料
    if not os.path.exists(DB_PATH):
        logger.error(f"❌ 資料庫不存在: {DB_PATH} (請先執行 ETL)")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 讀取已清洗過的交易資料
            df_bills = pd.read_sql("SELECT * FROM all_transactions", conn)
        
        if df_bills.empty:
            logger.warning("⚠️ 資料庫中無交易資料，取消計算。")
            return

        # 2. 載入計算規則 (Configs)
        configs = {}
        if ConfigLoader:
            try:
                # 載入所有與回饋相關的配置 (雖然目前 calculator 尚未全數使用，但先備齊)
                configs = {
                    'merchants': ConfigLoader.load_config(CONFIG_DIR, 'dim_merchants', strategy='append'),
                    'cards': ConfigLoader.load_config(CONFIG_DIR, 'dim_cards', strategy='replace'),
                    'gateways': ConfigLoader.load_config(CONFIG_DIR, 'dim_payment_gateway', strategy='append'),
                    'cube_selections': ConfigLoader.load_config(CONFIG_DIR, 'bridge_cube_selections', strategy='replace'),
                    'reward_rules': ConfigLoader.load_config(CONFIG_DIR, 'bridge_reward_rules', strategy='replace'),
                    'rewards_base': ConfigLoader.load_config(CONFIG_DIR, 'dim_card_rewards_base', strategy='replace'),
                    'rewards_campaigns': ConfigLoader.load_config(CONFIG_DIR, 'dim_card_rewards_campaigns', strategy='replace')
                }
            except Exception as e:
                logger.warning(f"⚠️ 載入部分規則檔失敗 (可能尚未建立): {e}")

        # 3. 初始化計算引擎並執行
        calculator = RewardsCalculator(configs=configs)
        df_result = calculator.process(df_bills)
        
        # 4. 寫回資料庫
        with sqlite3.connect(DB_PATH) as conn:
            # 將計算結果存入獨立的資料表，避免汙染原始交易表
            df_result.to_sql('analysis_rewards', conn, if_exists='replace', index=False)
            logger.info("✅ 回饋計算完成，結果已存入資料表: analysis_rewards")
            
        # 同時輸出一個 CSV 方便檢查
        output_csv = os.path.join(OUTPUT_DIR, 'rewards_preview.csv')
        df_result.to_csv(output_csv, index=False, encoding='utf-8-sig')
        logger.info(f"📊 回饋預覽已匯出至: {output_csv}")

    except Exception as e:
        logger.error(f"❌ 回饋計算過程中發生錯誤: {e}", exc_info=True)
