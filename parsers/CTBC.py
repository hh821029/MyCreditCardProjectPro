import pandas as pd
import const
from .base import BaseCsvParser


class CTBCParser(BaseCsvParser):
    def __init__(self):
        self.bank_id = 'ctbc_bank'
        self.encoding = 'cp950' # 關鍵設定
        self.header_keyword = "消費日"
        self.stop_at_keyword = None
        
        self.mapping = {
            "消費日": const.COL_TXN_DATE,
            "入帳起息日": const.COL_POST_DATE,
            "摘要": const.COL_MERCHANT,
            "幣別": const.COL_CURRENCY,
            "消費地金額": const.COL_CURR_AMOUNT,
            "新臺幣金額": const.COL_PAY_AMOUNT,
            "末四碼": const.COL_CARD_NO,
            "外幣折算日": const.COL_CONV_DATE,
            "消費地": const.COL_LOCATION
        }

    def parse(self, filepath: str) -> pd.DataFrame:
        # 強制指定 "末四碼" 為字串，預防 Pandas 自動轉 float 造成 .0
        df = self.read_csv_smart(filepath, self.encoding, self.header_keyword)
        if df.empty: return df

        df.columns = df.columns.astype(str).str.strip()
        available = [c for c in self.mapping.keys() if c in df.columns]
        df = df[available].rename(columns=self.mapping)
        df[const.COL_BANK_NAME] = self.bank_id
        
        # 確保卡號欄位是乾淨的字串 (處理可能已產生的 .0)
        if const.COL_CARD_NO in df.columns:
            df[const.COL_CARD_NO] = df[const.COL_CARD_NO].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df[const.COL_PAY_AMOUNT] = self._clean_amount(df, const.COL_PAY_AMOUNT)
        
        df = self.transform_common_dates(df, filepath)
        
        # 最後強制執行一次型態檢查
        df = self._enforce_dtypes(df)

        return df
