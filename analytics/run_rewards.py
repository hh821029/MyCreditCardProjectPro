# analytics/run_rewards.py
import logging
from services.rewards_service import run_rewards_calculation
from const import DB_PATH
import os


# 初始化日誌 (供 CLI 執行時使用)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


if __name__ == "__main__":

    if not os.path.exists(DB_PATH):
        logger.error(f"❌ 資料庫不存在: {DB_PATH}")
    else:
        logger.info("💰 啟動回饋計算服務 (規範 V2)...")
        run_rewards_calculation()
