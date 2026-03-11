import pandas as pd
import numpy as np
import re
from datetime import datetime

# ==========================================
# Stage 0: 規則合併與優先排序
# ==========================================
def load_and_merge_rules(df_base_rules: pd.DataFrame, df_campaigns: pd.DataFrame) -> pd.DataFrame:
    """
    合併基礎權益維度表與短期活動總表，並依據優先級排序。
    確保高優先級（如短期活動、新戶加碼）排在前面。
    """
    # 這裡實作時會將兩張表的欄位名稱對齊（標準化）
    # 假設對齊後的必要欄位有：Rule_ID, Card_ID, Regex, Start, End, Rate, Cap, Priority
    
    # 模擬合併邏輯
    df_all_rules = pd.concat([df_base_rules, df_campaigns], ignore_index=True)
    
    # 依據優先級 (Priority) 升冪排序 (1 最高，99 最低)
    df_all_rules = df_all_rules.sort_values(by='Priority', ascending=True).reset_index(drop=True)
    return df_all_rules

# ==========================================
# Stage 1: PK 例外覆寫與跳脫 (Exception Override)
# ==========================================
def apply_pk_overrides(df_bills: pd.DataFrame, df_exceptions: pd.DataFrame) -> pd.DataFrame:
    """
    透過 transaction_id (PK) 攔截異常交易（如：活動提前額滿、銀行算錯帳）。
    """
    if df_exceptions.empty:
        df_bills['is_bypassed'] = False
        df_bills['reward_earned'] = 0.0
        return df_bills

    df_merged = pd.merge(df_bills, df_exceptions, on='transaction_id', how='left')
    
    # 標記被 PK 覆寫的資料
    df_merged['is_bypassed'] = df_merged['override_flag'].notna()
    # 賦予覆寫的回饋金 (確保為 float 型態)
    df_merged['reward_earned'] = df_merged['override_reward'].fillna(0.0).astype(float)
    
    return df_merged

# ==========================================
# Stage 2: 全域排除檢驗 (Global Exclusions)
# ==========================================
def apply_global_exclusions(df_bills: pd.DataFrame) -> pd.DataFrame:
    """
    利用 Regex 檢驗是否落入全域排除名單。
    涵蓋：公用事業、NCCC小額支付、大型零售、稅款、銀行費用、票證自動加值。
    """
    # 綜合排除的正則表達式
    exclusion_pattern = r'.*(台灣電力公司|自來水|瓦斯|中華電信|停車費|管理費|醫指付|全國繳費網|麥當勞|肯德基|爭鮮|全聯|PXGo|7-11|7-ELEVEN|全家|萊爾富|OK超商|綜合所得稅|房屋稅|地價稅|使用牌照稅|營業稅|循環息|違約金|年費|手續費|預借現金|悠遊卡自動加值|一卡通自動加值|icash自動加值).*'
    
    for idx, row in df_bills.iterrows():
        if row['is_bypassed']:
            continue
            
        merchant_name = str(row['merchant_name'])
        is_exception_allowed = bool(row.get('is_exception_allowed', False)) # 預留給 Cube 集精選的豁免權
        
        # 若命中排除條件，且不允許特例豁免，則直接排除
        if re.search(exclusion_pattern, merchant_name) and not is_exception_allowed:
            df_bills.at[idx, 'is_bypassed'] = True
            df_bills.at[idx, 'reward_earned'] = 0.0
            df_bills.at[idx, 'applied_rule'] = 'GLOBAL_EXCLUSION'
            
    return df_bills

# ==========================================
# Stage 3: 狀態滾動與上限截斷 (Rolling Rewards)
# ==========================================
def calculate_rolling_rewards(df_bills: pd.DataFrame, rules_df: pd.DataFrame) -> pd.DataFrame:
    """
    針對正常交易，依時間排序後套用規則，並計算回饋上限。
    """
    # 確保依據卡號與時間排序，以正確計算累積值
    # Bills.db 欄位: card_no, transaction_date
    df_bills = df_bills.sort_values(by=['card_no', 'transaction_date'])
    
    # 追蹤累積回饋的字典：{(card_no, rule_id, year_month): accumulated_amount}
    accumulated_rewards = {}
    
    for idx, row in df_bills.iterrows():
        if row['is_bypassed']:
            continue
            
        # Bills.db 欄位: payment_amount, merchant_name, transaction_date
        payment_amount = float(row['payment_amount'])
        merchant_name = str(row['merchant_name'])
        txn_date = pd.to_datetime(row['transaction_date'])
        txn_month = txn_date.strftime('%Y-%m')
        card_no = row['card_no']
        
        # 篩選該卡片適用的規則 (規則表假設有 Card_No 欄位)
        card_rules = rules_df[rules_df['Card_No'] == card_no]
        
        applied = False
        for _, rule in card_rules.iterrows():
            rule_id = rule['Rule_ID']
            rule_regex = str(rule['Regex'])
            start_time = pd.to_datetime(rule['Start'])
            end_time = pd.to_datetime(rule['End'])
            rate = float(rule['Rate'])
            cap = float(rule['Cap'])
            
            # 1. 檢查時間是否在規則生效期內
            if not (start_time <= txn_date <= end_time):
                continue
                
            # 2. 檢查通路 Regex 匹配
            if re.search(rule_regex, merchant_name):
                # 計算預期回饋
                expected_reward = payment_amount * (rate / 100.0)
                
                # 取得當月該規則已累積金額
                key = (card_no, rule_id, txn_month)
                current_accumulated = accumulated_rewards.get(key, 0.0)
                
                # 計算剩餘額度並截斷
                remaining_cap = max(0.0, cap - current_accumulated)
                actual_reward = min(expected_reward, remaining_cap)
                
                # 更新累積狀態與寫入資料表
                accumulated_rewards[key] = current_accumulated + actual_reward
                df_bills.at[idx, 'reward_earned'] = float(actual_reward)
                df_bills.at[idx, 'applied_rule'] = rule_id
                
                applied = True
                break # 命中高優先級規則後，跳出尋找
                
        # 若沒有命中任何規則，預設給 0 或記錄為 UNMATCHED
        if not applied:
            df_bills.at[idx, 'reward_earned'] = 0.0
            df_bills.at[idx, 'applied_rule'] = 'UNMATCHED'

    return df_bills

# ==========================================
# 主執行入口 (測試用)
# ==========================================
if __name__ == "__main__":
    print("🚀 信用卡回饋計算引擎初始化中...")
    # 這裡可以撰寫假資料或讀取 test_bills.csv 來驗證這 3 個 Stage 是否如期運作。
    # 例如準備一筆 transaction_amount = 3000.0 且 merchant_name = "玉山 Wallet-全家便利商店" 的明細
    # 預期結果會被 Stage 2 的全域排除攔截，reward_earned 變為 0.0。