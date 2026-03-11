# processors/mapper.py
import pandas as pd
import os
import logging
import const
import re

logger = logging.getLogger(__name__)

class CardMapper:
    def __init__(self, config_dir: str):
        self.mapping_file = os.path.join(config_dir, 'dim_cards.csv') 
        self.rules = self._load_rules()

    def _load_rules(self):
        """讀取並預處理規則"""
        if not os.path.exists(self.mapping_file):
            logger.warning(f"⚠️ 找不到卡片對照表: {self.mapping_file}，將跳過歸戶邏輯")
            return pd.DataFrame()

        try:
            # 讀取時不指定 dtype，讓 pd.read_csv 自動讀取後我們再手動清洗
            df = pd.read_csv(self.mapping_file, keep_default_na=False)
            
            # 1. 清洗欄位名稱
            df.columns = df.columns.astype(str).str.strip()
            
            # 2. 清洗資料內容 (轉為字串、去空白、去除 .0)
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                # 特別針對 Card_No 欄位再做一次 .0 的徹底清除
                if col == 'Card_No':
                    df[col] = df[col].str.replace(r'\.0$', '', regex=True)
                
            return df
        except Exception as e:
            logger.error(f"❌ 讀取卡片對照表失敗: {e}")
            return pd.DataFrame()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        核心邏輯：
        1. 絕對粉碎機：清洗卡號 (去除 .0 與空白)
        2. 精準比對：依據 dim_cards.csv 設定
        3. 嚴格寫入：標記卡別、行動支付、摘要前綴
        """
        if df.empty or const.COL_CARD_NO not in df.columns:
            return df
            
        # ==========================================
        # 1. 原始資料裝甲清洗 (絕對粉碎機)
        # ==========================================
        # 確保 df 中的卡號也是乾淨的 (去除 .0, 空白)
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].astype(str).str.strip()
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].str.replace(r'\.0$', '', regex=True)
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].str.replace(' ', '')
        
        # 準備暫存的清洗 Series 用於比對 (避免多次計算)
        df_card_clean = df[const.COL_CARD_NO]

        # 預先準備好 Mobile Payment 欄位
        if const.COL_MOBILE_PAY not in df.columns:
            df[const.COL_MOBILE_PAY] = '' 
        else:
            df[const.COL_MOBILE_PAY] = df[const.COL_MOBILE_PAY].fillna('')

        # 準備 Mobile Payment 的清洗版 (用於判斷是否為空，避免覆蓋)
        df_mobile_clean = df[const.COL_MOBILE_PAY].astype(str).str.strip()
        df_mobile_clean = df_mobile_clean.replace({'nan': '', 'None': ''})

        # ==========================================
        # 2. 規則比對 (Config-Driven)
        # ==========================================
        for _, rule in self.rules.iterrows():
            # (A) 取得規則中的比對卡號
            target_card = rule.get('Card_No', '')
            if not target_card or target_card.lower() == 'nan': 
                continue
            
            # 建立比對 Mask
            mask = (df_card_clean == target_card)
            
            # (B) Bank ID 篩選 (對應 Bank_Name 欄位)
            target_bank = rule.get('Bank_Name', '')
            if target_bank and target_bank.lower() != 'nan':
                if const.COL_BANK_NAME in df.columns:
                    mask = mask & (df[const.COL_BANK_NAME] == target_bank)

            if not mask.any():
                continue

            # --- 寫入邏輯 ---
            
            # 1. 卡別 (Card Type) -> 對應 Card_Type
            val_type = rule.get('Card_Type')
            if pd.notna(val_type) and str(val_type).lower() != 'nan':
                df.loc[mask, const.COL_CARD_TYPE] = str(val_type).strip()

            # 2. 行動支付 (Mobile Payment) -> 對應 行動支付標籤
            val_mobile = rule.get('行動支付標籤')
            if pd.notna(val_mobile) and str(val_mobile).lower() != 'nan':
                mobile_str = str(val_mobile).strip()
                # 策略：填空不覆蓋
                is_empty = mask & (df_mobile_clean == '')
                if is_empty.any():
                    df.loc[is_empty, const.COL_MOBILE_PAY] = mobile_str
                    df_mobile_clean.loc[is_empty] = mobile_str

            # 3. 前綴詞 (Prefix) -> 對應 加在消費明細摘要前方
            val_prefix = rule.get('加在消費明細摘要前方')
            if pd.notna(val_prefix) and str(val_prefix).lower() != 'nan':
                prefix_str = str(val_prefix).strip()
                if prefix_str:
                    df.loc[mask, '_Temp_Prefix'] = prefix_str
        
        return df
