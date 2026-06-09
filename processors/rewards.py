import pandas as pd
import numpy as np
import logging
import re
import yaml
import os
from datetime import datetime
from typing import Dict, Optional, List
import const

logger = logging.getLogger(__name__)

class RewardsCalculator:
    """
    [V3.0] 信用卡回饋計算引擎 (Phase 1 完整重設)
    核心設計：分層瀑布式規則引擎 (Layered Waterfall Engine)
    
    ## 架構改進
    1. **Base vs Campaign 分離**: 
       - base_rules_master: 同一筆交易僅套用 1 條 (有 Break)
       - campaign_rules_master: 支援多條堆疊 (無 Break)
    
    2. **多層 Base 解析**:
       - Layer 1: Card-Type 特定 Base (e.g., "Cube卡一般消費")
       - Layer 2: Bank-level Base (e.g., "國泰銀一般消費")
       - Layer 3: Global Base (e.g., "一般消費")
       - Layer 4: None (rate=0)
    
    3. **權益選擇支援**:
       - Cube 卡: 依交易日期查詢 bridge_cube_selections_private.csv
       - Unicard: 依交易日期查詢 bridge_unicard_selections_private.csv
    
    4. **卡片啟用檢查**:
       - enable_reward_calc from dim_cards_private.csv
       - 預過濾已結束的卡片
    
    ## 關鍵約束 (Critical Constraint)
    - 一筆交易 = 一張卡 = 一個 Base Rule (同層不可多套)
    - 多張活動可堆疊在 Base 之上 (Campaign stacking)
    """

    def __init__(self, configs: Optional[Dict[str, pd.DataFrame]] = None):
        # Phase 0: config_db connection
        #self.config_db = const.CONFIGS_DB_PATH
        #self.conn_config = sqlite3.connect(self.config_db)

        self.configs = configs or {}
        
        # Phase 1: Base Rules (Waterfall with Break scope to Base layer)
        self.base_rules_master = pd.DataFrame()
        
        # Phase 4: Campaign Rules (No Break, full stacking)
        self.campaign_rules_master = pd.DataFrame()
        
        # External merchant lists (YAML)
        self.external_merchants = {}
        
        # Equity selections for special cards
        self.selections = {}  # {'cube': df, 'unicard': df}
        
        # Card activation status
        self.card_enable_status = pd.DataFrame()
        
        self._preprocess_configs()
        self._load_external_configs()
        self._load_selections()
        self._load_card_enable_status()

    def _load_external_configs(self):
        """載入外部 YAML 商家清單 (如 NCCC, 通用排除名單)"""
        
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

    def _load_selections(self):
        """載入動態權益選擇表與活動區間 (如 Cube, Unicard, Uniopen 等)"""
        for key, df in self.configs.items():
            if 'selection' in key.lower() or 'visit_spots' in key.lower():
                if df.empty:
                    continue
                try:
                    sel_df = df.copy()
                    if 'start_date' in sel_df.columns:
                        sel_df['start_date'] = pd.to_datetime(sel_df['start_date'], format='mixed', errors='coerce')
                    if 'end_date' in sel_df.columns:
                        sel_df['end_date'] = pd.to_datetime(sel_df['end_date'], format='mixed', errors='coerce')
                    
                    # 尋找可以作為 target_program 的欄位 (支援多個同時存在)
                    target_cols = [col for col in ['reward_program', 'campaign_name', 'base_reward_program', 'campaign_reward_program', 'rules_reward_program'] if col in sel_df.columns]
                            
                    if target_cols:
                        # 透過 melt (解樞紐) 將多個 program 欄位垂直合併為一欄 target_program
                        id_vars = [col for col in sel_df.columns if col not in target_cols]
                        melted_df = sel_df.melt(id_vars=id_vars, value_vars=target_cols, value_name='target_program')
                        
                        # 清理空值
                        melted_df = melted_df.dropna(subset=['target_program'])
                        melted_df = melted_df[melted_df['target_program'].astype(str).str.strip() != '']
                        
                        self.selections[key] = melted_df
                        logger.info(f"✅ 已載入動態區間選擇表 [{key}]: 展開後共 {len(melted_df)} 筆有效選擇")
                except Exception as e:
                    logger.error(f"❌ 載入動態區間選擇表 [{key}] 失敗: {e}")

    def _load_card_enable_status(self):
        """從 dim_cards 載入卡片啟用狀態"""
        try:
            cards_df = None
            if 'dim_cards' in self.configs:
                cards_df = self.configs['dim_cards']
            elif 'dim_cards_private' in self.configs:
                cards_df = self.configs['dim_cards_private']
                
            if cards_df is not None and not cards_df.empty:
                key_col = 'card_type' if 'card_type' in cards_df.columns else 'card_name'
                if key_col in cards_df.columns and 'enable_reward_calc' in cards_df.columns:
                    self.card_enable_status = cards_df[[key_col, 'enable_reward_calc']].drop_duplicates().set_index(key_col)
                    enabled_count = (self.card_enable_status['enable_reward_calc'] == True).sum()
                    logger.info(f"✅ 已載入卡片啟用狀態: {enabled_count}/{len(self.card_enable_status)} 卡片啟用")
        except Exception as e:
            logger.error(f"❌ 載入卡片啟用狀態失敗: {e}")

    def _concat_configs(self, prefix: str) -> pd.DataFrame:
        """輔助函式：合併 configs 中所有符合前綴的表單"""
        if prefix in self.configs:
            return self.configs[prefix]
            
        dfs = []
        for key, df in self.configs.items():
            if key.startswith(prefix) and isinstance(df, pd.DataFrame) and not df.empty:
                dfs.append(df)
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


    def _apply_dynamic_date_intersection(self, rules_df: pd.DataFrame, program_col: str) -> pd.DataFrame:
        """將規則表與所有載入的動態區間選擇表 (selections) 進行日期交集展開"""
        if rules_df.empty or not self.selections:
            return rules_df
            
        all_sels = []
        for _, sel_df in self.selections.items():
            if 'target_program' in sel_df.columns:
                sel = sel_df[['target_program', 'start_date', 'end_date']].copy()
                sel.rename(columns={'start_date': 'sel_start', 'end_date': 'sel_end'}, inplace=True)
                all_sels.append(sel)
                
        if not all_sels:
            return rules_df
            
        combined_sel = pd.concat(all_sels, ignore_index=True).dropna(subset=['target_program'])
        if combined_sel.empty:
            return rules_df
            
        combined_sel = combined_sel.drop_duplicates(subset=['target_program', 'sel_start', 'sel_end'])
        dynamic_programs = combined_sel['target_program'].unique()
        
        # [關鍵優化]：同時檢查 program_col (維度表) 以及 rules_reward_program (橋接表)
        has_rules_col = 'rules_reward_program' in rules_df.columns
        mask_dynamic_prog = rules_df[program_col].isin(dynamic_programs)
        mask_dynamic_rule = rules_df['rules_reward_program'].isin(dynamic_programs) if has_rules_col else pd.Series(False, index=rules_df.index)
        
        mask_dynamic = mask_dynamic_prog | mask_dynamic_rule
        
        df_static = rules_df[~mask_dynamic].copy()
        df_dynamic = rules_df[mask_dynamic].copy()
        
        if df_dynamic.empty:
            return rules_df
            
        # 定義 match_key 以便後續進行 inner join 獲取區間
        def get_match_key(row):
            if has_rules_col and row.get('rules_reward_program') in dynamic_programs:
                return row.get('rules_reward_program')
            if row.get(program_col) in dynamic_programs:
                return row.get(program_col)
            return None

        df_dynamic['match_key'] = df_dynamic.apply(get_match_key, axis=1)
        
        df_dynamic_merged = df_dynamic.merge(
            combined_sel,
            left_on='match_key',
            right_on='target_program',
            how='inner'
        )
        
        df_dynamic_merged['start_date'] = df_dynamic_merged[['start_date', 'sel_start']].max(axis=1, skipna=True)
        df_dynamic_merged['end_date'] = df_dynamic_merged[['end_date', 'sel_end']].min(axis=1, skipna=True)
        
        # 向量化篩選：僅保留 start_date <= end_date 的有效交集
        valid_date_mask = (df_dynamic_merged['start_date'].isna()) | (df_dynamic_merged['end_date'].isna()) | (df_dynamic_merged['start_date'] <= df_dynamic_merged['end_date'])
        df_dynamic_merged = df_dynamic_merged[valid_date_mask]
        df_dynamic_merged.drop(columns=['sel_start', 'sel_end', 'target_program', 'match_key'], errors='ignore', inplace=True)
        
        return pd.concat([df_static, df_dynamic_merged], ignore_index=True)

    def _preprocess_configs(self):
        """
        前處理：分離 Base Rules 與 Campaign Rules
        - Base Rules: rules_reward_program 來自 dim_card_rewards_base
        - Campaign Rules: rules_reward_program 來自 dim_card_rewards_campaigns
        """
        bridge = self._concat_configs('reward_rules')
        if bridge.empty:
            logger.warning("⚠️ 找不到 bridge_reward_rules，回饋計算可能受限。")
            return
        
        # 取得 Base 和 Campaign 維度表 (支援自動合併 _private 等附屬表單)
        base_dim = self._concat_configs('rewards_base')
        camp_dim = self._concat_configs('rewards_campaigns')

        # === Base Rules 分離 ===
        if not base_dim.empty:
            base_dim = base_dim.copy()
            base_dim['start_date'] = pd.to_datetime(base_dim['start_date'], format='mixed', errors='coerce')
            base_dim['end_date'] = pd.to_datetime(base_dim['end_date'], format='mixed', errors='coerce')
            
            # 只保留關聯到 Base 的規則 (join on rules_reward_program = base_reward_program)
            base_rules = bridge.merge(
                base_dim[['base_reward_program', 'bank_name', 'card_type', 'cap_amount', 'calc_method', 'round_strategy', 'start_date', 'end_date', 'base_reward_rate']],
                left_on='rules_reward_program',
                right_on='base_reward_program',
                how='inner',
                suffixes=('_rule', '_base')
            )
            
            if not base_rules.empty:
                # 整合日期 (交集)
                if 'start_date_rule' in base_rules.columns and 'start_date_base' in base_rules.columns:
                    base_rules['start_date'] = pd.DataFrame({
                        'rule': base_rules['start_date_rule'],
                        'base': base_rules['start_date_base']
                    }).max(axis=1, skipna=True)
                if 'end_date_rule' in base_rules.columns and 'end_date_base' in base_rules.columns:
                    base_rules['end_date'] = pd.DataFrame({
                        'rule': base_rules['end_date_rule'],
                        'base': base_rules['end_date_base']
                    }).min(axis=1, skipna=True)
                
                # 篩選無效日期區間 (交集為空，即 start_date > end_date)
                valid_date_mask = (base_rules['start_date'].isna()) | (base_rules['end_date'].isna()) | (base_rules['start_date'] <= base_rules['end_date'])
                base_rules = base_rules[valid_date_mask]
                assert isinstance(base_rules, pd.DataFrame)
                
                # 排序 (priority 越小越高)
                if 'priority' in base_rules.columns:
                    base_rules_priority = pd.to_numeric(base_rules['priority'], errors='coerce')
                    if isinstance(base_rules_priority, pd.Series):
                        base_rules['priority'] = base_rules_priority.fillna(999)
                    else:
                        base_rules['priority'] = 999 if pd.isna(base_rules_priority) else base_rules_priority
                    base_rules = base_rules.sort_values(by='priority', ascending=True)
                
                # 確保 merchant_rate 為百分比

                if 'merchant_rate' in base_rules.columns:
                    m_rate = pd.Series(pd.to_numeric(base_rules['merchant_rate'], errors='coerce'), index=base_rules.index)
                    b_rate = pd.Series(pd.to_numeric(base_rules['base_reward_rate'], errors='coerce'), index=base_rules.index) if 'base_reward_rate' in base_rules.columns else pd.Series(np.nan, index=base_rules.index)
                    resolved_rate = m_rate.fillna(b_rate).fillna(0.0)
                    base_rules['merchant_rate'] = resolved_rate / 100.0
                
                base_rules = self._apply_dynamic_date_intersection(base_rules, 'base_reward_program')
                self.base_rules_master = base_rules
                logger.info(f"✅ Base Rules 載入完成 (含動態展開): {len(self.base_rules_master)} 條")
        else:
            self.base_rules_master = pd.DataFrame()

        # === Campaign Rules 分離 ===
        if not camp_dim.empty:
            camp_dim = camp_dim.copy()
            camp_dim['start_date'] = pd.to_datetime(camp_dim['start_date'], format='mixed', errors='coerce')
            camp_dim['end_date'] = pd.to_datetime(camp_dim['end_date'], format='mixed', errors='coerce')
            
            # 只保留關聯到 Campaign 的規則
            camp_rules = bridge.merge(
                camp_dim[['campaign_reward_program', 'bank_name', 'card_type', 'cap_amount', 'calc_method', 'round_strategy', 'start_date', 'end_date', 'campaign_reward_rate']],
                left_on='rules_reward_program',
                right_on='campaign_reward_program',
                how='inner',
                suffixes=('_rule', '_camp')
            )
            
            if not camp_rules.empty:
                # 整合日期
                if 'start_date_rule' in camp_rules.columns and 'start_date_camp' in camp_rules.columns:
                    camp_rules['start_date'] = pd.DataFrame({
                        'rule': camp_rules['start_date_rule'],
                        'camp': camp_rules['start_date_camp']
                    }).max(axis=1, skipna=True)
                if 'end_date_rule' in camp_rules.columns and 'end_date_camp' in camp_rules.columns:
                    camp_rules['end_date'] = pd.DataFrame({
                        'rule': camp_rules['end_date_rule'],
                        'camp': camp_rules['end_date_camp']
                    }).min(axis=1, skipna=True)
                
                # 篩選無效日期區間 (交集為空，即 start_date > end_date)
                valid_date_mask = (camp_rules['start_date'].isna()) | (camp_rules['end_date'].isna()) | (camp_rules['start_date'] <= camp_rules['end_date'])
                camp_rules = camp_rules[valid_date_mask]
                assert isinstance(camp_rules, pd.DataFrame)
                
                # 排序
                if 'priority' in camp_rules.columns:
                    camp_rules_priority = pd.to_numeric(camp_rules['priority'], errors='coerce')
                    if isinstance(camp_rules_priority, pd.Series):
                        camp_rules['priority'] = camp_rules_priority.fillna(999)
                    else:
                        camp_rules['priority'] = 999 if pd.isna(camp_rules_priority) else camp_rules_priority
                    camp_rules = camp_rules.sort_values(by='priority', ascending=True)
                
                # 確保 merchant_rate 為百分比

                if 'merchant_rate' in camp_rules.columns:
                    m_rate = pd.Series(pd.to_numeric(camp_rules['merchant_rate'], errors='coerce'), index=camp_rules.index)
                    c_rate = pd.Series(pd.to_numeric(camp_rules['campaign_reward_rate'], errors='coerce'), index=camp_rules.index) if 'campaign_reward_rate' in camp_rules.columns else pd.Series(np.nan, index=camp_rules.index)
                    resolved_rate = m_rate.fillna(c_rate).fillna(0.0)
                    camp_rules['merchant_rate'] = resolved_rate / 100.0
                
                camp_rules = self._apply_dynamic_date_intersection(camp_rules, 'campaign_reward_program')
                self.campaign_rules_master = camp_rules
                logger.info(f"✅ Campaign Rules 載入完成 (含動態展開): {len(self.campaign_rules_master)} 條")
        else:
            self.campaign_rules_master = pd.DataFrame()

        # === 全局規則整合 (Global Rule Integration) ===
        all_rules = []
        if not self.base_rules_master.empty:
            base_df = self.base_rules_master.copy()
            base_df['is_base_rule'] = True
            base_df['is_campaign_rule'] = False
            base_df.rename(columns={'merchant_rate': 'final_rate'}, inplace=True)
            all_rules.append(base_df)

        if not self.campaign_rules_master.empty:
            camp_df = self.campaign_rules_master.copy()
            camp_df['is_base_rule'] = False
            camp_df['is_campaign_rule'] = True
            camp_df.rename(columns={'merchant_rate': 'final_rate'}, inplace=True)
            all_rules.append(camp_df)

        if all_rules:
            self.all_rules_master = pd.concat(all_rules, ignore_index=True)
            self.all_rules_master = self.all_rules_master.sort_values(by='priority', ascending=True)
            logger.info(f"✅ 全局規則整合完成: {len(self.all_rules_master)} 條，已按全局 priority 排序")
            
            # [暫時資料輸出] 輸出至 output/all_rules_master_sorted.csv 供檢查
            try:
                output_rules_path = os.path.join(const.OUTPUT_DIR, 'all_rules_master_sorted.csv')
                self.all_rules_master.to_csv(output_rules_path, index=False, encoding='utf-8-sig')
                logger.info(f"💾 已將全局規則表輸出至: {output_rules_path}")
            except Exception as e:
                logger.error(f"❌ 輸出全局規則表失敗: {e}")
        else:
            self.all_rules_master = pd.DataFrame()
            
    def _should_calculate_reward(self, card_name: str) -> bool:
        """檢查該卡片是否應該計算回饋"""
        if self.card_enable_status.empty:
            return True  # 如果未載入狀態表，預設啟用
        
        if card_name in self.card_enable_status.index:
            return self.card_enable_status.loc[card_name, 'enable_reward_calc'] == True
        
        return True  # 未找到的卡片預設啟用

    def _match_rule(self, row: pd.Series, rule: pd.Series) -> bool:
        """
        檢查單筆交易是否符合某條規則
        
        檢查項:
        - 日期範圍
        - 卡片類型
        - 銀行
        - 行動支付
        - 消費地點
        - 商家名稱
        """
        # 日期檢查
        txn_date = row[const.COL_TXN_DATE]
        if pd.notna(rule.get('start_date')) and txn_date < rule['start_date']:
            return False
        if pd.notna(rule.get('end_date')) and txn_date > rule['end_date']:
            return False
        
        # 卡片檢查
        if pd.notna(rule.get('card_type')) and rule['card_type'] != '':
            if row[const.COL_CARD_TYPE] != rule['card_type']:
                return False
        elif pd.notna(rule.get('bank_name')) and rule['bank_name'] != '':
            if row[const.COL_BANK_NAME] != rule['bank_name']:
                return False
        
        # 行動支付檢查
        if pd.notna(rule.get('mobile_payment')) and rule['mobile_payment'] != '':
            target_pay = str(rule['mobile_payment'])
            if target_pay == "實體卡":
                is_physical = (pd.isna(row[const.COL_MOBILE_PAY]) or row[const.COL_MOBILE_PAY] == '') and \
                              (pd.isna(row[const.COL_VPC_TYPE]) or row[const.COL_VPC_TYPE] == '')
                if not is_physical:
                    return False
            else:
                mobile_match = pd.notna(row[const.COL_MOBILE_PAY]) and \
                               str(row[const.COL_MOBILE_PAY]).find(target_pay) >= 0
                vpc_match = pd.notna(row[const.COL_VPC_TYPE]) and \
                            str(row[const.COL_VPC_TYPE]).find(target_pay) >= 0
                if not (mobile_match or vpc_match):
                    return False
        
        # VPC Type 獨立檢查 (OEM Pay 特定檢查)
        #if pd.notna(rule.get('vpc_type')) and rule['vpc_type'] != '':
        #    target_vpc = str(rule['vpc_type'])
        #    if pd.isna(row.get(const.COL_VPC_TYPE)) or row.get(const.COL_VPC_TYPE) == '':
        #        return False
        #    if str(row.get(const.COL_VPC_TYPE)).find(target_vpc) < 0:
        #        return False
                
        # EC Platform 獨立檢查 (網購平台檢查)
        if pd.notna(rule.get('ec_platform')) and rule['ec_platform'] != '':
            target_ec = str(rule['ec_platform'])
            row_ec = str(row.get(const.COL_EC_PLATFORM, '')) if pd.notna(row.get(const.COL_EC_PLATFORM)) else ''
            if target_ec.upper() == 'ANY' or target_ec == '*':
                if row_ec.strip() == '':  # 只要不是空的 (代表是網購) 就過關
                    return False
            elif row_ec.find(target_ec) < 0:
                return False
        
        # 消費地點檢查
        if pd.notna(rule.get('merchant_location')) and rule['merchant_location'] != '':
            if pd.isna(row[const.COL_LOCATION]) or row[const.COL_LOCATION] == '':
                return False
            if str(row[const.COL_LOCATION]).find(rule['merchant_location']) < 0:
                return False
        
        # 商家名稱檢查
        if pd.notna(rule.get('merchant_display')) and rule['merchant_display'] != '':
            merchant_name = str(row[const.COL_MERCHANT_DISPLAY])
            pattern = str(rule['merchant_display'])
            
            # 外部清單代理
            for key, merch_list in self.external_merchants.items():
                if pattern == key and merch_list:
                    # 檢查是否在外部清單中
                    if merchant_name in merch_list:
                        return True
                    return False
            
            # 直接字串搜尋
            if merchant_name.find(pattern) < 0:
                return False
        
        return True

    def _diagnose_match_failure(self, row: pd.Series, base_program: Optional[str]) -> str:
        """
        診斷交易為何未匹配任何規則（is_bypassed=True 時調用）
    
        返回失敗原因，例如：
        - "base_program 為 None (未找到卡片對應的 Base Program)"
        - "該 base_program 無規則定義"
        - "規則日期範圍不符: 交易日期 2024-04-26 超出範圍"
        - "規則商家名稱不符: 規則要求含'家樂福'，實際為'家樂福'"
        """
        if base_program is None:
            return "無任何規則匹配 (新架構下此為通用訊息)"
    
        # 檢查該 base_program 是否有相關規則
        base_rules_for_prog = self.base_rules_master[
            self.base_rules_master['rules_reward_program'] == base_program
        ]
        
        if base_rules_for_prog.empty:
            return f"base_program '{base_program}' 無規則定義"
        
        # 逐一檢查每條規則的匹配條件
        txn_date = row[const.COL_TXN_DATE]
        
        for _, rule in base_rules_for_prog.iterrows():
            failure_reasons = []
            
            # 日期檢查
            if pd.notna(rule.get('start_date')) and txn_date < rule['start_date']:
                failure_reasons.append(f"交易日期{txn_date.date()}早於規則開始日期{rule['start_date'].date()}")
            if pd.notna(rule.get('end_date')) and txn_date > rule['end_date']:
                failure_reasons.append(f"交易日期{txn_date.date()}晚於規則結束日期{rule['end_date'].date()}")
            
            # 卡片檢查
            if pd.notna(rule.get('card_type')) and rule['card_type'] != '':
                if row[const.COL_CARD_TYPE] != rule['card_type']:
                    failure_reasons.append(f"卡片類型不符: 規則要求'{rule['card_type']}'，實際為'{row[const.COL_CARD_TYPE]}'")
            elif pd.notna(rule.get('bank_name')) and rule['bank_name'] != '':
                if row[const.COL_BANK_NAME] != rule['bank_name']:
                    failure_reasons.append(f"銀行不符: 規則要求'{rule['bank_name']}'，實際為'{row[const.COL_BANK_NAME]}'")
            
            # 行動支付檢查
            if pd.notna(rule.get('mobile_payment')) and rule['mobile_payment'] != '':
                target_pay = str(rule['mobile_payment'])
                if target_pay == "實體卡":
                    is_physical = (pd.isna(row[const.COL_MOBILE_PAY]) or row[const.COL_MOBILE_PAY] == '') and \
                                (pd.isna(row[const.COL_VPC_TYPE]) or row[const.COL_VPC_TYPE] == '')
                    if not is_physical:
                        failure_reasons.append(f"支付方式不符: 規則要求'實體卡'，交易實際為非實體卡")
                else:
                    mobile_pay_value = str(row.get(const.COL_MOBILE_PAY, '')) if pd.notna(row.get(const.COL_MOBILE_PAY)) else ''
                    vpc_type_value = str(row.get(const.COL_VPC_TYPE, '')) if pd.notna(row.get(const.COL_VPC_TYPE)) else ''
                    
                    mobile_match = mobile_pay_value and mobile_pay_value.find(target_pay) >= 0
                    vpc_match = vpc_type_value and vpc_type_value.find(target_pay) >= 0
                    
                    if not (mobile_match or vpc_match):
                        failure_reasons.append(f"行動支付不符: 規則要求含'{target_pay}'，實際 mobile_payment='{mobile_pay_value}' vpc_type='{vpc_type_value}'")
            
            # VPC Type 獨立檢查
            if pd.notna(rule.get('vpc_type')) and rule['vpc_type'] != '':
                target_vpc = str(rule['vpc_type'])
                vpc_val = str(row.get(const.COL_VPC_TYPE, '')) if pd.notna(row.get(const.COL_VPC_TYPE)) else ''
                if vpc_val == '':
                    failure_reasons.append(f"VPC支付不符: 規則要求'{target_vpc}'，實際為空")
                elif vpc_val.find(target_vpc) < 0:
                    failure_reasons.append(f"VPC支付不符: 規則要求'{target_vpc}'，實際為'{vpc_val}'")
            
            # EC Platform 獨立檢查
            if pd.notna(rule.get('ec_platform')) and rule['ec_platform'] != '':
                target_ec = str(rule['ec_platform'])
                ec_val = str(row.get(const.COL_EC_PLATFORM, '')) if pd.notna(row.get(const.COL_EC_PLATFORM)) else ''
                if target_ec.upper() == 'ANY' or target_ec == '*':
                    if ec_val.strip() == '':
                        failure_reasons.append(f"網購平台不符: 規則要求必須為網購(ANY)，實際非網購")
                elif ec_val.find(target_ec) < 0:
                    failure_reasons.append(f"網購平台不符: 規則要求'{target_ec}'，實際為'{ec_val}'")
            
            # 消費地點檢查
            if pd.notna(rule.get('merchant_location')) and rule['merchant_location'] != '':
                if pd.isna(row[const.COL_LOCATION]) or row[const.COL_LOCATION] == '':
                    failure_reasons.append(f"消費地點為空，規則要求'{rule['merchant_location']}'")
                elif str(row[const.COL_LOCATION]).find(rule['merchant_location']) < 0:
                    failure_reasons.append(f"消費地點不符: 規則要求含'{rule['merchant_location']}'，實際為'{row[const.COL_LOCATION]}'")
            
            # 商家名稱檢查
            if pd.notna(rule.get('merchant_display')) and rule['merchant_display'] != '':
                merchant_name = str(row[const.COL_MERCHANT_DISPLAY])
                pattern = str(rule['merchant_display'])
                
                # 檢查外部清單
                for key, merch_list in self.external_merchants.items():
                    if pattern == key and merch_list:
                        if merchant_name not in merch_list:
                            failure_reasons.append(f"商家'{merchant_name}'不在外部清單'{key}'中")
                        break
                else:
                    # 直接字串搜尋
                    if merchant_name.find(pattern) < 0:
                        failure_reasons.append(f"商家名稱不符: 規則要求含'{pattern}'，實際為'{merchant_name}'")
            
            if not failure_reasons:
                # 該條規則應該匹配，但為什麼沒有？可能是 Break 了
                return f"規則'{rule.get('rules_reward_program')}' 符合但被後續規則的 Break 機制阻止"
        
        # 如果所有規則都檢查過了，返回第一條規則的失敗原因
        first_rule = base_rules_for_prog.iloc[0]
        return f"規則'{first_rule.get('rules_reward_program')}' 不符: 請檢查日期/卡片/支付方式/商家條件"


    def process(self, df_bills: pd.DataFrame) -> pd.DataFrame:
        """
        主處理流程 (V2: 全局 Priority Waterfall)
        
        Phase 1: 卡片啟用檢查 ✅
        Phase 2: 載入全規則表 + 維度資訊 ✅
        Phase 3: 全局 Priority 依序套用規則 + Break 機制 ✅
        Phase 4: 整合結果並輸出 ✅
        """
        if df_bills.empty:
            return df_bills

        df = df_bills.copy()
        
        # === 安全檢查：確保所有必要欄位存在 ===
        required_cols = [
            const.COL_TXN_DATE, const.COL_BANK_NAME, const.COL_CARD_TYPE,
            const.COL_MERCHANT_DISPLAY, const.COL_PAY_AMOUNT, const.COL_LOCATION
        ]
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"⚠️ 缺少欄位: {col}")
                df[col] = ''
        
        optional_cols = [const.COL_MOBILE_PAY, const.COL_VPC_NO, const.COL_VPC_TYPE]
        for col in optional_cols:
            if col not in df.columns:
                df[col] = ''
        
        # 日期標準化
        df[const.COL_TXN_DATE] = pd.to_datetime(df[const.COL_TXN_DATE], errors='coerce')
        pay_amounts = pd.to_numeric(df[const.COL_PAY_AMOUNT], errors='coerce')
        if isinstance(pay_amounts, pd.Series):
            df[const.COL_PAY_AMOUNT] = pay_amounts.fillna(0)
        else:
            df[const.COL_PAY_AMOUNT] = 0.0 if pd.isna(pay_amounts) else pay_amounts
        
        # === 預初始化所有回饋欄位 ===
        df['matched_base_rule'] = ''
        df['base_rule_rate'] = ''
        df['matched_campaigns'] = ''
        df['_campaign_details'] = [[] for _ in range(len(df))]
        df['_rule_applied'] = False  # 標記規則已套用，Break 後阻止後續檢查
        
        # === Phase 1: 卡片啟用檢查 ===
        df['_should_calculate'] = df[const.COL_CARD_TYPE].apply(lambda card: self._should_calculate_reward(card))
        
        # === Phase 3: 全局 Priority 執行（all_rules_master 已按 priority 排序）===
        if self.all_rules_master.empty:
            logger.warning("⚠️ all_rules_master 為空，跳過回饋計算。")

        for _, rule in self.all_rules_master.iterrows():
            # 找出尚未被 Break 的交易
            pending_mask = ~df['_rule_applied']
            if not isinstance(pending_mask, pd.Series):
                continue
                
            if not pending_mask.any():
                break
            
            # 逐筆檢查是否符合規則
            matched_mask = pending_mask.copy()
            for idx in df[pending_mask].index:
                if not self._match_rule(df.loc[idx], rule):
                    matched_mask[idx] = False
                elif not df.loc[idx, '_should_calculate']:
                    matched_mask[idx] = False
            
            if not matched_mask.any():
                continue
            
            # === 標記規則 (僅標記回饋率與名稱，不在此處計算絕對金額) ===
            rate = rule.get('final_rate', 0)
            
            # 決定是 Base 還是 Campaign
            if rule.get('is_base_rule'):
                # [優化] First-Wins (先搶先贏)：僅覆蓋尚未匹配到 Base Rule 的交易，保留最高優先級
                empty_base_mask = matched_mask & (df['matched_base_rule'] == '')
                if empty_base_mask.any():
                    df.loc[empty_base_mask, 'matched_base_rule'] = rule.get('rules_reward_program', '')
                    df.loc[empty_base_mask, 'base_rule_rate'] = f"{rate*100:.2f}%"
            elif rule.get('is_campaign_rule'):
                # 追踪 Campaign（支援堆疊）
                details_series = df.loc[matched_mask, '_campaign_details']
                if isinstance(details_series, pd.Series):
                    df.loc[matched_mask, '_campaign_details'] = details_series.apply(
                        lambda x: x + [f"{rule.get('rules_reward_program')}({rate*100:.0f}%)"] if isinstance(x, list) else [f"{rule.get('rules_reward_program')}({rate*100:.0f}%)"]
                    )
            
            # Break 邏輯（全局範圍）
            if str(rule.get('reward_cal_break')).upper() == 'TRUE':
                df.loc[matched_mask, '_rule_applied'] = True
        
        # 初始化未設置的欄位
        if 'matched_base_rule' not in df.columns:
            df['matched_base_rule'] = ''
        if 'base_rule_rate' not in df.columns:
            df['base_rule_rate'] = ''
        if '_campaign_details' not in df.columns:
            df['_campaign_details'] = [[] for _ in range(len(df))]
        

        # 合併 Campaign 詳情
        campaign_details = df['_campaign_details']
        if isinstance(campaign_details, pd.Series):
            df['matched_campaigns'] = campaign_details.apply(lambda x: '|'.join(x) if isinstance(x, list) and x else '')
        else:
            df['matched_campaigns'] = ''
        
        # === Phase 4: 整合結果 ===
        df['is_bypassed'] = (df['matched_base_rule'] == '') & (df['matched_campaigns'] == '')
        df['applied_rule'] = df['matched_base_rule'] + ' | ' + df['matched_campaigns']
        
        # 生成詳細除錯表
        self._export_debug_details(df)
        
        # 清理暫存欄位
        df = df.drop(columns=['_should_calculate', '_rule_applied', '_campaign_details'], errors='ignore')
        
        logger.info(f"✅ 回饋標記完成: {len(df)} 筆交易，{(~df['is_bypassed']).sum()} 筆匹配到回饋規則")
        
        return df

    def _export_debug_details(self, df: pd.DataFrame, output_dir: Optional[str] = None) -> None:
        """
        生成詳細除錯輸出表
        
        輸出欄位 (僅規則匹配過程，不包含計算結果):
        - card_type: 卡片類型
        - transaction_date: 交易日期
        - merchant_display: 商家名稱
        - payment_amount: 交易金額
        - mobile_payment: 行動支付方式（用於檢查規則匹配）
        - base_program: 確定的 Base Program
        - mobile_payment: 行動支付方式
        - matched_base_rule: 匹配的 Base Rule 名稱
        - base_rule_rate: Base Rule 回饋率
        - matched_campaigns: 所有 Campaign 規則及回饋率 (格式: "規則A(3%)|規則B(2%)")
        - is_bypassed: 是否無規則匹配
        - failure_reason: 若無匹配規則，失敗原因說明
        
        注意:
        - 不輸出 base_reward、campaign_reward、reward_earned
        - 原因: 這些金額需經過 reward_cycle、calc_method、round_strategy 處理，
        在詳細對照階段不應直接輸出，以避免混淆
        """

        
        if output_dir is None:
            output_dir = const.OUTPUT_DIR
        
        # 準備輸出表
        output_df = df[[
            const.COL_CARD_TYPE,
            const.COL_TXN_DATE,
            const.COL_MERCHANT_DISPLAY,
            const.COL_PAY_AMOUNT,
            const.COL_MOBILE_PAY,
            'matched_base_rule',
            'base_rule_rate',
            'matched_campaigns',
            'is_bypassed'
        ]].copy()
        
        # 重新命名欄位以便對照
        output_df.columns = [
            'card_type',
            'transaction_date',
            'merchant_display',
            'payment_amount',
            'mobile_payment',
            'matched_base_rule',
            'base_rule_rate',
            'matched_campaigns',
            'is_bypassed'
        ]
        
        # 新增失敗原因欄位
        output_df['failure_reason'] = ''
        
        # 為 is_bypassed=True 的交易診斷失敗原因
        bypass_mask = output_df['is_bypassed'] == True
        for idx in output_df[bypass_mask].index:
            original_idx = idx
            output_df.loc[idx, 'failure_reason'] = self._diagnose_match_failure(
                df.loc[original_idx],
                None
            )
        
        # 輸出 CSV
        output_path = os.path.join(output_dir, 'reward_calculation_detailed.csv')
        os.makedirs(output_dir, exist_ok=True)
        output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"✅ 詳細除錯表已輸出至: {output_path}")
        logger.info(f"   輸出 {len(output_df)} 筆交易，其中 {bypass_mask.sum()} 筆無規則匹配")