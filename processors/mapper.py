# processors/mapper.py
import pandas as pd
import os
import logging
import const
import re

logger = logging.getLogger(__name__)

class CardMapper:
    def __init__(self, config_dir: str):
        self.mapping_file = os.path.join(config_dir, 'cards.csv') # 假設檔名
        self.rules = self._load_rules()

    def _load_rules(self):
        """讀取並預處理規則"""
        if not os.path.exists(self.mapping_file):
            logger.warning(f"⚠️ 找不到卡片對照表: {self.mapping_file}，將跳過歸戶邏輯")
            return pd.DataFrame()

        try:
            # 定義 schema 避免讀取錯誤
            schema = {
                '對應卡片': str, '卡號': str, '行動支付標籤': str,
                '加在消費明細摘要前方': str, '卡號代換': str
            }
            df = pd.read_csv(self.mapping_file, dtype=schema, keep_default_na=False)
            
            # 清洗規則中的空白
            for col in schema.keys():
                df[col] = df[col].str.strip()
                
            return df
        except Exception as e:
            logger.error(f"❌ 讀取卡片對照表失敗: {e}")
            return pd.DataFrame()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        核心邏輯：
        1. 絕對粉碎機：清洗卡號 (去除 .0 與空白)
        2. 精準比對：依據 cards.csv 設定
        3. 嚴格寫入：防止 nan 字串汙染，且不覆蓋既有的行動支付
        """
        if df.empty or const.COL_CARD_NO not in df.columns:
            return df
            
        match_count = 0
        
        # ==========================================
        # 1. 原始資料裝甲清洗 (絕對粉碎機)
        # ==========================================
        # 轉字串 -> 去頭尾空白 -> 消滅結尾的 .0 -> 移除所有空格
        # 效果：" 1234.0 " -> "1234"，"1234 / 5678" -> "1234/5678"
        df_card_clean = df[const.COL_CARD_NO].astype(str).str.strip()
        df_card_clean = df_card_clean.str.replace(r'\.0$', '', regex=True)
        df_card_clean = df_card_clean.str.replace(' ', '')
        
        # 預先準備好 Mobile Payment 欄位 (如果沒有就建立)
        if const.COL_MOBILE_PAY not in df.columns:
            df[const.COL_MOBILE_PAY] = None 

        # 準備 Mobile Payment 的清洗版 (用於判斷是否為空，避免覆蓋)
        # 將 nan 字串與 None 視為空值
        df_mobile_clean = df[const.COL_MOBILE_PAY].astype(str).str.strip()
        df_mobile_clean = df_mobile_clean.replace({'nan': '', 'None': ''})

        # ==========================================
        # 2. 規則比對 (Config-Driven)
        # ==========================================
        for _, rule in self.rules.iterrows():
            # (A) CSV 裡的目標卡號也做一模一樣的清洗
            target_card = str(rule.get('卡號', '')).strip()
            target_card = target_card.replace('.0', '').replace(' ', '')
            
            # 防呆：如果設定檔這行沒填卡號，跳過
            if not target_card or target_card.lower() == 'nan': 
                continue
            
            # 建立比對 Mask (卡號精準比對)
            mask = (df_card_clean == target_card)
            
            # (B) Bank ID 篩選 (只有當規則有寫 Bank ID 時才檢查)
            target_bank = str(rule.get('bank_id', '')).strip()
            # 修正：只有當 target_bank 真的是有效字串且不是 nan 時才過濾
            if target_bank and target_bank.lower() != 'nan':
                if const.COL_BANK_NAME in df.columns:
                    mask = mask & (df[const.COL_BANK_NAME] == target_bank)

            if not mask.any():
                continue
                
            match_count += mask.sum()

            # --- 寫入邏輯 (嚴格防範 nan) ---
            
            # 1. 卡別 (Card Type)
            val = rule.get('對應卡片')
            if pd.notna(val):
                type_str = str(val).strip()
                if type_str and type_str.lower() != 'nan':
                    df.loc[mask, const.COL_CARD_TYPE] = type_str

            # 2. 行動支付 (Mobile Payment) - Level 2 優先級
            # 策略：填空不覆蓋。如果 Parser (Level 3) 已經填了 Apple Pay，這裡就不動。
            val = rule.get('行動支付標籤')
            if pd.notna(val):
                mobile_str = str(val).strip()
                if mobile_str and mobile_str.lower() != 'nan':
                    # 找出「目前還是空值」的欄位
                    is_empty = mask & (df_mobile_clean == '')
                    if is_empty.any():
                        df.loc[is_empty, const.COL_MOBILE_PAY] = mobile_str
                        # 同步更新 clean series，避免同一張卡被後面的規則覆寫
                        df_mobile_clean.loc[is_empty] = mobile_str

            # 3. 前綴詞 (Prefix) - 絕對防禦 nan
            val = rule.get('加在消費明細摘要前方')
            if pd.notna(val):
                prefix_str = str(val).strip()
                # 嚴格檢查：不是空字串 且 不是 'nan'
                if prefix_str and prefix_str.lower() != 'nan':
                    df.loc[mask, '_Temp_Prefix'] = prefix_str

            # 4. 卡號代換 (Replacement)
            val = rule.get('卡號代換')
            if pd.notna(val):
                repl_str = str(val).strip()
                repl_str = repl_str.replace('.0', '') # 同樣要去掉 .0
                
                if repl_str and repl_str.lower() != 'nan':
                    df.loc[mask, const.COL_CARD_NO] = repl_str
                    # ⚠️ 關鍵：同步更新 df_card_clean，防止這筆資料在後續迴圈被舊卡號重複比對
                    df_card_clean.loc[mask] = repl_str
        
        return df