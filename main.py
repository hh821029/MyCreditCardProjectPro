import logging
from services.etl_service import run_etl_pipeline

# ==========================================
# 設定日誌 (Logging)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

if __name__ == "__main__":
    run_etl_pipeline()
