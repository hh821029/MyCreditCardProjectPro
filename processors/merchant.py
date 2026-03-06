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
    # ... (MerchantNormalizer 這一區塊保持不變，維持原樣) ...
    def __init__(self, config_dir: str):
        self.config_file = os.path.join(config_dir, 'merchants.csv')
        self.rules = self._load_rules()

    def _load_rules(self):
        if not os.path.exists(self.config_file):
            return pd.DataFrame()
        try:
            df = pd.read_csv(self.config_file)
            if 'Priority' in df.columns:
                df['Priority'] = pd.to_numeric(df['Priority'], errors='coerce').fillna(0)
                df = df.sort_values(by='Priority', ascending=False)
            return df
        except Exception as e:
            logger.error(f"❌ 讀取商家設定失敗: {e}")
            return pd.DataFrame()

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
    負責讀取 payment_gateway.csv
    執行：
    1. 識別支付管道 -> 填入 Mobile_Payment
    2. 產生前綴 -> 填入暫存欄位 _Temp_Prefix
    """
    def __init__(self, config_dir: str):
        self.config_file = os.path.join(config_dir, 'payment_gateway.csv')
        self.rules = self._load_rules()

    def _load_rules(self):
        if not os.path.exists(self.config_file):
            return pd.DataFrame()
        try:
            df = pd.read_csv(self.config_file)
            if 'Priority' in df.columns:
                df['Priority'] = pd.to_numeric(df['Priority'], errors='coerce').fillna(0)
                df = df.sort_values(by='Priority', ascending=False)
            return df
        except Exception:
            return pd.DataFrame()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.rules.empty or df.empty: return df

        # [修正 1] 初始化暫存欄位，並填滿空字串 (避免 NaN)
        if '_Temp_Prefix' not in df.columns:
            df['_Temp_Prefix'] = ''
        
        # [修正 2] 確保 Mobile_Payment 存在，並且將 NaN 轉為空字串 ''
        if const.COL_MOBILE_PAY not in df.columns:
            df[const.COL_MOBILE_PAY] = ''
        else:
            # 這是關鍵！把 NaN 變成 ''，讓後面的 (== '') 判斷生效
            df[const.COL_MOBILE_PAY] = df[const.COL_MOBILE_PAY].fillna('')

        merchants = df[const.COL_MERCHANT].astype(str).str.strip()
        
        for _, rule in self.rules.iterrows():
            pattern = rule['Pattern']
            prefix = rule.get('Prefix_Label')
            category = rule.get('Category') 
            
            if pd.isna(pattern): continue
            
            try:
                # 1. 匹配 Pattern
                mask = merchants.str.contains(pattern, case=False, regex=True, na=False)
                
                # 2. 條件：Mobile_Payment 必須為空
                #    (因為上面已經做過 fillna('')，這裡的判斷就安全了)
                target_mask = mask & (df[const.COL_MOBILE_PAY] == '')
                
                if target_mask.any():
                    # A. 填入 Mobile_Payment (例如 "Line Pay")
                    if pd.notna(category):
                        df.loc[target_mask, const.COL_MOBILE_PAY] = category
                    
                    # B. 填入暫存前綴 (例如 "LinePay－")
                    if pd.notna(prefix):
                        df.loc[target_mask, '_Temp_Prefix'] = prefix
                        
            except re.error:
                continue
                
        return df