import os
import logging
import pandas as pd
from loaders.config_loader import ConfigLoader
from loaders.sqlite_loader import SQLiteLoader
from configs.db_columns_mapping import (
    CARD_INFO_COL_MAPPING,
    REWARD_PROGRAM_COL_MAPPING,
    MERCHANT_COL_MAPPING,
    PAYMENT_GATEWAY_COL_MAPPING,
    REWARD_RULE_COL_MAPPING
)

logger = logging.getLogger(__name__)

class ConfigSyncManager:
    """
    負責將 configs/*.csv 資料同步至 SQLite 資料庫。
    遵循 GEMINI.md 規範：
    1. 使用 ConfigLoader 處理編碼與私有檔合併 (Append/Replace)
    2. 使用 SQLiteLoader 執行資料庫寫入與索引建立
    """
    def __init__(self, config_dir='configs', db_path='output/Configs.db'):
        self.config_dir = config_dir
        self.db_path = db_path
        self.loader = SQLiteLoader(self.db_path)

    def _sync_item(self, name, csv_base, table_name, mapping_func, indices=None, strategy=None):
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

    def sync_gateways(self):
        self._sync_item(
            "支付平台", 
            "dim_payment_gateway", 
            "dim_payment_gateways", 
            PAYMENT_GATEWAY_COL_MAPPING, 
            indices=['gateway_name', 'gateway_display'],
            strategy='append'  # 支付平台資料以合併方式處理
        )

    def sync_reward_programs(self):
        """同步回饋計畫 (合併基礎與活動)"""
        try:
            logger.info("🔄 正在同步 回饋計畫 (Base + Campaigns)...")
            df_base = ConfigLoader.load_config(self.config_dir, "dim_card_rewards_base")
            df_camp = ConfigLoader.load_config(self.config_dir, "dim_card_rewards_campaigns")
            
            df_combined = pd.concat([df_base, df_camp], ignore_index=True).drop_duplicates()
            
            if df_combined.empty:
                logger.warning("⚠️ 回饋計畫資料為空，跳過。")
                return

            mapping = REWARD_PROGRAM_COL_MAPPING()
            df_mapped = df_combined.rename(columns=mapping)
            cols_to_keep = [v for v in mapping.values() if v in df_mapped.columns]
            df_final = df_mapped[cols_to_keep]

            self.loader.load(df_final, "dim_reward_programs", mode='replace', indices=['reward_program', 'card_type', 'bank_name'])
            logger.info("✅ 回饋計畫同步完成 -> [dim_reward_programs]")
        except Exception as e:
            logger.error(f"❌ 回饋計畫同步失敗: {e}", exc_info=True)

    def sync_reward_rules(self):
        self._sync_item(
            "回饋規則 (Waterfall)", 
            "bridge_reward_rules", 
            "bridge_reward_rules", 
            REWARD_RULE_COL_MAPPING, 
            indices=['reward_program', 'priority'],
            strategy='append'
        )

    def sync_all(self):
        logger.info("🚀 開始執行全量配置同步...")
        self.sync_cards()
        self.sync_merchants()
        self.sync_gateways()
        self.sync_reward_programs()
        self.sync_reward_rules()
        logger.info("🏁 全量配置同步完成！")

if __name__ == "__main__":
    # 設置基礎 Log 格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    sync_manager = ConfigSyncManager()
    sync_manager.sync_all()
