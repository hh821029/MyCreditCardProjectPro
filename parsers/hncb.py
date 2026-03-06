# parsers/hncb.py
import pandas as pd
import const
from .base import BaseHtmlParser # <--- 改繼承這個

class HNCBParser(BaseHtmlParser):
    def __init__(self):
        self.bank_id = 'hncb_bank'
        self.encoding = 'big5'      # 華南通常是 Big5
        self.header_keyword = "消費日"
        self.stop_at_keyword = "立即繳費" # 遇到這行就停止
        
        self.mapping = {
            "消費日": const.COL_TXN_DATE,
            "入帳日": const.COL_POST_DATE,
            "消費明細": const.COL_MERCHANT,
            "國別": const.COL_LOCATION,
            "幣別": const.COL_CURRENCY,
            "外幣金額": const.COL_CURR_AMOUNT, # 注意：華南欄位可能有空白，已被 BaseHtmlParser 清洗掉
            "新臺幣金額": const.COL_PAY_AMOUNT
        }
        # 卡號提取設定
        self.card_extraction_config = {
            'trigger': r'\*{12}', # Regex Trigger
            'card_no': r'\*{12}(\d{4})', # 抓星號後面的4碼
            'card_type': r'^(.*?)\*{12}' # 抓星號前面的文字 (即卡別)
        }

    def parse(self, filepath: str) -> pd.DataFrame:
        # 1. 讀取 (使用父類別方法)
        df = self.read_html_smart(
            filepath, 
            self.encoding, 
            self.header_keyword, 
            self.stop_at_keyword
        )
        
        if df.empty: return df

        # 2. 映射
        # 欄位名稱已經在 read_html_smart 清洗過去除空白了，直接對應即可
        available = [c for c in self.mapping.keys() if c in df.columns]
        df = df[available].rename(columns=self.mapping)
        df[const.COL_BANK_NAME] = self.bank_id

        # 3. 卡號提取邏輯 (_extract_card_info)
        df = self.extract_card_info_generic(df, self.card_extraction_config)
        
        # 4. 日期補全 (自動抓檔名年份)
        df = self.transform_common_dates(df, filepath)
        

        return df