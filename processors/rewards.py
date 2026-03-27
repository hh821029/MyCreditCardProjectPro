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
    信用卡回饋計算引擎 (V2)
    遵循 GEMINI.md 規範：支援日期篩選、加碼活動匹配、計算策略切換與上限控制。
    """

    def __init__(self, configs: Dict[str, pd.DataFrame] = None):
        self.configs = configs or {}
        # 確保日期格式正確
        self._preprocess_configs()

    def _preprocess_configs(self):
        """對設定檔進行前處理，如日期轉換"""
        if 'rewards_campaigns' in self.configs:
            df = self.configs['rewards_campaigns']
            if not df.empty:
                df['Start_Date'] = pd.to_datetime(df['Start_Date'])
                df['End_Date'] = pd.to_datetime(df['End_Date'])
                self.configs['rewards_campaigns'] = df

    def process(self, df_bills: pd.DataFrame) -> pd.DataFrame:
        """主處理流程"""
        if df_bills.empty:
            return df_bills

        df = df_bills.copy()
        df[const.COL_TXN_DATE] = pd.to_datetime(df[const.COL_TXN_DATE])
        
        # 初始化回饋欄位
        df['is_bypassed'] = False
        df['reward_earned'] = 0.0
        df['applied_rule'] = 'NONE'
        df['base_reward'] = 0.0
        df['campaign_reward'] = 0.0

        # Stage 1: 全域排除 (Global Exclusions)
        df = self.apply_global_exclusions(df)
        
        # Stage 2: 基礎回饋計算 (Base Rewards)
        df = self.calculate_base_rewards(df)
        
        # Stage 3: 短期活動加碼 (Campaign Rewards)
        df = self.calculate_campaign_rewards(df)
        
        # 最終匯總
        df['reward_earned'] = df['base_reward'] + df['campaign_reward']
        
        return df

    def apply_global_exclusions(self, df: pd.DataFrame) -> pd.DataFrame:
        """利用 Regex 檢驗是否落入全域排除名單"""
        # [註] 未來可從 transaction_types.yaml 或 dim_merchants 讀取排除標籤
        exclusion_pattern = r'.*(台灣電力公司|自來水|瓦斯|中華電信|停車費|管理費|醫指付|全國繳費網|麥當勞|肯德基|爭鮮|全聯|PXGo|7-11|7-ELEVEN|全家|萊爾富|OK超商|綜合所得稅|房屋稅|地價稅|使用牌照稅|營業稅|循環息|違約金|年費|手續費|預借現金|悠遊卡自動加值|一卡通自動加值|icash自動加值).*'
        
        mask = df[const.COL_MERCHANT].astype(str).str.contains(exclusion_pattern, na=False)
        
        if mask.any():
            df.loc[mask, 'is_bypassed'] = True
            df.loc[mask, 'applied_rule'] = 'GLOBAL_EXCLUSION'
            
        return df

    def calculate_base_rewards(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算基礎回饋 (如：一般消費 1%)"""
        if 'rewards_base' not in self.configs or self.configs['rewards_base'].empty:
            return df
            
        # 這裡僅實作簡單邏輯示範，未來應依據 bank_name/card_name 進行 merge
        # 假設預設一般消費為 1%
        mask = (~df['is_bypassed'])
        # 修正: 使用 np.floor 而非 .floor()
        df.loc[mask, 'base_reward'] = np.floor(df.loc[mask, const.COL_AMOUNT] * 0.01)
        df.loc[mask, 'applied_rule'] = 'BASE_1%'
        
        return df

    def calculate_campaign_rewards(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        實作活動加碼邏輯
        """
        if 'rewards_campaigns' not in self.configs or self.configs['rewards_campaigns'].empty:
            return df
            
        campaigns = self.configs['rewards_campaigns']
        
        for _, row in campaigns.iterrows():
            camp_name = row['Campaign_Name']
            start_date = row['Start_Date']
            end_date = row['End_Date']
            # 確保倍率為 float
            rate = float(row['Reward_Rate'])
            cap = row.get('Cap_Amount', np.inf)
            calc_method = row.get('Calc_Method', 'PER_ITEM')
            
            # 篩選符合條件的交易
            mask = (df[const.COL_TXN_DATE] >= start_date) & \
                   (df[const.COL_TXN_DATE] <= end_date) & \
                   (~df['is_bypassed'])
            
            if not mask.any():
                continue
                
            if calc_method == 'PER_ITEM':
                # 修正: 使用 np.floor
                current_rewards = np.floor(df.loc[mask, const.COL_AMOUNT] * rate)
            else:
                total_amount = df.loc[mask, const.COL_AMOUNT].sum()
                total_reward = np.floor(total_amount * rate)
                current_rewards = (df.loc[mask, const.COL_AMOUNT] / total_amount) * total_reward
            
            # 上限控制 (利用 cumsum)
            cum_reward = current_rewards.cumsum()
            allowed_reward = current_rewards.copy()
            
            # 找出超過上限的轉折點
            over_mask = cum_reward > cap
            if over_mask.any():
                # 剛好超過的那一筆，補足差額
                first_over_idx = over_mask.idxmax()
                prev_cum = cum_reward.shift(1).fillna(0)
                allowed_reward.loc[over_mask] = 0
                allowed_reward.loc[first_over_idx] = max(0, cap - prev_cum.loc[first_over_idx])
            
            # 更新到主表
            df.loc[mask, 'campaign_reward'] += allowed_reward
            df.loc[mask, 'applied_rule'] += f" | {camp_name}"
            
        return df
