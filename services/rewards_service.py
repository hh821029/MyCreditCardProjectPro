# services/rewards_service.py
import os
import pandas as pd
import logging
import sqlite3
import const
from typing import Dict, Optional
from processors.rewards import RewardsCalculator
from loaders.config_loader import ConfigLoader
import services.transaction_service as ts

logger = logging.getLogger(__name__)


OUTPUT_DIR = const.OUTPUT_DIR
DB_PATH = const.DB_PATH
CONFIG_DIR = const.CONFIG_DIR
ANALYSIS_DB_PATH = const.ANALYSIS_DB_PATH

def run_rewards_calculation():
    """執行回饋計算並產出 Demo 結果"""
    try:
        # 1. 執行 SQL 提取 (直接更名與轉型)
        df_bills = ts.get_transactions(window=const.TimeWindow.LIFETIME,exclude_non_retail=True)
        if df_bills.empty:
            logger.warning("⚠️ 資料庫中無交易資料。")
            return

        # 2. 載入規則
        configs = {
            'reward_rules': ConfigLoader.load_config(CONFIG_DIR, 'bridge_reward_rules', strategy='replace'),
            'rewards_base': ConfigLoader.load_config(CONFIG_DIR, 'dim_card_rewards_base', strategy='replace'),
            'rewards_campaigns': ConfigLoader.load_config(CONFIG_DIR, 'dim_card_rewards_campaigns', strategy='append')
        }

        # 3. 執行計算
        calculator = RewardsCalculator(configs=configs)
        df_result = calculator.process(df_bills)
        
        # 4. 寫入分析資料庫
        with sqlite3.connect(ANALYSIS_DB_PATH) as conn:
            df_result.to_sql('analysis_rewards', conn, if_exists='replace', index=False)
            
        # 5. 產出 Demo 結果 (Before-After 參照用)
        demo_output = os.path.join(OUTPUT_DIR, 'reward_calculation_result.csv')
        # 挑選關鍵欄位供對照
        display_cols = [const.COL_TXN_DATE, 
                        const.COL_CARD_TYPE,
                        const.COL_MERCHANT_DISPLAY,
                        const.COL_MOBILE_PAY,
                        const.COL_PAY_AMOUNT,
                        'is_bypassed', 
                        'applied_rule']
        df_result[display_cols].to_csv(demo_output, index=False, encoding='utf-8-sig')
        
        logger.info(f"✅ 計算完成！Demo 結果已產出至: {demo_output}")

    except Exception as e:
        logger.error(f"❌ 回饋計算失敗: {e}", exc_info=True)
