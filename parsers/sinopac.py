import pdfplumber
import pandas as pd
import re
from typing import List, Dict, Optional, Any
import const
from parsers.base import BasePdfParser

class SinopacBillParser(BasePdfParser):
    def __init__(self):
        super().__init__(bank=const.Bank.SINOPAC)

    def parse(self, pdf_path: str) -> pd.DataFrame:
        """
        三明治結構修復版：
        針對被切成 3 行的交易紀錄進行邏輯合併。
        """
        all_clean_rows = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
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
                            
                            # 1. 錨點偵測 (呼叫基底類別方法)
                            if not self._is_date_pattern(row[0]):
                                continue
                                
                            # 2. 開始組裝 (Reconstruction)
                            try:
                                desc_parts = []
                                
                                # A. 檢查上一行 (Top Bun)
                                if i > 0:
                                    prev_row = table[i-1]
                                    if not self._is_date_pattern(prev_row[0]) and len(prev_row) > 3:
                                        part = f"{prev_row[3] or ''}".strip()
                                        if part: desc_parts.append(part)

                                # B. 檢查當前行 (Meat)
                                if len(row) > 3:
                                    curr_part = f"{row[3] or ''}".strip()
                                    if curr_part: desc_parts.append(curr_part)

                                # C. 檢查下一行 (Bottom Bun)
                                if i < num_rows - 1:
                                    next_row = table[i+1]
                                    if not self._is_date_pattern(next_row[0]) and len(next_row) > 3:
                                        part = f"{next_row[3] or ''}".strip()
                                        if part: desc_parts.append(part)
                                
                                # 合併說明
                                full_description = "".join(desc_parts)

                                # 建立資料物件 (使用基底定義的 target_columns)
                                item = {
                                    const.COL_TXN_DATE: row[0],
                                    const.COL_POST_DATE: row[1],
                                    const.COL_CARD_NO: str(row[2]).replace('(', '').replace(')', ''),
                                    const.COL_MERCHANT: full_description,
                                    const.COL_PAY_AMOUNT: self._clean_pdf_amount(row[4]), # 呼叫基底類別方法
                                    const.COL_CONV_DATE: None,
                                    const.COL_CURR_AMOUNT: 0.0
                                }
                                all_clean_rows.append(item)

                            except IndexError:
                                continue

            # 轉成 DataFrame
            df = pd.DataFrame(all_clean_rows, columns=self.target_columns)
            
            # 加上銀行名稱標籤
            df[const.COL_BANK_NAME] = self.bank.bank_id

            # 呼叫 BaseBillParser 的通用處理 (日期轉換與型態強制)
            df = self.transform_common_dates(df, pdf_path)
            
            # 最終正規化 (補齊 TWD 等)
            df = self._finalize_normalization(df)
            
            df = self._enforce_dtypes(df)
            
            return df

        except Exception as e:
            print(f"Error parsing Sinopac PDF: {e}")
            return pd.DataFrame(columns=self.target_columns)

# 用於單獨測試
if __name__ == "__main__":
    pass
