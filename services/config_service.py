import logging
from loaders.sync_configs_to_db import ConfigSyncManager
import const
import pandas as pd
from typing import Optional

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

#def get_rewards_configs_table(
#    window: const.TimeWindow = const.TimeWindow.LAST_YEAR,
#    exclude_non_retail: bool = False,
#    anchor_date: Optional[str] = None,
#) -> pd.DataFrame:
#    """
#    通用交易資料讀取服務 (支援防禦性時間視窗與動態基準日)
#    """
#    conditions = []
#    params = {}

#    try:
#
#       df_billing_history = pd.read_sql("SELECT * FROM dim_billing_history", conn)
#
#
#
#    
#    return configs