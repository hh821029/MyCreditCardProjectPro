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
    banks: Optional[list[str]] = None,
    cards: Optional[list[str]] = None,
    payments: Optional[list[str]] = None,
    time_window: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location: Optional[str] = None,
    enable_billing_validation: bool = True,
    limit_by_card_start: bool = False
) -> dict:
    """
    從多個 RewardsConfigs_{bank}.db 提取回饋配置，並將其合併為單一配置字典返回 (向下相容)
    """
    # 若無指定銀行，預設載入所有已配置的銀行資料庫
    if not banks:
        banks = list(const.BANK_REWARDS_DB_MAP.keys())
    
    logger.info(f"🔑 開始從分庫載入回饋配置，銀行清單: {banks}")
    
    # 宣告暫存清單，用來收集各分庫的 dataframe
    rules_list = []
    base_list = []
    camp_list = []
    cards_list = []
    cube_list = []
    unicard_list = []
    uniopen_list = []
    billing_list = []
    
    for bank in banks:
        db_path = const.BANK_REWARDS_DB_MAP.get(bank)
        if not db_path:
            logger.warning(f"⚠️ 找不到銀行 [{bank}] 的資料庫路徑定義，跳過。")
            continue
            
        if not os.path.exists(db_path):
            logger.warning(f"⚠️ 銀行 [{bank}] 的資料庫檔案不存在 ({db_path})，跳過。")
            continue
            
        logger.info(f"Connecting to bank [{bank}] config db: {db_path}")
        try:
            with sqlite3.connect(db_path) as conn:
                # 1. 讀取 bridge_reward_rules
                try:
                    df = pd.read_sql_query("SELECT * FROM bridge_reward_rules", conn)
                    if not df.empty:
                        rules_list.append(df)
                except Exception as e:
                    logger.debug(f"[{bank}] 無法讀取 bridge_reward_rules: {e}")

                # 2. 讀取 dim_card_rewards_base
                try:
                    df = pd.read_sql_query("SELECT * FROM dim_card_rewards_base", conn)
                    if not df.empty:
                        base_list.append(df)
                except Exception:
                    try:
                        df = pd.read_sql_query("SELECT * FROM dim_reward_base", conn)
                        if not df.empty:
                            base_list.append(df)
                    except Exception as e:
                        logger.debug(f"[{bank}] 無法讀取 dim_card_rewards_base: {e}")

                # 3. 讀取 dim_card_rewards_campaigns
                try:
                    df = pd.read_sql_query("SELECT * FROM dim_card_rewards_campaigns", conn)
                    if not df.empty:
                        camp_list.append(df)
                except Exception:
                    try:
                        df = pd.read_sql_query("SELECT * FROM dim_reward_campaigns", conn)
                        if not df.empty:
                            camp_list.append(df)
                    except Exception as e:
                        logger.debug(f"[{bank}] 無法讀取 dim_card_rewards_campaigns: {e}")

                # 4. 讀取 dim_cards
                try:
                    df = pd.read_sql_query("SELECT * FROM dim_cards", conn)
                    if not df.empty:
                        cards_list.append(df)
                except Exception as e:
                    logger.debug(f"[{bank}] 無法讀取 dim_cards: {e}")

                # 5. 讀取 bridge_cube_selections
                try:
                    df = pd.read_sql_query("SELECT * FROM bridge_cube_selections", conn)
                    if not df.empty:
                        cube_list.append(df)
                except Exception as e:
                    logger.debug(f"[{bank}] 無法讀取 bridge_cube_selections: {e}")

                # 6. 讀取 bridge_unicard_selections
                try:
                    df = pd.read_sql_query("SELECT * FROM bridge_unicard_selections", conn)
                    if not df.empty:
                        unicard_list.append(df)
                except Exception as e:
                    logger.debug(f"[{bank}] 無法讀取 bridge_unicard_selections: {e}")

                # 7. 讀取 bridge_uniopen_visit_spots
                try:
                    df = pd.read_sql_query("SELECT * FROM bridge_uniopen_visit_spots", conn)
                    if not df.empty:
                        uniopen_list.append(df)
                except Exception as e:
                    logger.debug(f"[{bank}] 無法讀取 bridge_uniopen_visit_spots: {e}")

                # 8. 讀取 dim_billing_history
                try:
                    df = pd.read_sql_query("SELECT * FROM dim_billing_history", conn)
                    if not df.empty:
                        billing_list.append(df)
                except Exception as e:
                    logger.debug(f"[{bank}] 無法讀取 dim_billing_history: {e}")

        except Exception as e:
            logger.error(f"❌ 讀取銀行 [{bank}] 回饋配置失敗: {e}", exc_info=True)

    # 合併收集到的資料，並進行 SchemaEnforcer 與去重 (drop_duplicates)
    def concat_and_clean(df_list, table_name):
        if not df_list:
            # 回傳包含對應 schema 的空 DataFrame
            return pd.DataFrame()
        df_concat = pd.concat(df_list, ignore_index=True)
        # 去除重複列 (特別像 "共通" 規則在各資料庫中都會有一份)
        df_concat = df_concat.drop_duplicates().reset_index(drop=True)
        return SchemaEnforcer.enforce(df_concat)

    df_rules = concat_and_clean(rules_list, 'bridge_reward_rules')
    df_base = concat_and_clean(base_list, 'dim_card_rewards_base')
    df_camp = concat_and_clean(camp_list, 'dim_card_rewards_campaigns')
    df_cards = concat_and_clean(cards_list, 'dim_cards')
    df_cube = concat_and_clean(cube_list, 'bridge_cube_selections')
    df_unicard = concat_and_clean(unicard_list, 'bridge_unicard_selections')
    df_uniopen = concat_and_clean(uniopen_list, 'bridge_uniopen_visit_spots')
    df_billing = concat_and_clean(billing_list, 'dim_billing_history')

    configs = {
        'reward_rules': df_rules,
        'rewards_base': df_base,
        'rewards_campaigns': df_camp,
        'dim_cards': df_cards,
        'bridge_cube_selections': df_cube,
        'bridge_unicard_selections': df_unicard,
        'bridge_uniopen_visit_spots': df_uniopen,
        'dim_billing_history': df_billing
    }

    logger.info(f"Loaded config shapes -> rules: {df_rules.shape}, base: {df_base.shape}, campaigns: {df_camp.shape}, billing: {df_billing.shape}")
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
                
            # 2. 取得不重複的卡片名 (依 CSV 的物理順序排序)
            try:
                cursor.execute("""
                    SELECT card_type 
                    FROM dim_cards 
                    WHERE card_type IS NOT NULL AND card_type != '' 
                    GROUP BY card_type 
                    ORDER BY min(rowid)
                """)
                result["cards"] = [row[0] for row in cursor.fetchall()]
                logger.info(f"🔍 讀取卡片名成功 (依 rowid 排序)，共 {len(result['cards'])} 筆")
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