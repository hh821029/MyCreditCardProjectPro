# services/billing_service.py
import pandas as pd
import logging
from typing import Tuple, Dict, Optional
import datetime
import os

logger = logging.getLogger(__name__)

def preprocess_billing_history(df_billing: pd.DataFrame) -> pd.DataFrame:
    """
    預處理結帳歷史紀錄：
    1. 雙向互補 actual_closing_date 與 closing_date。
    2. 將日期欄位轉換為 datetime64 型別。
    3. 依據 [bank_name, card_type, statement_month] 排序。
    4. 計算每一期帳單的適用消費區間 [interval_start, interval_end]。
    """
    if df_billing is None or df_billing.empty:
        return pd.DataFrame()

    df = df_billing.copy()

    # 1. 雙向互補空值
    df['actual_closing_date'] = df['actual_closing_date'].fillna(df['closing_date'])
    df['closing_date'] = df['closing_date'].fillna(df['actual_closing_date'])

    # 2. 轉型為 datetime
    df['statement_month'] = pd.to_datetime(df['statement_month'], errors='coerce')
    df['actual_closing_date'] = pd.to_datetime(df['actual_closing_date'], errors='coerce')
    df['closing_date'] = pd.to_datetime(df['closing_date'], errors='coerce')

    # 過濾掉日期轉換失敗的列
    df = df.dropna(subset=['statement_month', 'actual_closing_date'])

    # 確保 card_type 空值一致性
    df['card_type'] = df['card_type'].fillna('')

    # 3. 排序以利區間計算
    df = df.sort_values(by=['bank_name', 'card_type', 'statement_month']).reset_index(drop=True)

    # 4. 起迄區間生成 (Billing Interval Reconstruction)
    df['interval_start'] = pd.NaT
    df['interval_end'] = df['actual_closing_date']

    # 按 (bank_name, card_type) 分組計算起迄日
    groups = df.groupby(['bank_name', 'card_type'], dropna=False)
    processed_dfs = []

    for name, group in groups:
        group = group.copy().sort_values(by='statement_month')
        actual_closes = group['actual_closing_date'].values
        starts = []
        
        for idx in range(len(group)):
            if idx > 0:
                # interval_start = 上一期的 actual_closing_date + 1 天
                prev_close = pd.Timestamp(actual_closes[idx-1])
                starts.append(prev_close + pd.Timedelta(days=1))
            else:
                # 第一期極端案例補救：推算為當期實際結帳日的前一個月同日 + 1 天
                curr_close = pd.Timestamp(actual_closes[idx])
                starts.append(curr_close - pd.DateOffset(months=1) + pd.Timedelta(days=1))
                
        group['interval_start'] = starts
        processed_dfs.append(group)

    if processed_dfs:
        df_final = pd.concat(processed_dfs, ignore_index=True)
    else:
        df_final = df

    return df_final

def _save_error_log(row: pd.Series, df_bills: pd.DataFrame, error_type: str) -> str:
    """將出錯的交易資料儲存至 errorlog 資料夾"""

    os.makedirs('errorlog', exist_ok=True)
    
    # 篩選所有出錯的行，或者若無法篩選則用當前行
    if error_type == 'missing_statement_month':
        df_err = df_bills[df_bills['statement_month'].isna() | (df_bills['statement_month'].astype(str).str.strip() == '')]
    elif error_type == 'missing_txn_date':
        df_err = df_bills[df_bills['transaction_date'].isna() & df_bills['posting_date'].isna()]
    else:
        # 其他錯誤，如區間衝突或找不到配置，只儲存當前錯誤行
        df_err = pd.DataFrame([row])
        
    if df_err.empty:
        df_err = pd.DataFrame([row])
        
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join('errorlog', f'errorlog_{timestamp}.csv')
    df_err.to_csv(filename, index=False, encoding='utf-8-sig')
    return filename

