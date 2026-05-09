# processors/merchant.py
import pandas as pd
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
        # 確保 Merchant_Display 存在，初始值等於原始 Merchant
        if const.COL_MERCHANT_DISPLAY not in df.columns:
            df[const.COL_MERCHANT_DISPLAY] = df[const.COL_MERCHANT]
        
        merchants = df[const.COL_MERCHANT].astype(str).str.strip()
        
        for _, rule in self.rules.iterrows():
            # 優先使用 snake_case 與當前 CSV 標題
            pattern = rule.get('pattern')
            replacement = rule.get('merchant') or rule.get('merchant_display')
            category = rule.get('category')
            
            if pd.isna(pattern) or pattern == '': continue

            try:
                mask = merchants.str.contains(pattern, case=False, regex=True, na=False)
            except re.error:
                continue

            if mask.any():
                target_mask = mask & df[const.COL_CATEGORY].isna()
                if target_mask.any():
                    if pd.notna(replacement) and replacement != '':
                        # 修改 Merchant_Display 而非 Merchant
                        df.loc[target_mask, const.COL_MERCHANT_DISPLAY] = replacement
                    if pd.notna(category) and category != '':
                        df.loc[target_mask, const.COL_CATEGORY] = category
        return df


class PaymentProcessTagger:
    """
    負責標記支付管道或處理方式 (如 LinePay, 街口, 自動扣款)
    """
    def __init__(self, config_dir: str, rules: pd.DataFrame = None):
        """
        :param rules: 由外部注入的規則 DataFrame (包含 payment_process_pattern, process_prefix, payment_process)
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
            # 使用新的統一命名規範
            pattern = rule.get(const.COL_PROCESS_PATTERN) or rule.get('payment_process_pattern')
            prefix = rule.get(const.COL_PROCESS_PREFIX) or rule.get('process_prefix')
            process_name = rule.get(const.COL_PAYMENT_PROCESS) or rule.get('payment_process')
            
            if pd.isna(pattern) or pattern == '': continue
            
            try:
                mask = merchants.str.contains(pattern, case=False, regex=True, na=False)
                target_mask = mask & (df[const.COL_MOBILE_PAY] == '')
                
                if target_mask.any():
                    if pd.notna(process_name):
                        df.loc[target_mask, const.COL_MOBILE_PAY] = process_name
                    
                    if pd.notna(prefix):
                        df.loc[target_mask, '_Temp_Prefix'] = prefix
                        
            except re.error:
                continue
                
        return df
