# analytics/run_rfm.py
import logging
from services.analysis_service import run_analytics

# 初始化日誌 (供 CLI 執行時使用)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    run_analytics()