def validate_billing_consistency(df_bills: pd.DataFrame, df_billing: pd.DataFrame) -> pd.Series:
    """
    雙軌區間一致性校驗管線：
    1. 為每筆交易尋找其對應的結帳區間（優先特定卡片，次優先銀行通用）。
    2. 校驗交易日期是否落入該區間內。若不符，直接 raise ValueError。
    3. 回傳每筆交易對應的 actual_closing_date 序列 (pd.Series)。
    """
    if df_bills.empty:
        return pd.Series(dtype=str)

    if df_billing.empty:
        raise ValueError("❌ 結帳歷史維度表 (dim_billing_history) 為空，無法進行一致性校驗！")

    # 建立查找字典以加速 O(1) 比對
    dict_specific = {}
    dict_fallback = {}

    for _, row in df_billing.iterrows():
        bank = str(row['bank_name']).strip().lower()
        card = str(row['card_type']).strip().lower()
        
        # 轉成 YYYY-MM
        sm_dt = pd.to_datetime(row['statement_month'])
        sm_str = sm_dt.strftime('%Y-%m')
        
        start_val = pd.Timestamp(row['interval_start'])
        end_val = pd.Timestamp(row['interval_end'])
        act_close = pd.Timestamp(row['actual_closing_date'])
        
        if card != '':
            dict_specific[(bank, card, sm_str)] = (start_val, act_close, end_val)
        else:
            dict_fallback[(bank, sm_str)] = (start_val, act_close, end_val)

    applied_closing_dates = []

    for idx, row in df_bills.iterrows():
        bank_id = str(row.get('bank_name', '')).strip().lower()
        card_type = str(row.get('card_type', '')).strip().lower()
        sm_val = row.get('statement_month')
        
        if pd.isna(sm_val) or (isinstance(sm_val, str) and sm_val.strip() == ''):
            err_file = _save_error_log(row, df_bills, 'missing_statement_month')
            raise ValueError(f"❌ 交易資料缺失帳單月份 (statement_month)！錯誤已記錄至 {err_file}。列內容: {dict(row)}")
            
        sm_str = pd.to_datetime(sm_val).strftime('%Y-%m')
        
        txn_date_val = row.get('posting_date')
        if pd.isna(txn_date_val):
            txn_date_val = row.get('transaction_date')
            if pd.isna(txn_date_val):
                err_file = _save_error_log(row, df_bills, 'missing_txn_date')
                raise ValueError(f"❌ 交易資料缺少 posting_date 與 transaction_date！錯誤已記錄至 {err_file}。列內容: {dict(row)}")
                
        txn_date = pd.to_datetime(txn_date_val)

        # 1. 雙軌查找
        interval = dict_specific.get((bank_id, card_type, sm_str))
        if interval is None:
            # 嘗試銀行通用軌
            interval = dict_fallback.get((bank_id, sm_str))

        if interval is None:
            err_file = _save_error_log(row, df_bills, 'missing_config')
            raise ValueError(
                f"❌ 找不到結帳日配置！\n"
                f"  交易詳情: 日期={txn_date.strftime('%Y-%m-%d')}, 發卡行={row.get('bank_name')}, 卡片={row.get('card_type')}, "
                f"商家={row.get('merchant_display')}, 金額={row.get('payment_amount')}\n"
                f"  帳單月: {sm_str}\n"
                f"  請在 configs/dim_billing_history_private.csv 中補上該月份的結帳日。\n"
                f"  錯誤已記錄至 {err_file}。"
            )

        start_date, end_date, act_close = interval

        # 2. 一致性校驗
        if not (start_date <= txn_date <= end_date):
            err_file = _save_error_log(row, df_bills, 'interval_conflict')
            raise ValueError(
                f"🚨 交易日期與帳單月份區間衝突！\n"
                f"  交易詳情: 日期={txn_date.strftime('%Y-%m-%d')}, 卡片={row.get('card_type')}, "
                f"商家={row.get('merchant_display')}, 金額={row.get('payment_amount')}\n"
                f"  事實帳單月: {sm_str}\n"
                f"  配置結帳區間: [{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}] "
                f"(實際結帳日: {act_close.strftime('%Y-%m-%d')})\n"
                f"  請核對實體帳單與 dim_billing_history 設定是否正確。\n"
                f"  錯誤已記錄至 {err_file}。"
            )

        applied_closing_dates.append(act_close.strftime('%Y-%m-%d'))

    return pd.Series(applied_closing_dates, index=df_bills.index)
