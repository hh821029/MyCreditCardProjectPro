import pandas as pd
import sqlite3
import logging
import os
from typing import Optional, List, Literal

logger = logging.getLogger(__name__)

class SQLiteLoader:
    """
    [資料載入層 - 通用工具]
    負責將 DataFrame 寫入 SQLite 資料庫。
    只處理：
    1. 資料庫連線與寫入
    2. 日期欄位字串化 (SQLite 不支援 native date)
    3. 空值處理 (NaN -> NULL)
    4. 建立索引
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        # 確保目錄存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def load(self, df: pd.DataFrame, table_name: str, mode: Literal['append', 'delete_rows', 'fail', 'replace'] = 'replace', indices: Optional[List[str]] = None):
        """
        將 DataFrame 寫入 SQLite
        mode: 'replace' (全量覆蓋), 'append' (附加)
        indices: 欄位名稱列表，用於建立索引
        """
        if df.empty:
            logger.warning(f"⚠️ 沒有資料可寫入資料庫表 [{table_name}]。")
            return

        logger.info(f"💾 準備將 {len(df)} 筆資料寫入資料庫 ({self.db_path}) 表 [{table_name}]...")
        
        df_final = df.copy()

        # 1. 處理日期欄位，將 Pandas Timestamp 轉為純字串，避免 SQLite 報錯
        # 這裡採取通用的識別方式：欄位名稱包含 'date' 或 'month'
        for col in df_final.columns:
            if any(key in col.lower() for key in ['date', 'month']):
                try:
                    # 使用 format='mixed' 處理不同格式，errors='coerce' 將無法解析的轉為 NaT
                    dt_series = pd.to_datetime(df_final[col], format='mixed', errors='coerce')
                    if isinstance(dt_series, pd.Series):
                        df_final[col] = dt_series.dt.strftime('%Y-%m-%d')
                    else:
                        df_final[col] = pd.Series(dt_series).dt.strftime('%Y-%m-%d')
                except Exception as e:
                    logger.debug(f"跳過非日期欄位 {col}: {e}")

        # 2. 處理空值 (避免 SQL 寫入 NaN 變成 'NaN' 字串)
        # 統一將 NaN, NaT 轉為 None (SQL NULL)
        df_final = df_final.replace({pd.NA: None, float('nan'): None, 'nan': None})
        # 對於 datetime64 轉出來的 NaT，需要特別處理
        df_final = df_final.where(pd.notnull(df_final), None)

        # 3. 寫入 SQLite
        try:
            with sqlite3.connect(self.db_path) as conn:
                df_final.to_sql(table_name, conn, if_exists=mode, index=False)
                
                # 4. 建立索引 (Optimization)
                if indices:
                    cursor = conn.cursor()
                    for idx_col in indices:
                        if idx_col in df_final.columns:
                            # 判斷是否為 unique index (例如 transaction_id)
                            is_unique = "UNIQUE" if idx_col.endswith('_id') else ""
                            idx_name = f"idx_{table_name}_{idx_col}"
                            cursor.execute(f"CREATE {is_unique} INDEX IF NOT EXISTS {idx_name} ON {table_name} ({idx_col})")
                    conn.commit()
                
                # 5. 驗證
                cursor = conn.cursor()
                cursor.execute(f"SELECT count(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                logger.info(f"✅ 資料庫作業完成！資料表 [{table_name}] 目前共有 {count} 筆資料。")

        except Exception as e:
            logger.error(f"❌ 寫入資料庫失敗: {e}", exc_info=True)
            raise e
