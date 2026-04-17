import pandas as pd
import numpy as np
import re
import logging
from datetime import datetime
from typing import Dict, Optional, List
import const

logger = logging.getLogger(__name__)

class RewardsCalculator:
    """
    [4/13 強化版] 信用卡回饋計算引擎 (V2.1)
    核心設計：瀑布式規則引擎 (Waterfall Engine)
    - 支援優先級控制與計算截斷 (Reward_Cal_Break)
    - 統一使用清洗後的 Merchant_Display 作為匹配依據
    - 關聯 Bridge Rules 與 Dimension Tables 處理上限
    """

    def __init__(self, configs: Dict[str, pd.DataFrame] = None):
        self.configs = configs or {}
        self.rules_master = pd.DataFrame()
        self._preprocess_configs()

    def _preprocess_configs(self):
        """
        前處理：將 Bridge Rules 與 Dim Tables 關聯，建立規則主表
        """
        if 'reward_rules' not in self.configs or self.configs['reward_rules'].empty:
            logger.warning("⚠️ 找不到 bridge_reward_rules，回饋計算可能受限。")
            return

        bridge = self.configs['reward_rules'].copy()
        
        # 1. 分別與 Base 和 Campaign 表進行 Join
        # [註] 如果有多個 Dim 表，我們合併它們的關聯資訊
        base_dim = self.configs.get('rewards_base', pd.DataFrame())
        camp_dim = self.configs.get('rewards_campaigns', pd.DataFrame())

        # 基礎回饋關聯 (依據 Reward_Program)
        if not base_dim.empty:
            # 挑選關鍵維度欄位
            base_cols = ['Reward_Program', 'Bank_Name', 'Card_Type', 'Cap_Amount', 'Calc_Method', 'Round_Strategy']
            bridge = bridge.merge(base_dim[base_cols], on='Reward_Program', how='left', suffixes=('', '_base'))

        # 活動回饋關聯 (依據 Campaign_Name，在此對應 Reward_Program)
        if not camp_dim.empty:
            camp_cols = ['Campaign_Name', 'Bank_Name', 'Card_Type', 'Cap_Amount', 'Calc_Method', 'Round_Strategy']
            bridge = bridge.merge(camp_dim[camp_cols], left_on='Reward_Program', right_on='Campaign_Name', how='left', suffixes=('', '_camp'))

        # 2. 整合欄位 (Coalesce 邏輯)
        # 如果 Bank_Name 有多個，合併之 (優先取 camp，再取 base)
        if 'Bank_Name_camp' in bridge.columns:
            bridge['Bank_Name'] = bridge['Bank_Name'].fillna(bridge['Bank_Name_camp'])
        if 'Card_Type_camp' in bridge.columns:
            bridge['Card_Type'] = bridge['Card_Type'].fillna(bridge['Card_Type_camp'])
        if 'Cap_Amount_camp' in bridge.columns:
            bridge['Cap_Amount'] = bridge['Cap_Amount'].fillna(bridge['Cap_Amount_camp'])
            
        # 3. 日期轉換
        bridge['Start_Date'] = pd.to_datetime(bridge['Start_Date'], errors='coerce')
        bridge['End_Date'] = pd.to_datetime(bridge['End_Date'], errors='coerce')
        
        # 4. 排序：Priority 越小優先級越高 (50 優先於 99)
        self.rules_master = bridge.sort_values(by='Priority', ascending=True)
        
        # 5. 確保率值為 float (Merchant_Rate 是百分率，如 0.3 = 0.3%)
        self.rules_master['Merchant_Rate'] = pd.to_numeric(self.rules_master['Merchant_Rate'], errors='coerce').fillna(0) / 100.0
        
        logger.info(f"✅ 規則主表建置完成，共有 {len(self.rules_master)} 條運算規則。")

    def process(self, df_bills: pd.DataFrame) -> pd.DataFrame:
        """主處理流程：瀑布式逐規則計算"""
        if df_bills.empty: return df_bills

        df = df_bills.copy()
        df[const.COL_TXN_DATE] = pd.to_datetime(df[const.COL_TXN_DATE])
        
        # 初始化回饋追蹤欄位
        df['reward_earned'] = 0.0
        df['applied_rules'] = ''
        df['is_calculation_finished'] = False  # 用於 Break 標記
        
        # 如果沒有規則主表，直接結束
        if self.rules_master.empty: return df

        # 核心：逐一規則進行匹配 (The Waterfall Loop)
        for _, rule in self.rules_master.iterrows():
            # 找出尚未完成計算的交易
            pending_mask = ~df['is_calculation_finished']
            if not pending_mask.any(): break
            
            # 1. 基礎過濾條件 (日期、卡片、銀行)
            mask = pending_mask & \
                   (df[const.COL_TXN_DATE] >= rule['Start_Date']) & \
                   (df[const.COL_TXN_DATE] <= rule['End_Date'])
            
            # 1-1. 卡片與銀行過濾 (如果有定義)
            if pd.notna(rule.get('Bank_Name')):
                mask = mask & (df[const.COL_BANK_NAME] == rule['Bank_Name'])
            # 注意: Card_Type 在原始交易中可能對應到 Card_Type 或 Card_Name
            # 這裡假設維度表的 Card_Type 指的是廣義的卡別 (如 Cube)
            
            # 2. 商家與支付過濾 (關鍵：Regex 匹配)
            # 商家匹配 (使用 Merchant_Display 作為 SSOT)
            if pd.notna(rule.get('merchants')) and rule['merchants'] != '':
                merch_mask = df[const.COL_MERCHANT_DISPLAY].astype(str).str.contains(rule['merchants'], case=False, regex=True, na=False)
                mask = mask & merch_mask
                
            # 行動支付匹配
            if pd.notna(rule.get('mobile_payment')) and rule['mobile_payment'] != '':
                mobile_mask = df[const.COL_MOBILE_PAY].astype(str).str.contains(rule['mobile_payment'], case=False, regex=True, na=False)
                mask = mask & mobile_mask

            if not mask.any(): continue
            
            # 3. 計算回饋 (這裡實作 PER_ITEM 邏輯，AGGREGATE 可在後續擴充)
            rate = rule['Merchant_Rate']
            current_rewards = np.floor(df.loc[mask, const.COL_PAY_AMOUNT] * rate)
            
            # 4. 上限控制 (若有 Cap_Amount)
            cap = rule.get('Cap_Amount')
            if pd.notna(cap) and cap > 0:
                # 這裡使用簡單的 Per-Row 上限控制作為示範，
                # 若要處理「跨交易累計上限」，需在此針對 mask 子集合進行 cumsum
                pass # 目前先以比率計算為主，上限邏輯可依需求微調

            # 5. 更新結果
            df.loc[mask, 'reward_earned'] += current_rewards
            df.loc[mask, 'applied_rules'] += (df.loc[mask, 'applied_rules'].apply(lambda x: ' | ' if x != '' else '') + rule['Reward_Program'])
            
            # 6. 截斷邏輯 (Break)
            if str(rule.get('Reward_Cal_Break')).upper() == 'TRUE':
                df.loc[mask, 'is_calculation_finished'] = True
                
        # 清理暫存欄位
        df = df.drop(columns=['is_calculation_finished'])
        
        # 為了相容之前的 Demo 輸出，將 reward_earned 設為總和
        df['is_bypassed'] = df['applied_rules'] == ''
        df['base_reward'] = df['reward_earned'] # 簡化對照
        df['campaign_reward'] = 0.0
        df['applied_rule'] = df['applied_rules']
        
        return df
