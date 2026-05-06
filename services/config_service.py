import logging
from loaders.sync_configs_to_db import ConfigSyncManager

logger = logging.getLogger(__name__)

def run_config_card_sync():
    """信用卡資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_cards()

def run_config_reward_sync():
    """回饋計畫與規則同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_reward_programs()
    sync_manager.sync_reward_rules()

def run_config_merchant_sync():
    """特約商店資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_merchants()

def run_config_paygate_sync():
    """支付平台資料同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_gateways()

def run_all_config_sync():
    """全量設定同步服務"""
    sync_manager = ConfigSyncManager()
    sync_manager.sync_all()
