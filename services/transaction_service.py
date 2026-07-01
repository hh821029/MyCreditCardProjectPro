import sqlite3
import os
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
    db_path: str = const.DB_PATH,
    limit_by_card_start: bool = False
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
        f"transaction_type AS {const.COL_TXN_TYPE}",
        f"statement_month AS {const.COL_STAT_MON}"
    ]

    # 1.5. 限制交易日期必須在啟用卡片起始日之後
    if limit_by_card_start:
        # 決定要讀取的設定資料庫
        # 全選勾選 或 未指定：使用主設定庫 TransactionsConfigs.db
        is_all_banks = not banks or len(banks) == len(const.BANK_REWARDS_DB_MAP)
        
        min_start_date = None
        
        if is_all_banks:
            config_db = const.CONFIGS_DB_PATH
            try:
                with sqlite3.connect(config_db) as cfg_conn:
                    row = cfg_conn.execute("SELECT min(card_start_date) FROM dim_cards WHERE card_start_date IS NOT NULL AND card_start_date != ''").fetchone()
                    if row and row[0]:
                        min_start_date = str(row[0]).split()[0]
            except Exception as e:
                logger.error(f"❌ 查詢啟用卡片最小起始日失敗 (主設定庫: {config_db}): {e}")
        else:
            # 勾選一個或多個：從這些被勾選的銀行專屬分區資料庫中查找
            min_dates = []
            for b in banks:
                b_clean = b.strip().lower()
                if b_clean in const.BANK_REWARDS_DB_MAP:
                    config_db = const.BANK_REWARDS_DB_MAP[b_clean]
                    try:
                        with sqlite3.connect(config_db) as cfg_conn:
                            row = cfg_conn.execute("SELECT min(card_start_date) FROM dim_cards WHERE card_start_date IS NOT NULL AND card_start_date != ''").fetchone()
                            if row and row[0]:
                                min_dates.append(str(row[0]).split()[0])
                    except Exception as e:
                        logger.error(f"❌ 查詢啟用卡片最小起始日失敗 (分區庫: {config_db}): {e}")
            if min_dates:
                min_start_date = min(min_dates)
            
        if min_start_date:
            conditions.append("transaction_date >= :card_start_min")
            params["card_start_min"] = min_start_date
            logger.info(f"📅 [卡片啟用日限縮] 設定交易日期上限必須 >= {min_start_date}")

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
