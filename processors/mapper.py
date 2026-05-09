# processors/mapper.py
import pandas as pd
import os
import logging
import const
import re

logger = logging.getLogger(__name__)

class CardMapper:
    def __init__(self, config_dir: str, rules: pd.DataFrame = None):
        if rules is not None and not rules.empty:
            self.rules = self._preprocess_rules(rules)
            logger.info(f"✅ CardMapper 已由外部載入 {len(self.rules)} 條規則")
        else:
            try:
                from loaders.config_loader import ConfigLoader
                df = ConfigLoader.load_config(config_dir, 'dim_cards', strategy='replace')
                self.rules = self._preprocess_rules(df)
                logger.info(f"✅ CardMapper 透過 ConfigLoader 載入 {len(self.rules)} 條規則")
            except ImportError:
                logger.warning("⚠️ 無法載入 ConfigLoader，改用基礎讀取邏輯")
                self.mapping_file = os.path.join(config_dir, 'dim_cards.csv') 
                self.rules = self._load_legacy_rules()

    def _preprocess_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗並預處理傳入的規則 DataFrame"""
        if df.empty:
            return df
            
        try:
            df.columns = df.columns.astype(str).str.strip()
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                if col in ['Card_No', '代換前卡號']:
                    df[col] = df[col].str.replace(r'\.0$', '', regex=True)
                    df[col] = df[col].str.replace(' ', '', regex=False)
            return df
        except Exception as e:
            logger.error(f"❌ 預處理卡片對照規則失敗: {e}")
            return pd.DataFrame()

    def _load_legacy_rules(self):
        """[備援] 舊版讀取邏輯"""
        if not hasattr(self, 'mapping_file') or not os.path.exists(self.mapping_file):
            return pd.DataFrame()
        try:
            df = pd.read_csv(self.mapping_file, keep_default_na=False)
            return self._preprocess_rules(df)
        except Exception as e:
            logger.error(f"❌ 讀取卡片對照表失敗: {e}")
            return pd.DataFrame()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        核心邏輯：
        1. 絕對粉碎機：清洗卡號 (去除 .0 與空白)
        2. 精準唯一比對：每一行規則僅有一個 Match Key (代換前卡號優先)
        3. 帳務排除：針對手續費、利息、折抵等非消費交易，不予標記行動支付標籤
        """
        if df.empty or const.COL_CARD_NO not in df.columns:
            return df
            
        # ==========================================
        # 1. 原始資料清洗
        # ==========================================
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].astype(str).str.strip()
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].str.replace(r'\.0$', '', regex=True)
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].str.replace(' ', '')
        
        df_card_clean = df[const.COL_CARD_NO].copy()

        if const.COL_MOBILE_PAY not in df.columns:
            df[const.COL_MOBILE_PAY] = '' 
        else:
            df[const.COL_MOBILE_PAY] = df[const.COL_MOBILE_PAY].fillna('')

        df_mobile_clean = df[const.COL_MOBILE_PAY].astype(str).str.strip()
        df_mobile_clean = df_mobile_clean.replace({'nan': '', 'None': ''})

        # ==========================================
        # 2. 帳務紀錄識別 (排除 Mask)
        # ==========================================
        exclude_keywords = ['手續費', '利息', '年費', '回饋', '繳款', '紅利折抵', '小樹點折抵', '退貨', '沖正']
        exclude_pattern = '|'.join(exclude_keywords)
        is_account_record = df[const.COL_MERCHANT].astype(str).str.contains(exclude_pattern, na=False)

        # ==========================================
        # 3. 規則比對 (精準唯一模式)
        # ==========================================
        for _, rule in self.rules.iterrows():
            # 使用 snake_case key
            target_card = rule.get('card_no', '')
            original_card = rule.get('代換前卡號', '')
            
            # --- 決定比對標的 (Match Key) ---
            match_key = original_card if (pd.notna(original_card) and original_card != '' and original_card.lower() != 'nan') else target_card
            
            if not match_key:
                continue
            
            # 精準比對 (Exact Matching)
            mask = (df_card_clean == match_key)
            
            # 銀行名稱篩選 (雙重保險)
            target_bank = rule.get('bank_name', '')
            if target_bank and target_bank.lower() != 'nan':
                if const.COL_BANK_NAME in df.columns:
                    mask = mask & (df[const.COL_BANK_NAME] == target_bank)

            if not mask.any():
                continue

            # ==========================================
            # 4. 寫入與正規化
            # ==========================================
            
            # (A) 卡號正規化與卡別
            df.loc[mask, const.COL_CARD_NO] = target_card
            
            val_type = rule.get('card_type')
            if pd.notna(val_type) and str(val_type).lower() != 'nan':
                df.loc[mask, const.COL_CARD_TYPE] = str(val_type).strip()

            # (B) 行動支付標籤與前綴
            eligible_mask = mask & (~is_account_record)
            
            if eligible_mask.any():
                # 行動支付標籤 (保留目前 CSV 中的名稱)
                val_mobile = rule.get('行動支付標籤')
                if pd.notna(val_mobile) and str(val_mobile).lower() != 'nan':
                    mobile_str = str(val_mobile).strip()
                    is_empty = eligible_mask & (df_mobile_clean == '')
                    if is_empty.any():
                        df.loc[is_empty, const.COL_MOBILE_PAY] = mobile_str
                        df_mobile_clean.loc[is_empty] = mobile_str

                # 前綴詞
                val_prefix = rule.get('加在消費明細摘要前方')
                if pd.notna(val_prefix) and str(val_prefix).lower() != 'nan':
                    prefix_str = str(val_prefix).strip()
                    if prefix_str:
                        df.loc[eligible_mask, '_Temp_Prefix'] = prefix_str
        
        return df
