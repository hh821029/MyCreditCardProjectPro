# processors/mapper.py
import pandas as pd
import os
import logging
import const
import re
from typing import Optional

logger = logging.getLogger(__name__)

class CardMapper:
    def __init__(self, config_dir: str, rules: Optional[pd.DataFrame] = None):
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
        2. [新增] 雙卡號拆解：針對 "NNNN / MMMM" 格式，提取虛擬卡號 (MMMM) 進行查詢 (XLOOKUP 邏輯)
        3. 規則比對：精準唯一比對
        4. 帳務排除：針對手續費、利息、折抵等非消費交易，不予標記行動支付標籤
        """
        if df.empty or const.COL_CARD_NO not in df.columns:
            return df
            
        # ==========================================
        # 1. 原始資料清洗與欄位初始化
        # ==========================================
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].astype(str).str.strip()
        df[const.COL_CARD_NO] = df[const.COL_CARD_NO].str.replace(r'\.0$', '', regex=True)
        # 注意：此處不直接移除所有空白，以便處理 " / " 分隔符
        
        if const.COL_MOBILE_PAY not in df.columns:
            df[const.COL_MOBILE_PAY] = '' 
        else:
            df[const.COL_MOBILE_PAY] = df[const.COL_MOBILE_PAY].fillna('')

        if const.COL_VPC_NO not in df.columns:
            df[const.COL_VPC_NO] = ''
        if const.COL_VPC_TYPE not in df.columns:
            df[const.COL_VPC_TYPE] = ''

        df_mobile_clean = df[const.COL_MOBILE_PAY].astype(str).str.strip()
        df_mobile_clean = df_mobile_clean.replace({'nan': '', 'None': ''})

        # ==========================================
        # 2. 帳務紀錄識別 (排除 Mask)
        # ==========================================
        exclude_keywords = ['手續費', '利息', '年費', '回饋', '繳款', '紅利折抵', '小樹點折抵', '退貨', '沖正']
        exclude_pattern = '|'.join(exclude_keywords)
        is_account_record = df[const.COL_MERCHANT].astype(str).str.contains(exclude_pattern, na=False)

        # ==========================================
        # 3. 核心比對邏輯 (逐列處理以應對複雜邏輯)
        # ==========================================
        
        # 建立 vpc_no 索引以便快速查詢 (XLOOKUP 基礎)
        vpc_lookup = self.rules[self.rules['vpc_no'].fillna('') != ''].set_index('vpc_no')
        
        for idx, card_val in df[const.COL_CARD_NO].items():
            card_str = str(card_val)
            match_rule = None
            
            # --- A. 處理雙卡號 (NNNN / MMMM) ---
            if ' / ' in card_str:
                parts = [p.strip() for p in card_str.split('/')]
                # 國泰格式：實體卡 / 虛擬卡
                if len(parts) >= 2:
                    physical_part = parts[0]
                    virtual_part = parts[1]
                    
                    # 執行 XLOOKUP：查詢 vpc_no
                    if virtual_part in vpc_lookup.index:
                        match_rule = vpc_lookup.loc[virtual_part]
                        if isinstance(match_rule, pd.DataFrame):
                            match_rule = match_rule.iloc[0]
                        
                        # 更新當前行資訊
                        df.at[idx, const.COL_CARD_NO] = physical_part
                        df.at[idx, const.COL_VPC_NO] = virtual_part
                        logger.debug(f"🔍 雙卡號匹配成功: {virtual_part} -> {match_rule.get('vpc_type')}")
            
            # --- B. 處理一般卡號匹配 (若尚未由雙卡號成功匹配) ---
            if match_rule is None:
                clean_card = card_str.replace(' ', '')
                # 比對 代換前卡號 或 card_no
                cond = (self.rules['代換前卡號'] == clean_card) | (self.rules['card_no'] == clean_card)
                matches = self.rules[cond]
                if not matches.empty:
                    match_rule = matches.iloc[0]
            
            # ==========================================
            # 4. 寫入比對結果
            # ==========================================
            if match_rule is not None:
                # 實體卡號與卡別
                target_card = match_rule.get('card_no', '')
                if target_card:
                    df.at[idx, const.COL_CARD_NO] = str(target_card).replace('.0', '')
                
                val_type = match_rule.get('card_type')
                if pd.notna(val_type) and str(val_type).lower() != 'nan':
                    df.at[idx, const.COL_CARD_TYPE] = str(val_type).strip()

                # vpc_type (OEM Pay 類型)
                val_vpc_type = match_rule.get('vpc_type')
                if pd.notna(val_vpc_type) and str(val_vpc_type).lower() != 'nan':
                    df.at[idx, const.COL_VPC_TYPE] = str(val_vpc_type).strip()

                # 行動支付標籤與前綴 (排除帳務紀錄)
                if not is_account_record[idx]:
                    # 分離邏輯：若已有 vpc_type (OEM Pay)，則不填入 mobile_payment (第三方支付)
                    current_vpc = df.at[idx, const.COL_VPC_TYPE]
                    if not current_vpc:
                        val_mobile = match_rule.get('行動支付標籤')
                        if pd.notna(val_mobile) and str(val_mobile).lower() != 'nan':
                            df.at[idx, const.COL_MOBILE_PAY] = str(val_mobile).strip()

                    # 前綴詞
                    val_prefix = match_rule.get('加在消費明細摘要前方')
                    if pd.notna(val_prefix) and str(val_prefix).lower() != 'nan':
                        prefix_str = str(val_prefix).strip()
                        if prefix_str:
                            df.at[idx, '_Temp_Prefix'] = prefix_str
        
        return df
