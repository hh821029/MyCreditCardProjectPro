import pdfplumber
import pandas as pd
import re
from typing import List, Dict, Optional, Any # <--- 這裡補上了 Any
import const # 確保 const.py 在專案根目錄，且環境設定正確

class SinopacBillParser:
    def __init__(self):
        # 定義標準輸出欄位 (使用 const 統一命名)
        self.target_columns = [
            const.COL_TXN_DATE, 
            const.COL_POST_DATE, 
            const.COL_MERCHANT,       # description -> Merchant
            const.COL_CARD_NO, 
            const.COL_PAY_AMOUNT,     # amount_ntd -> Payment_Amount
            const.COL_CONV_DATE, 
            const.COL_CURR_AMOUNT     # amount_foreign -> Currency_Amount
        ]

    def parse(self, pdf_path: str) -> pd.DataFrame:
        """
        三明治結構修復版：
        針對被切成 3 行的交易紀錄進行邏輯合併。
        """
        all_clean_rows = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # print(f"[Sinopac] 正在處理: {pdf_path} (共 {len(pdf.pages)} 頁)...")
                
                for page in pdf.pages:
                    # 使用 text 策略
                    tables = page.extract_tables(table_settings={
                        "vertical_strategy": "text", 
                        "horizontal_strategy": "text"
                    })

                    for table in tables:
                        num_rows = len(table)
                        
                        for i in range(num_rows):
                            row = table[i]
                            
                            # 1. 錨點偵測
                            if not self._is_date(row[0]):
                                continue
                                
                            # 2. 開始組裝 (Reconstruction)
                            try:
                                desc_parts = []
                                
                                # A. 檢查上一行 (Top Bun)
                                if i > 0:
                                    prev_row = table[i-1]
                                    if not self._is_date(prev_row[0]) and len(prev_row) > 3:
                                        part = str(prev_row[3] or '').strip()
                                        if part: desc_parts.append(part)

                                # B. 檢查當前行 (Meat)
                                if len(row) > 3:
                                    curr_part = str(row[3] or '').strip()
                                    if curr_part: desc_parts.append(curr_part)

                                # C. 檢查下一行 (Bottom Bun)
                                if i < num_rows - 1:
                                    next_row = table[i+1]
                                    if not self._is_date(next_row[0]) and len(next_row) > 3:
                                        part = str(next_row[3] or '').strip()
                                        if part: desc_parts.append(part)
                                
                                # 合併說明
                                full_description = "".join(desc_parts)

                                # 建立資料物件 (使用 const 作為 key)
                                item = {
                                    const.COL_TXN_DATE: row[0],
                                    const.COL_POST_DATE: row[1],
                                    const.COL_CARD_NO: str(row[2]).replace('(', '').replace(')', ''),
                                    const.COL_MERCHANT: full_description,
                                    const.COL_PAY_AMOUNT: self._clean_amount(row[4]), # 台幣/應繳金額
                                    const.COL_CONV_DATE: None,
                                    const.COL_CURR_AMOUNT: 0.0
                                }
                                
                                # 外幣邏輯預留 (若未來需要)
                                if len(row) > 6:
                                    pass

                                all_clean_rows.append(item)

                            except IndexError:
                                continue

            # 轉成 DataFrame
            df = pd.DataFrame(all_clean_rows, columns=self.target_columns)
            
            # 加上銀行名稱標籤 (重要！)
            df[const.COL_BANK_NAME] = 'sinopac_bank'

            # 最終型態轉換
            df[const.COL_TXN_DATE] = pd.to_datetime(df[const.COL_TXN_DATE], errors='coerce')
            df[const.COL_POST_DATE] = pd.to_datetime(df[const.COL_POST_DATE], errors='coerce')
            
            return df

        except Exception as e:
            print(f"Error parsing PDF: {e}")
            return pd.DataFrame(columns=self.target_columns)

    def _is_date(self, value: Any) -> bool:
        """判斷是否為日期格式 YYYY/MM/DD"""
        if not value: return False
        return bool(re.match(r'^\d{4}/\d{2}/\d{2}$', str(value).strip()))

    def _clean_amount(self, value: str) -> float:
        """清洗金額"""
        if not value: return 0.0
        val_str = str(value).strip()
        
        is_negative = False
        if (val_str.startswith('(') and val_str.endswith(')')) or val_str.endswith('-'):
            is_negative = True
            
        clean_num = re.sub(r'[^\d.]', '', val_str)
        if not clean_num: return 0.0
        
        try:
            f_val = float(clean_num)
            return -f_val if is_negative else f_val
        except ValueError:
            return 0.0

# 用於單獨測試
if __name__ == "__main__":
    # 注意：在 parsers 目錄下直接執行時，路徑可能需要調整，建議用 main.py 呼叫
    pass