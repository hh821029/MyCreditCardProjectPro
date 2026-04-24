# loaders/sqlite_loader.py
import pandas as pd
import sqlite3
import hashlib
import os
import logging
import const
from configs.db_columns_mapping import ALL_TRANSACTION_COL_MAPPING

logger = logging.getLogger(__name__)

class SQLiteLoader:
    """
    [資料載入層]
    負責將清洗完畢的 DataFrame 寫入 SQLite 資料庫。
    包含：
    1. 生成唯一 Transaction ID (MD5 Hash)
    2. 欄位名稱轉換 (CamelCase -> snake_case)
    3. 資料庫寫入與索引建立
    """
    def __init__(self, output_dir: str, db_name: str = 'Bills.db', table_name: str = 'all_transactions'):
        # 確保 output 資料夾存在
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.output_dir, db_name)
        self.table_name = table_name

    def _generate_transaction_id(self, row: pd.Series) -> str:
        """
        建立唯一的交易 ID (Hash)
        組合：日期 + 商家 + 金額 + 卡號 + 交易類型
        """
        def safe_str(val):
            return str(val).strip() if pd.notna(val) else ""

        # 使用 const.py 定義的常數，確保欄位名稱一致
        unique_str = (
            safe_str(row.get(const.COL_TXN_DATE)) +
            safe_str(row.get(const.COL_MERCHANT)) +
            safe_str(row.get(const.COL_CARD_NO)) +
            safe_str(row.get(const.COL_PAY_AMOUNT)) + 
            safe_str(row.get(const.COL_TXN_TYPE)) +
            safe_str(row.get('_seq'))
        )
        return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

    def load(self, df: pd.DataFrame, mode: str = 'replace'):
        """
        將 DataFrame 寫入 SQLite
        mode: 'replace' (全量覆蓋), 'append' (附加)
        """
        if df.empty:
            logger.warning("⚠️ 沒有資料可寫入資料庫。")
            return

        logger.info(f"💾 準備將 {len(df)} 筆資料寫入資料庫 ({self.db_path})...")
        
        # 1. 生成 Primary Key (Transaction_ID)
        df_db = df.copy()
        # 1-1. 計算同日流水號 (解決同日同店同金額連刷被誤刪的問題)
        group_cols = [
            const.COL_TXN_DATE, 
            const.COL_MERCHANT, 
            const.COL_CARD_NO, 
            const.COL_PAY_AMOUNT, 
            const.COL_TXN_TYPE
        ]
        # cumcount 會從 0 開始編號：第一杯咖啡是 0, 第二杯是 1...
        df_db['_seq'] = df_db.groupby(group_cols, dropna=False).cumcount().astype(str)
        # 1-2. 生成 Primary Key (Transaction_ID)
        df_db['transaction_id'] = df_db.apply(self._generate_transaction_id, axis=1)

        # 1-3. 移除重複的交易 (Deduplication)
        # 找出哪些資料即將被移除 (keep='first' 代表第一筆保留，後續重複的都會被標記為 True)
        duplicated_mask = df_db.duplicated(subset=['transaction_id'], keep='first')
        
        if duplicated_mask.any():
            # 把它們抓出來
            df_duplicates = df_db[duplicated_mask].copy()
            drop_count = len(df_duplicates)
            
            logger.info(f"🧹 移除了 {drop_count} 筆重複交易紀錄。")
            
            # [觀察用] 將被移除的資料輸出成 CSV 讓你檢查
            debug_csv_path = os.path.join(self.output_dir, 'dropped_duplicates.csv')
            df_duplicates.to_csv(debug_csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"🔍 被移除的重複資料已存至: {debug_csv_path}，請前往檢查！")
            
        # 正式執行移除 (只保留第一筆)
        df_db = df_db[~duplicated_mask]
        # [移除暫存欄位] 算完 ID 後，_seq 就功成身退了
        df_db = df_db.drop(columns=['_seq'])

        # 2. 欄位更名與篩選 (Mapping to Snake Case)
        rename_map = ALL_TRANSACTION_COL_MAPPING()  # 從獨立的 config 模組取得映射表
        available_cols = [c for c in rename_map.keys() if c in df_db.columns]
        
        # 建立最終要寫入的 DataFrame
        df_final = df_db[available_cols].rename(columns=rename_map)
        df_final['transaction_id'] = df_db['transaction_id']

        # 3. 處理日期欄位，將 Pandas Timestamp 轉為純字串，避免 SQLite 報錯
        date_cols = ['transaction_date', 'posting_date', 'conversion_date', 'statement_month']
        for col in date_cols:
            if col in df_final.columns:
                # 轉為 'YYYY-MM-DD' 格式，若為空值則轉為 NaT
                df_final[col] = pd.to_datetime(df_final[col], errors='coerce').dt.strftime('%Y-%m-%d')

        # 4. 處理空值 (避免 SQL 寫入 NaN 變成 'NaN' 字串)
        # 數值型態填入 None (SQL 的 NULL)，字串型態看需求，這裡統一將字串的 NaN 轉為 None
        df_final = df_final.replace({pd.NA: None, float('nan'): None, 'nan': None})


        # 5. 寫入 SQLite
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 若選擇 replace，會直接覆蓋整張表；若選擇 append，請注意 PK 重複的問題
                # 為了穩健起見，如果 mode='append' 但你想避免重複，需要寫較複雜的 UPSERT 語句
                # 這裡我們先維持原版的 'replace' 或簡單的 'append'
                df_final.to_sql(self.table_name, conn, if_exists=mode, index=False)
                
                # 5. 建立索引 (Optimization)
                cursor = conn.cursor()
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_txn_date ON {self.table_name} (transaction_date)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_merchant ON {self.table_name} (merchant_name)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_card_no ON {self.table_name} (card_no)")
                # transaction_id 雖然是唯一值，但如果是 replace 模式，每次都會重建
                cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_txn_id ON {self.table_name} (transaction_id)")
                
                conn.commit()
                
                # 6. 驗證
                cursor.execute(f"SELECT count(*) FROM {self.table_name}")
                count = cursor.fetchone()[0]
                logger.info(f"✅ 資料庫作業完成！資料表 [{self.table_name}] 目前共有 {count} 筆資料。")

        except Exception as e:
            logger.error(f"❌ 寫入資料庫失敗: {e}", exc_info=True)