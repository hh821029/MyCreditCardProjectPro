import sqlite3
import pandas as pd
import logging
from typing import Optional
import const

logger = logging.getLogger(__name__)

def get_transactions(
    window: const.TimeWindow = const.TimeWindow.LAST_YEAR,
    exclude_non_retail: bool = False,
    anchor_date: Optional[str] = None,
    db_path: str = const.DB_PATH
) -> pd.DataFrame:
    """
    通用交易資料讀取服務 (支援防禦性時間視窗與動態基準日)
    """
    conditions = []
    params = {}
    
    # 統一 SQL 欄位映射與型別強轉 (SSOT 對齊)
    query_parts = [
        "transaction_id",
        f"transaction_date AS {const.COL_TXN_DATE}",
        f"merchant_display AS {const.COL_MERCHANT_DISPLAY}",
        f"merchant_location AS {const.COL_LOCATION}",
        f"mobile_payment AS {const.COL_MOBILE_PAY}",
        f"CAST(payment_amount AS REAL) AS {const.COL_PAY_AMOUNT}",
        f"CAST(card_type AS TEXT) AS {const.COL_CARD_TYPE}",
        f"bank_name AS {const.COL_BANK_NAME}",
        f"transaction_type AS {const.COL_TXN_TYPE}"
    ]
    
    # 動態獲取最新交易日作為 anchor_date，以防止記帳數據落後當下系統時間造成的空白查詢
    if not anchor_date and window != const.TimeWindow.LIFETIME:
        try:
            with sqlite3.connect(db_path) as conn:
                max_date = conn.execute("SELECT max(transaction_date) FROM all_transactions").fetchone()[0]
                if max_date:
                    anchor_date = max_date.split()[0] # 拔除可能的時間後綴
        except Exception:
            pass

    # 取得起迄時間限制
    start_date = window.get_start_date(anchor_date)
    if start_date:
        conditions.append("transaction_date >= :start_date")
        params["start_date"] = start_date
        
    if exclude_non_retail:
        conditions.append("transaction_type NOT IN ('繳款', '紅利折抵', '各項費用')")
        
    # 組裝 SQL
    sql = f"SELECT {', '.join(query_parts)} FROM all_transactions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
        
    try:
        with sqlite3.connect(db_path) as conn:
            # 善用 parse_dates 在 C 底層直接將時間轉為 Datetime 物件，效率最高
            df = pd.read_sql(sql, conn, params=params, parse_dates=[const.COL_TXN_DATE])
            logger.info(f"📥 [DB 提取] 成功載入 {len(df)} 筆交易資料 (時間視窗: {window.name}, 基準日: {anchor_date})")
            return df
    except Exception as e:
        logger.error(f"❌ 讀取交易資料庫失敗: {e}", exc_info=True)
        return pd.DataFrame()