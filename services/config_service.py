import os
import logging
from loaders.sync_configs_to_db import ConfigSyncManager
import const
import pandas as pd
from typing import Optional
import sqlite3
from loaders.schema_enforcer import SchemaEnforcer

logger = logging.getLogger(__name__)

def run_config_card_sync():
    """信用卡資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_cards()

def run_config_reward_sync():
    """回饋計畫與規則同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_reward_base()
    sync_manager.sync_reward_campaigns()
    sync_manager.sync_reward_rules()
    sync_manager.sync_bridge_cube_selections()
    sync_manager.sync_bridge_unicard_selections()
    sync_manager.sync_bridge_uniopen_visit_spots()

def run_config_merchant_sync():
    """特約商店資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_merchants()

def run_config_paygate_sync():
    """支付平台資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_payment_processes()

def run_all_config_sync():
    """全量設定同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_all()

def run_config_billing_history_sync():
    """對帳單歷史資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_dim_billing_history()

def run_config_fx_table_sync():
    """匯率每日表同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_dim_fx_table()

def get_rewards_configs_table(
    window: Optional[const.TimeWindow] = None,
    exclude_non_retail: bool = False,
    anchor_date: Optional[str] = None,
) -> dict:
    """
    從 TransactionsConfigs.db 提取回饋配置 (服務化提取)
    """    
    db_path = const.CONFIGS_DB_PATH
    logger.info(f"Connecting to: {db_path}")
    
    configs = {}
    try:
        with sqlite3.connect(db_path) as conn:
            # 1. 讀取 bridge_reward_rules
            df_rules = pd.read_sql_query("SELECT * FROM bridge_reward_rules", conn)
            logger.info("Successfully loaded bridge_reward_rules table.")
            
            # 2. 讀取 dim_card_rewards_base (附防呆名稱)
            try:
                df_base = pd.read_sql_query("SELECT * FROM dim_card_rewards_base", conn)
            except Exception:
                try:
                    df_base = pd.read_sql_query("SELECT * FROM dim_reward_base", conn)
                except Exception as e:
                    logger.error(f"Failed to read dim_card_rewards_base or dim_reward_base: {e}")
                    raise e
            logger.info("Successfully loaded dim_card_rewards_base table.")
            
            # 3. 讀取 dim_card_rewards_campaigns (附防呆名稱)
            try:
                df_camp = pd.read_sql_query("SELECT * FROM dim_card_rewards_campaigns", conn)
            except Exception:
                try:
                    df_camp = pd.read_sql_query("SELECT * FROM dim_reward_campaigns", conn)
                except Exception as e:
                    logger.error(f"Failed to read dim_card_rewards_campaigns or dim_reward_campaigns: {e}")
                    raise e
            logger.info("Successfully loaded dim_card_rewards_campaigns table.")
            
            # 型態執法防護
            df_rules = SchemaEnforcer.enforce(df_rules)
            df_base = SchemaEnforcer.enforce(df_base)
            df_camp = SchemaEnforcer.enforce(df_camp)
            
            # 打包回傳，確保 Key 匹配運算引擎
            configs = {
                'reward_rules': df_rules,
                'rewards_base': df_base,
                'rewards_campaigns': df_camp
            }
            
            # 4. 讀取 dim_cards
            try:
                df_cards = pd.read_sql_query("SELECT * FROM dim_cards", conn)
                df_cards = SchemaEnforcer.enforce(df_cards)
                configs['dim_cards'] = df_cards
                logger.info(f"Successfully loaded dim_cards table: {df_cards.shape}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read dim_cards from database: {e}")
                
            # 5. 讀取 bridge_cube_selections
            try:
                df_cube = pd.read_sql_query("SELECT * FROM bridge_cube_selections", conn)
                df_cube = SchemaEnforcer.enforce(df_cube)
                configs['bridge_cube_selections'] = df_cube
                logger.info(f"Successfully loaded bridge_cube_selections table: {df_cube.shape}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read bridge_cube_selections from database: {e}")
                
            # 6. 讀取 bridge_unicard_selections
            try:
                df_unicard = pd.read_sql_query("SELECT * FROM bridge_unicard_selections", conn)
                df_unicard = SchemaEnforcer.enforce(df_unicard)
                configs['bridge_unicard_selections'] = df_unicard
                logger.info(f"Successfully loaded bridge_unicard_selections table: {df_unicard.shape}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read bridge_unicard_selections from database: {e}")

            # 7. 讀取 bridge_uniopen_visit_spots
            try:
                df_uniopen = pd.read_sql_query("SELECT * FROM bridge_uniopen_visit_spots", conn)
                df_uniopen = SchemaEnforcer.enforce(df_uniopen)
                configs['bridge_uniopen_visit_spots'] = df_uniopen
                logger.info(f"Successfully loaded bridge_uniopen_visit_spots table: {df_uniopen.shape}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read bridge_uniopen_visit_spots from database: {e}")
            
            # 輸出 tables shape 供除錯驗證
            logger.info(f"Loaded config shapes -> rules: {df_rules.shape}, base: {df_base.shape}, campaigns: {df_camp.shape}")
            
    except Exception as e:
        logger.error(f"❌ 讀取回饋配置資料庫失敗: {e}", exc_info=True)
        raise e
        
    return configs

def get_analyzable_data() -> dict:
    """
    從 TransactionsConfigs.db 中取得：
    1. 不重複的銀行名 (來自 const.Bank)
    2. 不重複的卡片名 (來自 dim_cards.card_type)
    3. 不重複的第三方支付 (來自 dim_payment_process.payment_process，取 priority < 25)
    """
    db_path = const.CONFIGS_DB_PATH
    logger.info(f"💾 開始讀取可分析資料欄位，資料庫路徑: {db_path}")
    
    result = {
        "banks": [],
        "cards": [],
        "payment_processes": [],
        "locations": [],
        "categories": [],
        "sub_categories": [],
        "category_sub_map": {}
    }
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 取得不重複的銀行名 (改由 const.Bank 載入)
            try:
                result["banks"] = [{"id": bank.bank_id, "name": bank.bank_display_name} for bank in const.Bank]
                logger.info(f"🔍 讀取銀行名成功 (from const.Bank)，共 {len(result['banks'])} 筆")
            except Exception as e:
                logger.warning(f"⚠️ 無法從 const.Bank 讀取 bank_name: {e}")
                
            # 2. 取得不重複的卡片名
            try:
                cursor.execute("SELECT DISTINCT card_type FROM dim_cards WHERE card_type IS NOT NULL AND card_type != ''")
                result["cards"] = [row[0] for row in cursor.fetchall()]
                logger.info(f"🔍 讀取卡片名成功，共 {len(result['cards'])} 筆")
            except Exception as e:
                logger.warning(f"⚠️ 無法從 dim_cards 讀取 card_type: {e}")
                
            # 3. 取得不重複的第三方支付 (priority < 25)
            try:
                cursor.execute("SELECT DISTINCT payment_process FROM dim_payment_process WHERE priority < 25 AND payment_process IS NOT NULL AND payment_process != '' ORDER BY priority ")
                result["payment_processes"] = [row[0] for row in cursor.fetchall()]
                logger.info(f"🔍 讀取第三方支付成功，共 {len(result['payment_processes'])} 筆")
            except Exception as e:
                logger.warning(f"⚠️ 無法從 dim_payment_process 讀取 payment_process: {e}")
                
            # 4. 取得國家代碼 (從 const.Location Enum)
            try:
                result["locations"] = [loc.alpha_2 for loc in const.Location]
                logger.info(f"🔍 讀取國家代碼成功，共 {len(result['locations'])} 筆")
            except Exception as e:
                logger.warning(f"⚠️ 無法從 const.Location 讀取 locations: {e}")
                
            # 5. 取得消費類別 (從 dim_merchants.csv)
            try:
                merchants_path = os.path.join(const.CONFIG_DIR, 'dim_merchants.csv')
                if os.path.exists(merchants_path):
                    m_df = pd.read_csv(merchants_path, dtype=str)
                    if 'category' in m_df.columns:
                        cats = m_df['category'].dropna().unique().tolist()
                        result["categories"] = sorted([c.strip() for c in cats if c.strip()])
                logger.info(f"🔍 讀取消費類別成功，共 {len(result['categories'])} 筆")
            except Exception as e:
                logger.warning(f"⚠️ 無法從 dim_merchants.csv 讀取 categories: {e}")
                
            # 6. 建立消費主類別與次類別的對應關係與次分類清單 (從 dim_merchants.csv)
            try:
                merchants_path = os.path.join(const.CONFIG_DIR, 'dim_merchants.csv')
                if os.path.exists(merchants_path):
                    m_df = pd.read_csv(merchants_path, dtype=str)
                    if 'category' in m_df.columns and 'sub_category' in m_df.columns:
                        # 清洗並過濾空值
                        m_df['category'] = m_df['category'].astype(str).str.strip()
                        m_df['sub_category'] = m_df['sub_category'].astype(str).str.strip()
                        
                        valid_df = m_df[
                            m_df['category'].notna() & (m_df['category'] != '') & (m_df['category'] != 'nan') &
                            m_df['sub_category'].notna() & (m_df['sub_category'] != '') & (m_df['sub_category'] != 'nan')
                        ]
                        
                        # 建立對照 Map
                        cat_sub_map = {}
                        for _, row in valid_df.iterrows():
                            cat = row['category']
                            sub_cat = row['sub_category']
                            if cat not in cat_sub_map:
                                cat_sub_map[cat] = set()
                            cat_sub_map[cat].add(sub_cat)
                        
                        result["category_sub_map"] = {k: sorted(list(v)) for k, v in cat_sub_map.items()}
                        
                        # 取得所有不重複的次分類
                        all_sub_cats = valid_df['sub_category'].unique().tolist()
                        result["sub_categories"] = sorted(all_sub_cats)
                logger.info(f"🔍 讀取消費主次分類對應關係成功，共 {len(result['category_sub_map'])} 組主分類，共 {len(result['sub_categories'])} 個次分類")
            except Exception as e:
                logger.warning(f"⚠️ 無法從 dim_merchants.csv 讀取主次分類對應關係: {e}")
                
    except Exception as e:
        logger.error(f"❌ 讀取可分析資料失敗: {e}", exc_info=True)
        raise e
        
    return result