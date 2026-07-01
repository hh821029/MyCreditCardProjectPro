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

    def _collect_bank_programs(self) -> dict:
        """蒐集各銀行所屬的所有回饋計畫名稱 (用於方案 A 規則過濾)"""
        bank_programs = {b: set() for b in const.BANK_REWARDS_DB_MAP.keys()}
        
        try:
            # 1. 讀取 dim_card_rewards_base
            df_base = ConfigLoader.load_config(self.config_dir, "dim_card_rewards_base", strategy='replace')
            if not df_base.empty:
                for _, row in df_base.iterrows():
                    bank = row.get('bank_name')
                    prog = row.get('base_reward_program')
                    if pd.notna(bank) and pd.notna(prog):
                        b = str(bank).strip().lower()
                        if b in bank_programs:
                            bank_programs[b].add(str(prog).strip())
            
            # 2. 讀取 dim_card_rewards_campaigns
            df_camp = ConfigLoader.load_config(self.config_dir, "dim_card_rewards_campaigns", strategy='append')
            if not df_camp.empty:
                for _, row in df_camp.iterrows():
                    bank = row.get('bank_name')
                    prog = row.get('campaign_reward_program')
                    if pd.notna(bank) and pd.notna(prog):
                        b = str(bank).strip().lower()
                        if b in bank_programs:
                            bank_programs[b].add(str(prog).strip())
                            
            # 3. 讀取各特殊對照表
            special_tables = [
                ("bridge_cube_selections", "base_reward_program", 'replace'),
                ("bridge_unicard_selections", "rules_reward_program", 'replace'),
                ("bridge_unicard_selections", "campaign_reward_program", 'replace'),
                ("bridge_uniopen_visit_spots", "rules_reward_program", 'replace'),
                ("bridge_uniopen_visit_spots", "campaign_reward_program", 'replace')
            ]
            for csv_base, col, strat in special_tables:
                matched_bank = const.Bank.from_keyword(csv_base)
                if matched_bank:
                    b = matched_bank.bank_id
                    if b in bank_programs:
                        df_sel = ConfigLoader.load_config(self.config_dir, csv_base, strategy=strat)
                        if not df_sel.empty and col in df_sel.columns:
                            for val in df_sel[col].dropna().unique():
                                bank_programs[b].add(str(val).strip())
                                
        except Exception as e:
            logger.error(f"❌ 蒐集銀行回饋計畫名稱失敗: {e}", exc_info=True)
            
        return bank_programs

    def _sync_partitioned_item(self, name: str, csv_base: str, table_name: str, mapping_func, indices: Optional[List[str]] = None, strategy: str = 'append', bank_programs: Optional[dict] = None):
        """分庫同步邏輯"""
        try:
            logger.info(f"🔄 正在分庫同步 {name} (策略: {strategy})...")
            df = ConfigLoader.load_config(self.config_dir, csv_base, strategy=strategy)
            
            if df.empty:
                logger.warning(f"⚠️ {name} 資料為空，跳過同步。")
                return

            # 套用欄位映射
            mapping = mapping_func()
            df_mapped = df.rename(columns=mapping)
            cols_to_keep = [v for v in mapping.values() if v in df_mapped.columns]
            df_final = df_mapped[cols_to_keep]
            if not isinstance(df_final, pd.DataFrame):
                df_final = pd.DataFrame(df_final)

            # 依據發卡銀行 (Bank) 進行垂直拆分
            for bank_id, db_path in const.BANK_REWARDS_DB_MAP.items():
                bank_loader = SQLiteLoader(db_path)
                df_bank = pd.DataFrame()

                # 1. 判斷是否有 bank_name 欄位
                if 'bank_name' in df_final.columns:
                    df_bank = df_final[df_final['bank_name'] == bank_id]
                
                # 2. 判斷是否為特殊的 selection 映射表
                elif 'selection' in csv_base.lower() or 'visit_spots' in csv_base.lower():
                    matched_bank = const.Bank.from_keyword(csv_base)
                    if matched_bank and matched_bank.bank_id == bank_id:
                        df_bank = df_final
                    else:
                        continue
                
                # 3. 判斷是否為回饋規則表 (bridge_reward_rules)
                elif csv_base == 'bridge_reward_rules':
                    if bank_programs and bank_id in bank_programs:
                        progs = bank_programs[bank_id]
                        def filter_rule(row):
                            rule_prog = row.get('rules_reward_program')
                            if pd.isna(rule_prog):
                                return False
                            rule_prog_str = str(rule_prog).strip()
                            return rule_prog_str.startswith('共通') or rule_prog_str in progs
                        
                        df_bank = df_final[df_final.apply(filter_rule, axis=1)]
                    else:
                        logger.warning(f"⚠️ {name} 缺少 bank_programs，跳過同步至 {bank_id}。")
                        continue
                
                # 寫入資料庫
                if not df_bank.empty:
                    if not isinstance(df_bank, pd.DataFrame):
                        df_bank = pd.DataFrame(df_bank)
                    bank_loader.load(df_bank, table_name, mode='replace', indices=indices)
                    logger.info(f"✅ {name} ({bank_id}) 同步完成 -> [{table_name}] 在 {os.path.basename(db_path)}")
                else:
                    df_empty = pd.DataFrame(columns=df_final.columns)
                    bank_loader.load(df_empty, table_name, mode='replace', indices=indices)
        except Exception as e:
            logger.error(f"❌ {name} 分庫同步失敗: {e}", exc_info=True)

    def sync_cards(self):
        # 1. 寫入全域庫
        self._sync_item(
            "信用卡資料", 
            "dim_cards", 
            "dim_cards", 
            CARD_INFO_COL_MAPPING, 
            indices=['card_no', 'card_type', 'bank_name'],
            strategy='replace'
        )
        # 2. 寫入各分庫
        self._sync_partitioned_item(
            "信用卡資料(分庫)", 
            "dim_cards", 
            "dim_cards", 
            CARD_INFO_COL_MAPPING, 
            indices=['card_no', 'card_type', 'bank_name'],
            strategy='replace'
        )

    def sync_merchants(self):
        self._sync_item(
            "特約商店", 
            "dim_merchants", 
            "dim_merchants", 
            MERCHANT_COL_MAPPING, 
            indices=['merchant_display', 'category'],
            strategy='append'
        )

    def sync_payment_processes(self):
        self._sync_item(
            "支付/處理流程", 
            "dim_payment_process", 
            "dim_payment_process", 
            PAYMENT_PROCESS_COL_MAPPING, 
            indices=['payment_process', 'payment_process_pattern'],
            strategy='append'
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
        self._sync_partitioned_item(
            "基礎回饋計畫", 
            "dim_card_rewards_base", 
            "dim_card_rewards_base", 
            REWARD_PROGRAM_COL_MAPPING, 
            indices=['reward_program', 'card_type', 'bank_name'],
            strategy='replace'
        )

    def sync_reward_campaigns(self):
        self._sync_partitioned_item(
            "活動加碼回饋", 
            "dim_card_rewards_campaigns", 
            "dim_card_rewards_campaigns", 
            REWARD_CAMPAIGN_COL_MAPPING, 
            indices=['campaign_name', 'card_type', 'bank_name'],
            strategy='append'
        )

    def sync_reward_rules(self, bank_programs: Optional[dict] = None):
        if bank_programs is None:
            bank_programs = self._collect_bank_programs()
        self._sync_partitioned_item(
            "回饋規則 (Waterfall)", 
            "bridge_reward_rules", 
            "bridge_reward_rules", 
            REWARD_RULE_COL_MAPPING, 
            indices=['reward_program', 'priority'],
            strategy='append',
            bank_programs=bank_programs
        )

    def sync_bridge_cube_selections(self):
        self._sync_partitioned_item(
            "國泰Cube權益切換歷史", 
            "bridge_cube_selections", 
            "bridge_cube_selections", 
            BRIDGE_CUBE_SELECTION_COL_MAPPING, 
            indices=['base_reward_program', 'start_date', 'end_date'],
            strategy='replace'
        )

    def sync_bridge_unicard_selections(self):
        self._sync_partitioned_item(
            "玉山Unicard方案訂閱歷史", 
            "bridge_unicard_selections", 
            "bridge_unicard_selections", 
            BRIDGE_UNICARD_SELECTION_COL_MAPPING, 
            indices=['rules_reward_program', 'campaign_reward_program', 'start_date', 'end_date'],
            strategy='replace'
        )

    def sync_bridge_uniopen_visit_spots(self):
        self._sync_partitioned_item(
            "中信Uniopen踩點加碼歷史", 
            "bridge_uniopen_visit_spots", 
            "bridge_uniopen_visit_spots", 
            BRIDGE_UNIOPEN_VISIT_SPOTS_COL_MAPPING, 
            indices=['campaign_reward_program', 'rules_reward_program', 'start_date', 'end_date'],
            strategy='replace'
        )

    def sync_dim_fx_table(self):
        self._sync_partitioned_item(
            "匯率每日表", 
            "dim_fx_table", 
            "dim_fx_table", 
            FX_TABLE_COL_MAPPING, 
            indices=['conversion_date', 'bank_name', 'currency_type'],
            strategy='replace'
        )

    def sync_dim_billing_history(self):
        self._sync_partitioned_item(
            "對帳單歷史", 
            "dim_billing_history", 
            "dim_billing_history", 
            BILLING_HISTORY_COL_MAPPING, 
            indices=['bank_name', 'statement_month'],
            strategy='replace'
        )

    def sync_all(self):
        logger.info("🚀 開始執行全量配置同步 (雙資料庫拆分架構)...")
        # 1. 全域維度表
        self.sync_cards()
        self.sync_merchants()
        self.sync_payment_processes()
        self.sync_ec_platforms()
        
        # 2. 先蒐集各銀行關聯的計畫名稱 (用於方案 A 規則過濾)
        bank_programs = self._collect_bank_programs()
        
        # 3. 分庫同步配置
        self.sync_reward_base()
        self.sync_reward_campaigns()
        self.sync_bridge_cube_selections()
        self.sync_bridge_unicard_selections()
        self.sync_bridge_uniopen_visit_spots()
        self.sync_dim_fx_table()
        self.sync_dim_billing_history()
        
        # 傳入 bank_programs 避免重複蒐集，提升同步效能
        self.sync_reward_rules(bank_programs=bank_programs)
        
        logger.info("🏁 全量配置同步完成！")

if __name__ == "__main__":
    # 設置基礎 Log 格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    sync_manager = ConfigSyncManager()
    sync_manager.sync_all()
