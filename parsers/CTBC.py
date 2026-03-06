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
        df = self.read_csv_smart(filepath, self.encoding, self.header_keyword)
        if df.empty: return df

        df.columns = df.columns.astype(str).str.strip()
        available = [c for c in self.mapping.keys() if c in df.columns]
        df = df[available].rename(columns=self.mapping)
        df[const.COL_BANK_NAME] = self.bank_id
        
        df[const.COL_PAY_AMOUNT] = self._clean_amount(df, const.COL_PAY_AMOUNT)
        
        df = self.transform_common_dates(df, filepath)



        return df