# analytics/run_rewards.py
import logging
from services.rewards_service import run_rewards_calculation

# 初始化日誌 (供 CLI 執行時使用)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    run_rewards_calculation()
