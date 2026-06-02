# analytics/run_rfm.py
import logging
from services.analysis_service import run_analytics
from const import DB_PATH
import os

# 初始化日誌 (供 CLI 執行時使用)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        logger.error(f"❌ 資料庫不存在: {DB_PATH} ")
    else:
        logger.info("開始執行 RFM 分析")
        run_analytics()
        logger.info("🎉 全部分析完成！你的財務數據已準備就緒。")
