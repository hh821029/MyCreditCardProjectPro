# processors/merchant.py
import pandas as pd
import os
import logging
import re
import const
import warnings

warnings.filterwarnings("ignore", "This pattern is interpreted as a regular expression, and has match groups")
logger = logging.getLogger(__name__)

class MerchantNormalizer:
    def __init__(self, config_dir: str, rules: pd.DataFrame = None):
        """
        商戶名稱正規化處理器
        :param rules: 由外部注入的規則 DataFrame (包含 Pattern, Replacement, Category)
        """
        # 如果沒有傳入規則，則初始化為空，不再自行讀檔
        self.rules = rules if rules is not None else pd.DataFrame()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.rules.empty or df.empty: return df

        if const.COL_CATEGORY not in df.columns: df[const.COL_CATEGORY] = None
        
        merchants = df[const.COL_MERCHANT].astype(str).str.strip()
        
        for _, rule in self.rules.iterrows():
            pattern = rule['Pattern']
            replacement = rule['Replacement']
            category = rule['Category']
            
            if pd.isna(pattern) or pattern == '': continue

            try:
                mask = merchants.str.contains(pattern, case=False, regex=True, na=False)
            except re.error:
                continue

            if mask.any():
                target_mask = mask & df[const.COL_CATEGORY].isna()
                if target_mask.any():
                    if pd.notna(replacement) and replacement != '':
                        df.loc[target_mask, const.COL_MERCHANT] = replacement
                    if pd.notna(category) and category != '':
                        df.loc[target_mask, const.COL_CATEGORY] = category
        return df


class PaymentGatewayTagger:
    """
    負責標記支付管道 (如 LinePay, 街口)
    """
    def __init__(self, config_dir: str, rules: pd.DataFrame = None):
        """
        :param rules: 由外部注入的規則 DataFrame (包含 Pattern, Prefix_Label, Category)
        """
        self.rules = rules if rules is not None else pd.DataFrame()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.rules.empty or df.empty: return df

        if '_Temp_Prefix' not in df.columns:
            df['_Temp_Prefix'] = ''
        
        if const.COL_MOBILE_PAY not in df.columns:
            df[const.COL_MOBILE_PAY] = ''
        else:
            df[const.COL_MOBILE_PAY] = df[const.COL_MOBILE_PAY].fillna('')

        merchants = df[const.COL_MERCHANT].astype(str).str.strip()
        
        for _, rule in self.rules.iterrows():
            pattern = rule['Pattern']
            prefix = rule.get('Prefix_Label')
            category = rule.get('Category') 
            
            if pd.isna(pattern): continue
            
            try:
                mask = merchants.str.contains(pattern, case=False, regex=True, na=False)
                target_mask = mask & (df[const.COL_MOBILE_PAY] == '')
                
                if target_mask.any():
                    if pd.notna(category):
                        df.loc[target_mask, const.COL_MOBILE_PAY] = category
                    
                    if pd.notna(prefix):
                        df.loc[target_mask, '_Temp_Prefix'] = prefix
                        
            except re.error:
                continue
                
        return df
