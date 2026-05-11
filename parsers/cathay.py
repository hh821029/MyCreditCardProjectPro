import pandas as pd
import const
import re
import numpy as np
from .base import BaseCsvParser


class CubeParser(BaseCsvParser):
    def __init__(self):
        self.bank = const.Bank.CATHAY
        self.encoding = 'utf-8-sig'
        self.header_keyword = "消費日"
        self.stop_at_keyword = "正卡消費" # <--- YAML 設定在此生效
        
        self.mapping = {
            "消費日": const.COL_TXN_DATE,
            "入帳起息日": const.COL_POST_DATE,
            "交易說明": const.COL_MERCHANT,
            "消費國家/幣別": "Raw_Country_Currency", # 暫存欄位
            "消費金額": const.COL_CURR_AMOUNT,
            "新臺幣金額": const.COL_PAY_AMOUNT,
            "卡號/行動末四碼": const.COL_CARD_NO,
            "折算日": const.COL_CONV_DATE
        }

    def parse(self, filepath: str) -> pd.DataFrame:
        # 1. 讀取 (傳入 stop_at_keyword)
        df = self.read_csv_smart(filepath, self.encoding, self.header_keyword, self.stop_at_keyword)
        if df.empty: return df

        # 2. 標題清洗、欄位映射
        clean_headers = df.columns.astype(str).str.replace(' ', '').str.replace('\t', '')
        df.columns = clean_headers
        available = [c for c in self.mapping.keys() if c in df.columns]
        df = df[available].rename(columns=self.mapping)
        df[const.COL_BANK_NAME] = self.bank.bank_id

        # 3. 清洗國泰專屬的「偽空值」符號
        #    把獨立存在的 "-", "−", "－" 轉為真正的 NaN(修正成對應的空值型態)
        df = self._clean_cathay_null_symbols(df)
        
        # 4. 國泰專屬拆解 (國家/幣別)
        if "Raw_Country_Currency" in df.columns:
            split = df["Raw_Country_Currency"].astype(str).str.split('/', n=1, expand=True)
            if split.shape[1] >= 1:
                df[const.COL_LOCATION] = split[0].str.strip()
            if split.shape[1] >= 2:
                df[const.COL_CURRENCY] = split[1].str.strip()
            df = df.drop(columns=["Raw_Country_Currency"])

        # 5. 點數折抵預處理 (Pre-process Redemption)
        df = self._process_point_redemption(df)

        df[const.COL_PAY_AMOUNT] = self._clean_amount(df, const.COL_PAY_AMOUNT)

        # 6.呼叫父類別，並傳入 filepath (為了抓年份)
        df = self.transform_common_dates(df, filepath)
        
        # 7. 最終正規化 (補齊 TWD 等)
        df = self._finalize_normalization(df)

        return df
    
    def _clean_cathay_null_symbols(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        將國泰 CSV 中用來表示空值的橫槓符號轉為對應型別的空值。
        """
        pattern = r'^\s*[-−－—]\s*$'
        
        for col in df.columns:
            target_type = const.COLUMN_TYPES.get(col)
            # 建立遮罩：找出符合橫槓符號的儲存格
            mask = df[col].astype(str).str.contains(pattern, regex=True, na=False)
            
            if mask.any():
                if target_type == 'date':
                    df.loc[mask, col] = pd.NaT
                elif target_type == 'float':
                    df.loc[mask, col] = np.nan
                else:
                    # 包含 str 或未定義型別，統一用 None (在 Pandas Object 中代表 NULL)
                    df.loc[mask, col] = None
                    
        return df

    def _process_point_redemption(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        處理國泰特有的 "點數折抵＿XXXX" 格式
        目標：
        1. 標記 Transaction_Type 為 '紅利折抵' (統一標準)
        2. [直接覆蓋] 將 Merchant 統一改為 '小樹點折抵'
           (不論原本是折抵哪一家商店，對帳務來說這就是一筆點數折抵的紀錄)
        """
        if const.COL_MERCHANT not in df.columns: return df

        if const.COL_TXN_TYPE not in df.columns:
            df[const.COL_TXN_TYPE] = ''

        # 國泰的格式通常是 "點數折抵" 或 "點數折抵＿"
        pattern = r'^點數折抵[＿_]?\s*'
        mask = df[const.COL_MERCHANT].astype(str).str.contains(pattern, regex=True, na=False)

        if mask.any():
            # 1. 交易類型統一標記為 "紅利折抵"
            df.loc[mask, const.COL_TXN_TYPE] = '紅利折抵'

            # 2. 商家名稱直接統一改為 "小樹點折抵"
            #    不保留後面的商家名稱，因為這筆交易的本質就是點數使用
            df.loc[mask, const.COL_MERCHANT] = '小樹點折抵'

        return df