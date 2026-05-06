# services/rewards_service.py
import os
import pandas as pd
import logging
import sqlite3
from typing import Dict, Optional
from processors.rewards import RewardsCalculator
from loaders.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

import const

OUTPUT_DIR = const.OUTPUT_DIR
DB_PATH = const.DB_PATH
CONFIG_DIR = const.CONFIG_DIR

def run_rewards_calculation():
    """執行回饋計算並產出 Demo 結果"""
    logger.info("💰 啟動回饋計算服務 (規範 V2)...")

    if not os.path.exists(DB_PATH):
        logger.error(f"❌ 資料庫不存在: {DB_PATH}")
        return

    try:
        import const
        # 1. 執行 SQL 提取 (直接更名與轉型)
        # 注意：SQLite 沒有真正的日期型態，所以我們選取後交給 Pandas parse_dates 處理
        query = f"""
            SELECT 
                transaction_date AS {const.COL_TXN_DATE},
                merchant_display AS {const.COL_MERCHANT_DISPLAY},
                merchant_location AS {const.COL_LOCATION},
                mobile_payment AS {const.COL_MOBILE_PAY},
                CAST(payment_amount AS REAL) AS {const.COL_PAY_AMOUNT},
                CAST(card_type AS TEXT) AS {const.COL_CARD_TYPE},
                bank_name AS {const.COL_BANK_NAME},
                transaction_type AS {const.COL_TXN_TYPE}
            FROM all_transactions
            WHERE transaction_type NOT IN ('繳款', '紅利折抵', '各項費用')
        """
        
        with sqlite3.connect(DB_PATH) as conn:
            df_bills = pd.read_sql(query, conn, parse_dates=[const.COL_TXN_DATE])
        
        if df_bills.empty:
            logger.warning("⚠️ 資料庫中無交易資料。")
            return

        # 2. 載入規則
        configs = {
            'reward_rules': ConfigLoader.load_config(CONFIG_DIR, 'bridge_reward_rules', strategy='replace'),
            'rewards_base': ConfigLoader.load_config(CONFIG_DIR, 'dim_card_rewards_base', strategy='replace'),
            'rewards_campaigns': ConfigLoader.load_config(CONFIG_DIR, 'dim_card_rewards_campaigns', strategy='replace')
        }

        # 3. 執行計算
        calculator = RewardsCalculator(configs=configs)
        df_result = calculator.process(df_bills)
        
        # 4. 寫回資料庫
        with sqlite3.connect(DB_PATH) as conn:
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
