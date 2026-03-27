# loaders/schema_enforcer.py
import pandas as pd
import numpy as np
import logging
import const

logger = logging.getLogger(__name__)

class SchemaEnforcer:
    """
    [型別執法模組]
    職責：根據 const.COLUMN_TYPES 強制規範 DataFrame 的資料型別。
    解決：Pandas 自動型別偵測導致的 float64 vs str 衝突、NaN 轉字串、浮點數尾巴等問題。
    """

    @staticmethod
    def enforce(df: pd.DataFrame) -> pd.DataFrame:
        """
        對傳入的 DataFrame 執行強制型別轉換
        """
        if df is None or df.empty:
            return df
            
        df_enforced = df.copy()
        
        for col_name, target_type in const.COLUMN_TYPES.items():
            # 只處理 DataFrame 裡實際存在的欄位
            if col_name not in df_enforced.columns:
                continue

            # --- 1. 處理數值 (Float) ---
            if target_type == 'float':
                # 如果是字串，先去逗號
                if df_enforced[col_name].dtype == 'object':
                    df_enforced[col_name] = df_enforced[col_name].astype(str).str.replace(',', '', regex=False)
                # 強制轉數值 (無法轉的變 NaN)
                df_enforced[col_name] = pd.to_numeric(df_enforced[col_name], errors='coerce')

            # --- 2. 處理字串 (String) ---
            elif target_type == 'str':
                # 先轉為字串，此時 1234.0 會變成 "1234.0"
                s = df_enforced[col_name].astype(str)
                
                # 修復浮點數格式 (只針對 "純數字.0" 進行修復，避免 1234 變成 "1234.0")
                s = s.str.replace(r'^(\d+)\.0$', r'\1', regex=True)
                
                # 去除前後空白
                s = s.str.strip()
                
                # 將 "nan", "None", "" 統一轉為真正的 None (object 型態下代表 NULL)
                # 這樣在寫入資料庫或進行比較時最穩定
                s = s.replace({'nan': None, 'None': None, '': None})
                
                df_enforced[col_name] = s

            # --- 3. 處理日期 (Date) ---
            elif target_type == 'date':
                # 確保轉換為 datetime64[ns]
                if not pd.api.types.is_datetime64_any_dtype(df_enforced[col_name]):
                    df_enforced[col_name] = pd.to_datetime(df_enforced[col_name], errors='coerce')

        return df_enforced

    @staticmethod
    def list_inconsistent_columns(df: pd.DataFrame):
        """
        [診斷用] 列出目前 DataFrame 中與 Schema 定義不符的欄位 (供開發者檢查)
        """
        inconsistencies = []
        for col_name, target_type in const.COLUMN_TYPES.items():
            if col_name in df.columns:
                current_dtype = str(df[col_name].dtype)
                # 簡單判定：如果是 float 但我們要 str，或者 object 但我們要 float
                if target_type == 'str' and 'float' in current_dtype:
                    inconsistencies.append(f"⚠️ {col_name}: Current={current_dtype}, Target=str")
                elif target_type == 'float' and 'object' in current_dtype:
                    inconsistencies.append(f"⚠️ {col_name}: Current={current_dtype}, Target=float")
        
        if inconsistencies:
            logger.warning("Detected schema inconsistencies:\n" + "\n".join(inconsistencies))
        return inconsistencies
