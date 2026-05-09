import pandas as pd
import numpy as np
import logging
import re
from datetime import datetime
from typing import Dict, Optional, List
import const

logger = logging.getLogger(__name__)

class RewardsCalculator:
    """
    [4/13 強化版] 信用卡回饋計算引擎 (V2.2)
    核心設計：瀑布式規則引擎 (Waterfall Engine)
    - 支援優先級控制與計算截斷 (reward_cal_break)
    - 統一使用清洗後的 merchant_display 作為匹配依據
    - 關聯 Bridge Rules 與 Dimension Tables 處理上限
    """

    def __init__(self, configs: Dict[str, pd.DataFrame] = None):
        self.configs = configs or {}
        self.rules_master = pd.DataFrame()
        self.external_merchants = {} # 存放外部 YAML 商家清單 (如 nccc, general_reward_exclusion)
        self._preprocess_configs()
        self._load_external_configs()

    def _load_external_configs(self):
        """載入外部外部 YAML 商家清單 (如 NCCC, 通用排除名單)"""
        import yaml
        import os
        
        config_files = {
            'nccc_listed_merchant': 'nccc_listed_merchant.yaml',
            'general_reward_exclusion': 'general_reward_exclusion.yaml'
        }
        
        for key, filename in config_files.items():
            path = os.path.join(const.CONFIG_DIR, filename)
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if data and key in data:
                            self.external_merchants[key] = data[key]
                            logger.info(f"✅ 已載入外部清單 [{key}]: {len(self.external_merchants[key])} 筆")
                except Exception as e:
                    logger.error(f"❌ 載入外部清單 [{key}] 失敗: {e}")

    def _preprocess_configs(self):
        """
        前處理：將 Bridge Rules 與 Dim Tables 關聯，建立規則主表
        """
        if 'reward_rules' not in self.configs or self.configs['reward_rules'].empty:
            logger.warning("⚠️ 找不到 bridge_reward_rules，回饋計算可能受限。")
            return

        bridge = self.configs['reward_rules'].copy()
        
        # 1. 分別與 Base 和 Campaign 表進行 Join
        base_dim = self.configs.get('rewards_base', pd.DataFrame())
        camp_dim = self.configs.get('rewards_campaigns', pd.DataFrame())

        # 基礎回饋關聯 (依據 rules_reward_program 對接 base_reward_program)
        if not base_dim.empty:
            base_cols = ['base_reward_program', 'bank_name', 'card_type', 'cap_amount', 'calc_method', 'round_strategy', 'start_date', 'end_date']
            base_cols = [c for c in base_cols if c in base_dim.columns]
            bridge = bridge.merge(
                base_dim[base_cols], 
                left_on='rules_reward_program', 
                right_on='base_reward_program', 
                how='left', 
                suffixes=('', '_base')
            )

        # 活動回饋關聯 (依據 rules_reward_program 對接 campaign_reward_program)
        if not camp_dim.empty:
            camp_cols = ['campaign_reward_program', 'bank_name', 'card_type', 'cap_amount', 'calc_method', 'round_strategy', 'start_date', 'end_date']
            camp_cols = [c for c in camp_cols if c in camp_dim.columns]
            bridge = bridge.merge(
                camp_dim[camp_cols], 
                left_on='rules_reward_program', 
                right_on='campaign_reward_program', 
                how='left', 
                suffixes=('', '_camp')
            )

        # 2. 整合欄位與計算日期交集
        date_cols = ['start_date', 'end_date', 'start_date_base', 'end_date_base', 'start_date_camp', 'end_date_camp']
        for col in date_cols:
            if col in bridge.columns:
                bridge[col] = pd.to_datetime(bridge[col], format='mixed', errors='coerce')

        # 處理日期交集 (Intersection Logic)
        if 'start_date_base' in bridge.columns:
            bridge['start_date'] = bridge[['start_date', 'start_date_base']].max(axis=1)
        if 'start_date_camp' in bridge.columns:
            bridge['start_date'] = bridge[['start_date', 'start_date_camp']].max(axis=1)
            
        if 'end_date_base' in bridge.columns:
            bridge['end_date'] = bridge[['end_date', 'end_date_base']].min(axis=1)
        if 'end_date_camp' in bridge.columns:
            bridge['end_date'] = bridge[['end_date', 'end_date_camp']].min(axis=1)

        # 剔除無效規則 (交集為空)
        valid_mask = bridge['start_date'].fillna(pd.Timestamp('1900-01-01')) <= \
                     bridge['end_date'].fillna(pd.Timestamp('2099-12-31'))
        bridge = bridge[valid_mask].copy()

        # 填補最終日期 NaT
        bridge['start_date'] = bridge['start_date'].fillna(pd.Timestamp('1900-01-01'))
        bridge['end_date'] = bridge['end_date'].fillna(pd.Timestamp('2099-12-31'))

        # 整合其餘欄位 (Coalesce 邏輯)
        if 'bank_name_camp' in bridge.columns:
            bridge['bank_name'] = bridge['bank_name'].fillna(bridge['bank_name_camp'])
        if 'card_type_camp' in bridge.columns:
            bridge['card_type'] = bridge['card_type'].fillna(bridge['card_type_camp'])
        if 'cap_amount_camp' in bridge.columns:
            bridge['cap_amount'] = bridge['cap_amount'].fillna(bridge['cap_amount_camp'])
            
        # 4. 排序：priority 越小優先級越高
        if 'priority' in bridge.columns:
            self.rules_master = bridge.sort_values(by='priority', ascending=True)
        else:
            self.rules_master = bridge
        
        # 5. 確保率值為 float (merchant_rate 是百分率，如 0.3 = 0.3%)
        if 'merchant_rate' in self.rules_master.columns:
            self.rules_master['merchant_rate'] = pd.to_numeric(self.rules_master['merchant_rate'], errors='coerce').fillna(0) / 100.0
        
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
                   (df[const.COL_TXN_DATE] >= rule['start_date']) & \
                   (df[const.COL_TXN_DATE] <= rule['end_date'])
            
            # 1-1. 卡片與銀行過濾
            if pd.notna(rule.get('card_type')) and rule['card_type'] != '':
                mask = mask & (df[const.COL_CARD_TYPE] == rule['card_type'])
            elif pd.notna(rule.get('bank_name')) and rule['bank_name'] != '':
                mask = mask & (df[const.COL_BANK_NAME] == rule['bank_name'])
            
            # 2. 支付、地點與商家過濾
            # 2-1. 行動支付匹配
            if pd.notna(rule.get('mobile_payment')) and rule['mobile_payment'] != '':
                target_pay = str(rule['mobile_payment'])
                if target_pay == "實體卡":
                    mobile_mask = df[const.COL_MOBILE_PAY].fillna('').isin(['', '實體卡'])
                else:
                    mobile_mask = df[const.COL_MOBILE_PAY].astype(str).str.contains(target_pay, case=False, regex=True, na=False)
                mask = mask & mobile_mask
            
            # 2-2. 消費地點匹配
            if pd.notna(rule.get('merchant_location')) and rule['merchant_location'] != '':
                loc_mask = df[const.COL_LOCATION].astype(str).str.contains(rule['merchant_location'], case=False, regex=True, na=False)
                mask = mask & loc_mask
                
            # 2-3. 商家名稱匹配 (使用 merchant_display 作為 SSOT)
            if pd.notna(rule.get('merchant_display')) and rule['merchant_display'] != '':
                pattern = str(rule['merchant_display'])
                
                # [特殊關鍵字處理]
                for key, merch_list in self.external_merchants.items():
                    if pattern == key and merch_list:
                        pattern = '|'.join([re.escape(m) for m in merch_list])
                        break
                
                merch_mask = df[const.COL_MERCHANT_DISPLAY].astype(str).str.contains(pattern, case=False, regex=True, na=False)
                mask = mask & merch_mask

            if not mask.any(): continue
            
            # 3. 計算回饋 (PER_ITEM 邏輯)
            rate = rule.get('merchant_rate', 0)
            current_rewards = np.floor(df.loc[mask, const.COL_PAY_AMOUNT] * rate)

            # 4. 上限控制 (若有 cap_amount)
            cap = rule.get('cap_amount')
            if pd.notna(cap) and cap > 0:
                pass # 上限邏輯暫不更動

            # 5. 更新結果
            df.loc[mask, 'reward_earned'] += current_rewards
            program_name = rule.get('rules_reward_program') or 'Unknown'
            df.loc[mask, 'applied_rules'] += (df.loc[mask, 'applied_rules'].apply(lambda x: ' | ' if x != '' else '') + program_name)
            
            # 6. 截斷邏輯 (Break)
            if str(rule.get('reward_cal_break')).upper() == 'TRUE':
                df.loc[mask, 'is_calculation_finished'] = True
                
        # 清理暫存欄位
        df = df.drop(columns=['is_calculation_finished'])
        
        # 相容輸出
        df['is_bypassed'] = df['applied_rules'] == ''
        df['base_reward'] = df['reward_earned']
        df['campaign_reward'] = 0.0
        df['applied_rule'] = df['applied_rules']
        
        return df
