import os
import logging
from typing import Optional, List
import pandas as pd
import const
from loaders.config_loader import ConfigLoader
from loaders.sqlite_loader import SQLiteLoader
from configs.db_columns_mapping import (
    CARD_INFO_COL_MAPPING,
    REWARD_PROGRAM_COL_MAPPING,
    REWARD_CAMPAIGN_COL_MAPPING,
    MERCHANT_COL_MAPPING,
    PAYMENT_PROCESS_COL_MAPPING,
    EC_PLATFORM_COL_MAPPING,
    REWARD_RULE_COL_MAPPING,
    BRIDGE_CUBE_SELECTION_COL_MAPPING,
    BRIDGE_UNICARD_SELECTION_COL_MAPPING,
    BRIDGE_UNIOPEN_VISIT_SPOTS_COL_MAPPING,
    FX_TABLE_COL_MAPPING,
    BILLING_HISTORY_COL_MAPPING,
)

logger = logging.getLogger(__name__)

class ConfigSyncManager:
    """
    負責將 configs/*.csv 資料同步至 SQLite 資料庫。
    遵循 GEMINI.md 規範：
    1. 使用 ConfigLoader 處理編碼與私有檔合併 (Append/Replace)
    2. 使用 SQLiteLoader 執行資料庫寫入與索引建立
    """
    def __init__(self, config_dir='configs', db_path=None):
        self.config_dir = config_dir
        self.db_path = db_path if db_path is not None else const.CONFIGS_DB_PATH
        self.loader = SQLiteLoader(self.db_path)

    def _sync_item(self, name: str, csv_base: str, table_name: str, mapping_func, indices: Optional[List[str]] = None, strategy: str = 'append'):
        """通用同步邏輯"""
        try:
            logger.info(f"🔄 正在同步 {name}...")
            df = ConfigLoader.load_config(self.config_dir, csv_base, strategy=strategy)
            
            if df.empty:
                logger.warning(f"⚠️ {name} 資料為空，跳過同步。")
                return

            # 套用欄位映射
            mapping = mapping_func()
            df_mapped = df.rename(columns=mapping)
            
            # 僅保留映射定義中的欄位
            cols_to_keep = [v for v in mapping.values() if v in df_mapped.columns]
            df_final = df_mapped[cols_to_keep]
            if not isinstance(df_final, pd.DataFrame):
                df_final = pd.DataFrame(df_final)
 
            # 寫入資料庫
            self.loader.load(df_final, table_name, mode='replace', indices=indices)
            logger.info(f"✅ {name} 同步完成 -> [{table_name}]")
        except Exception as e:
            logger.error(f"❌ {name} 同步失敗: {e}", exc_info=True)

    def sync_cards(self):
        self._sync_item(
            "信用卡資料", 
            "dim_cards", 
            "dim_cards", 
            CARD_INFO_COL_MAPPING, 
            indices=['card_no', 'card_type', 'bank_name'],
            strategy='replace'  # 信用卡資料以私有檔優先且取代基礎檔
        )

    def sync_merchants(self):
        self._sync_item(
            "特約商店", 
            "dim_merchants", 
            "dim_merchants", 
            MERCHANT_COL_MAPPING, 
            indices=['merchant_display', 'category'],
            strategy='append'  # 特約商店資料以合併方式處理
        )

    def sync_payment_processes(self):
        self._sync_item(
            "支付/處理流程", 
            "dim_payment_process", 
            "dim_payment_process", 
            PAYMENT_PROCESS_COL_MAPPING, 
            indices=['payment_process', 'payment_process_pattern'],
            strategy='append'  # 支付/處理流程資料以合併方式處理
        )

    def sync_ec_platforms(self):
        self._sync_item(
            "電商平台", 
            "dim_ec_platform", 
            "dim_ec_platform", 
            EC_PLATFORM_COL_MAPPING, 
            indices=['ec_platform', 'ec_platform_pattern'],
            strategy='append'
        )

    def sync_reward_base(self):
        """同步基礎回饋計畫"""
        self._sync_item(
            "基礎回饋計畫", 
            "dim_card_rewards_base", 
            "dim_card_rewards_base", 
            REWARD_PROGRAM_COL_MAPPING, 
            indices=['reward_program', 'card_type', 'bank_name'],
            strategy='replace'
        )

    def sync_reward_campaigns(self):
        """同步活動加碼回饋"""
        self._sync_item(
            "活動加碼回饋", 
            "dim_card_rewards_campaigns", 
            "dim_card_rewards_campaigns", 
            REWARD_CAMPAIGN_COL_MAPPING, 
            indices=['campaign_name', 'card_type', 'bank_name'],
            strategy='append'
        )

    def sync_reward_rules(self):
        self._sync_item(
            "回饋規則 (Waterfall)", 
            "bridge_reward_rules", 
            "bridge_reward_rules", 
            REWARD_RULE_COL_MAPPING, 
            indices=['reward_program', 'priority'],
            strategy='append'
        )

    def sync_bridge_cube_selections(self):
        self._sync_item(
            "國泰Cube權益切換歷史", 
            "bridge_cube_selections", 
            "bridge_cube_selections", 
            BRIDGE_CUBE_SELECTION_COL_MAPPING, 
            indices=['base_reward_program', 'start_date', 'end_date'],
            strategy='replace'
        )

    def sync_bridge_unicard_selections(self):
        self._sync_item(
            "玉山Unicard方案訂閱歷史", 
            "bridge_unicard_selections", 
            "bridge_unicard_selections", 
            BRIDGE_UNICARD_SELECTION_COL_MAPPING, 
            indices=['rules_reward_program', 'campaign_reward_program', 'start_date', 'end_date'],
            strategy='replace'
        )

    def sync_bridge_uniopen_visit_spots(self):
        self._sync_item(
            "中信Uniopen踩點加碼歷史", 
            "bridge_uniopen_visit_spots", 
            "bridge_uniopen_visit_spots", 
            BRIDGE_UNIOPEN_VISIT_SPOTS_COL_MAPPING, 
            indices=['campaign_reward_program', 'rules_reward_program', 'start_date', 'end_date'],
            strategy='replace'
        )

    def sync_dim_fx_table(self):
        self._sync_item(
            "匯率每日表", 
            "dim_fx_table", 
            "dim_fx_table", 
            FX_TABLE_COL_MAPPING, 
            indices=['conversion_date', 'bank_name', 'currency_type'],
            strategy='replace'
        )

    def sync_dim_billing_history(self):
        self._sync_item(
            "對帳單歷史", 
            "dim_billing_history", 
            "dim_billing_history", 
            BILLING_HISTORY_COL_MAPPING, 
            indices=['bank_name', 'statement_month'],
            strategy='replace'
        )

    def sync_all(self):
        logger.info("🚀 開始執行全量配置同步...")
        self.sync_cards()
        self.sync_merchants()
        self.sync_payment_processes()
        self.sync_ec_platforms()
        self.sync_reward_base()
        self.sync_reward_campaigns()
        self.sync_reward_rules()
        self.sync_bridge_cube_selections()
        self.sync_bridge_unicard_selections()
        self.sync_bridge_uniopen_visit_spots()
        self.sync_dim_fx_table()
        self.sync_dim_billing_history()
        logger.info("🏁 全量配置同步完成！")

if __name__ == "__main__":
    # 設置基礎 Log 格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    sync_manager = ConfigSyncManager()
    sync_manager.sync_all()
