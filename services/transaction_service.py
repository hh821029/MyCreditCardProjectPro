import sqlite3
import pandas as pd
import logging
from typing import Optional, List
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

def query_transactions_modular(
    banks: Optional[List[str]] = None,
    cards: Optional[List[str]] = None,
    payments: Optional[List[str]] = None,
    time_window: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location: Optional[str] = None,
    exclude_non_retail: bool = False,
    db_path: str = const.DB_PATH
) -> pd.DataFrame:
    """
    動態 SQL 條件查詢服務 (支援銀行、卡片、支付方式、預設/自訂時間與國別篩選)
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

    # 2. 處理時間區間 (預設時間區間優先)
    # 動態獲取最新交易日作為 anchor_date，以防止記帳數據落後當下系統時間造成的空白查詢
    anchor_date = None
    if time_window or (not start_date and not end_date):
        try:
            with sqlite3.connect(db_path) as conn:
                max_date = conn.execute("SELECT max(transaction_date) FROM all_transactions").fetchone()[0]
                if max_date:
                    anchor_date = max_date.split()[0] # 拔除可能的時間後綴
        except Exception:
            pass

    if time_window:
        try:
            tw_enum = const.TimeWindow[time_window]
            calculated_start = tw_enum.get_start_date(anchor_date)
            if calculated_start:
                conditions.append("transaction_date >= :start_date")
                params["start_date"] = calculated_start
            if anchor_date:
                conditions.append("transaction_date <= :end_date")
                params["end_date"] = anchor_date
        except KeyError:
            logger.warning(f"⚠️ 傳入未知的時間視窗名稱: {time_window}，將略過預設時間篩選。")
    else:
        # 使用自訂起迄時間
        if start_date:
            conditions.append("transaction_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("transaction_date <= :end_date")
            params["end_date"] = end_date

    # 3. 處理銀行核取清單
    if banks:
        bank_placeholders = []
        for i, b in enumerate(banks):
            key = f"bank_{i}"
            bank_placeholders.append(f":{key}")
            params[key] = b
        conditions.append(f"bank_name IN ({', '.join(bank_placeholders)})")

    # 4. 處理卡片核取清單
    if cards:
        card_placeholders = []
        for i, c in enumerate(cards):
            key = f"card_{i}"
            card_placeholders.append(f":{key}")
            params[key] = c
        conditions.append(f"card_type IN ({', '.join(card_placeholders)})")

    # 5. 處理支付方式核取清單
    if payments:
        pay_placeholders = []
        for i, p in enumerate(payments):
            key = f"pay_{i}"
            pay_placeholders.append(f":{key}")
            params[key] = p
        conditions.append(f"mobile_payment IN ({', '.join(pay_placeholders)})")

    # 6. 處理兩碼國家代碼篩選 (精確比對)
    if location:
        conditions.append("merchant_location = :location")
        params["location"] = location

    # 7. 排除非零售交易 (回饋金計算所需)
    if exclude_non_retail:
        conditions.append("transaction_type NOT IN ('繳款', '紅利折抵', '各項費用')")

    # 8. 組裝與執行 SQL
    sql = f"SELECT {', '.join(query_parts)} FROM all_transactions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    
    sql += " ORDER BY transaction_date DESC"

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql(sql, conn, params=params, parse_dates=[const.COL_TXN_DATE])
            logger.info(f"📥 [DB 條件篩選] 成功載入 {len(df)} 筆交易資料 (條件數: {len(conditions)})")
            return df
    except Exception as e:
        logger.error(f"❌ 條件查詢交易資料庫失敗: {e}", exc_info=True)
        return pd.DataFrame()