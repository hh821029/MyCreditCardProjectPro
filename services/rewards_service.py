# services/rewards_service.py
import os
import pandas as pd
import logging
import sqlite3
import const
from typing import Dict, Optional, List
from processors.rewards import RewardsCalculator
from loaders.config_loader import ConfigLoader
import services.transaction_service as ts
import services.config_service as cs

logger = logging.getLogger(__name__)


OUTPUT_DIR = const.OUTPUT_DIR
DB_PATH = const.DB_PATH
CONFIG_DIR = const.CONFIG_DIR
ANALYSIS_DB_PATH = const.ANALYSIS_DB_PATH

def run_rewards_calculation(
    banks: Optional[List[str]] = None,
    cards: Optional[List[str]] = None,
    payments: Optional[List[str]] = None,
    time_window: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location: Optional[str] = None
):
    """執行回饋計算並產出 Demo 結果"""
    try:
        # 1. 執行 SQL 提取 (直接更名與轉型)
        if any([banks, cards, payments, time_window, start_date, end_date, location]):
            logger.info("⚙️ 偵測到篩選參數，將採用動態 SQL 篩選交易資料進行回饋金計算...")
            df_bills = ts.query_transactions_modular(
                banks=banks,
                cards=cards,
                payments=payments,
                time_window=time_window,
                start_date=start_date,
                end_date=end_date,
                location=location,
                exclude_non_retail=True
            )
        else:
            df_bills = ts.get_transactions(window=const.TimeWindow.LIFETIME, exclude_non_retail=True)
        if df_bills.empty:
            logger.warning("⚠️ 資料庫中無交易資料。")
            return

        # 2. 載入規則 (從資料庫服務載入)

        configs = cs.get_rewards_configs_table()

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
