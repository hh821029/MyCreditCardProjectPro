import pandas as pd
import numpy as np
import re
import logging
from datetime import datetime
from typing import Dict, Optional
import const

logger = logging.getLogger(__name__)

class RewardsCalculator:
    """
    信用卡回饋計算引擎
    引入多維度規則表：
    1. bridge_cube_selections: 國泰 CUBE 權益切換紀錄
    2. bridge_reward_rules: 規則與商戶/支付管道的對照橋接
    3. dim_card_rewards_base: 基礎權益定義
    4. dim_card_rewards_campaigns: 短期加碼活動定義
    5. dim_merchants: 商戶正規化規則 (含私有檔)
    6. dim_payment_gateway: 支付管道規則
    """

    def __init__(self, configs: Dict[str, pd.DataFrame] = None):
        self.configs = configs or {}
        
    def _prepare_rules(self) -> pd.DataFrame:
        """
        [預留] 合併基礎權益與短期活動，並依優先級排序。
        """
        return pd.DataFrame()

    def process(self, df_bills: pd.DataFrame) -> pd.DataFrame:
        """主處理流程"""
        if df_bills.empty:
            return df_bills

        df = df_bills.copy()
        
        # 初始化回饋欄位
        df['is_bypassed'] = False
        df['reward_earned'] = 0.0
        df['applied_rule'] = 'NONE'

        # Stage 1: 全域排除 (如：手續費、稅款)
        df = self.apply_global_exclusions(df)
        
        # Stage 2: 國泰 CUBE 權益標註 (註解備用)
        # Stage 3: 滾動計算回饋與上限
        df = self.calculate_rolling_rewards(df)
        
        return df

    def apply_global_exclusions(self, df: pd.DataFrame) -> pd.DataFrame:
        """利用 Regex 檢驗是否落入全域排除名單"""
        exclusion_pattern = r'.*(台灣電力公司|自來水|瓦斯|中華電信|停車費|管理費|醫指付|全國繳費網|麥當勞|肯德基|爭鮮|全聯|PXGo|7-11|7-ELEVEN|全家|萊爾富|OK超商|綜合所得稅|房屋稅|地價稅|使用牌照稅|營業稅|循環息|違約金|年費|手續費|預借現金|悠遊卡自動加值|一卡通自動加值|icash自動加值).*'
        
        mask = df[const.COL_MERCHANT].astype(str).str.contains(exclusion_pattern, na=False)
        
        if mask.any():
            df.loc[mask, 'is_bypassed'] = True
            df.loc[mask, 'reward_earned'] = 0.0
            df.loc[mask, 'applied_rule'] = 'GLOBAL_EXCLUSION'
            
        return df

    def calculate_rolling_rewards(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        針對正常交易，依時間排序後套用規則，並計算回饋上限。
        """
        return df
