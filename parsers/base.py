# parsers/base.py
import pandas as pd
import io
import os
import re
import logging
import const
from bs4 import BeautifulSoup # 記得確認 requirements.txt 有這兩樣
import lxml 

logger = logging.getLogger(__name__)

# ==========================================
# 1. 內部工具函式
# ==========================================
def _parse_date_smart(value, base_year=None, bill_month=None):
    """
    智慧日期解析：
    1. 支援完整格式 (YYYY/MM/DD, 民國年) -> 直接解析
    2. 支援缺年格式 (MM/DD) -> 根據 base_year 與 bill_month 自動補全年份
    """
    if pd.isna(value) or str(value).strip() == '':
        return pd.NaT
    
    s = str(value).strip()
    if s.lower() == 'nan': return pd.NaT

    # --- A. 嘗試標準完整格式 (含年份) ---
    # 支援 YYYY/MM/DD 或 民國年 112/05/20
    if len(re.findall(r'[-/]', s)) >= 2:
        try:
            match = re.match(r'^(\d{2,3})[-/](\d{1,2})[-/](\d{1,2})', s)
            if match:
                y_str, m, d = match.groups()
                year = int(y_str)
                if year < 1911: year += 1911
                return pd.Timestamp(year=year, month=int(m), day=int(d))
            return pd.to_datetime(s)
        except:
            pass

    # --- B. 處理缺年格式 (MM/DD) ---
    # 這是 CSV 最需要的功能
    if base_year and bill_month:
        # 支援 M/D, MM/DD, M-D
        match_md = re.match(r'^(\d{1,2})[-/](\d{1,2})', s)
        if match_md:
            m_str, d_str = match_md.groups()
            m, d = int(m_str), int(d_str)
            
            final_year = base_year
            
            # [跨年邏輯]
            # 假設帳單檔名是 202601 (1月)，但交易日是 12/25
            # 代表這是「去年」的消費
            # 判斷邏輯：如果 帳單月份(1) < 交易月份(12)，則年份 -1
            if bill_month < m and (m - bill_month) > 6: 
                # 加個 (m - bill_month) > 6 是為了保險 (避免只是差一兩個月的調整)
                # 例如帳單是2月，交易是1月，不用減。但帳單是1月，交易是12月，要減。
                final_year -= 1
            
            # 反向防呆：帳單是12月，但交易是1月 (通常是明年?)
            elif bill_month == 12 and m == 1:
                final_year += 1
                
            try:
                return pd.Timestamp(year=final_year, month=m, day=d)
            except ValueError:
                pass

    return pd.NaT

# ==========================================
# 2. Base Classes
# ==========================================

class BaseBillParser:
    """
    [基底類別] 負責通用邏輯：檔名解析、日期清洗
    """
    def _get_bill_period(self, filepath: str):
        """
        從檔名提取年份與月份
        策略：依序嘗試多種 Regex 模式，直到匹配成功
        """
        filename = os.path.basename(filepath)
        
        patterns = [
            # 1. [優先] 玉山格式: "玉山銀行112年05月..." (民國年中文)
            {
                'pat': r'(\d{2,3})年(\d{1,2})月',
                'is_roc': True
            },
            # 2. [通用] 西元年 YYYYMM (涵蓋 國泰、永豐、華南、中信)
            # 中信: "..._20260211..." -> 會抓到 2026, 02 (正確)
            # 國泰: "202602..." -> 會抓到 2026, 02
            # 永豐: "永豐202602" -> 會抓到 2026, 02
            {
                'pat': r'(20\d{2})(\d{2})',
                'is_roc': False
            },
            # 3. [備用] 民國年 YYYMM (純數字，例如 "華南11501.xls")
            {
                'pat': r'(\d{3})(\d{2})',
                'is_roc': True
            }
        ]

        for p in patterns:
            match = re.search(p['pat'], filename)
            if match:
                y_str, m_str = match.group(1), match.group(2)
                year = int(y_str)
                month = int(m_str)
                
                # 民國年轉西元
                if p['is_roc']:
                    year += 1911
                
                return year, month
            
        return None, None

    def transform_common_dates(self, df: pd.DataFrame, filepath: str) -> pd.DataFrame:
        """
        統一將標準欄位中的日期字串轉換為 Timestamp
        **自動帶入檔名中的年份**
        **並自動移除日期無效的雜訊行 (Garbage Collection)**
        """
        base_year, bill_month = self._get_bill_period(filepath)
        
        if base_year:
            # 可以在這裡 print log 確認是否有抓對年份
            # logger.info(f"檔名年份偵測: {os.path.basename(filepath)} -> {base_year}/{bill_month}")
            pass
        else:
            logger.warning(f"⚠️ 無法從檔名識別年份，日期解析可能會有誤: {os.path.basename(filepath)}")

        target_cols = [const.COL_TXN_DATE, const.COL_POST_DATE, const.COL_CONV_DATE]
        
        for col in target_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: _parse_date_smart(x, base_year, bill_month))


        # 強力過濾：如果 Transaction_Date 是 NaT，直接丟棄整行
        if const.COL_TXN_DATE in df.columns:
            # 記錄過濾前的筆數
            original_count = len(df)
            
            # 執行過濾
            df = df.dropna(subset=[const.COL_TXN_DATE])
            
            # (選用) 如果過濾掉太多，印個 log
            # dropped_count = original_count - len(df)
            # if dropped_count > 0:
            #     logger.debug(f"  🧹 過濾掉 {dropped_count} 筆無日期資料 (雜訊尾巴)")
        

        # 在回傳前，將全空的欄位移除 (dropna axis=1, how='all')
        # 這能有效避免 concat 時因為某個 parser 多了一個全是 NaN 的欄位而跳警告
        df = df.dropna(axis=1, how='all')

        return df

    def _enforce_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        根據 const.COLUMN_TYPES 強制統一欄位型態
        """
        for col_name, dtype in const.COLUMN_TYPES.items():
            # 只處理 DataFrame 裡實際存在的欄位
            if col_name not in df.columns:
                continue

            # --- 處理數值 (Float) ---
            if dtype == 'float':
                # 如果是 object (字串)，先去逗號
                if df[col_name].dtype == 'object':
                    df[col_name] = df[col_name].astype(str).str.replace(',', '', regex=False)
                # 強制轉數值 (無法轉的變 NaN)
                df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

            # --- 處理字串 (String) ---
            elif dtype == 'str':
                # 1. 先轉為字串 (此時 1234.0 會變成 "1234.0")
                s = df[col_name].astype(str)
                
                # 2. [新增] 修復浮點數格式 (只針對 "純數字.0" 進行修復)
                #    Regex 解說:
                #    ^(\d+)  -> 開頭必須是數字，並捕獲起來
                #    \.0$    -> 結尾必須是 .0
                #    r'\1'   -> 替換為捕獲的數字部分
                #    這樣可以避免誤殺像 "Version 2.0" 這種非整數的字串
                s = s.str.replace(r'^(\d+)\.0$', r'\1', regex=True)
                
                # 3. 去除前後空白
                s = s.str.strip()
                
                # 4. 回填並處理空值
                df[col_name] = s
                # 將 "nan", "None", "" 統一轉為真正的 None
                df[col_name] = df[col_name].replace({'nan': None, 'None': None, '': None})

            # --- 處理日期 (Date) ---
            elif dtype == 'date':
                # 日期已經在 transform_common_dates 處理過了
                # 這裡可以做個保險：確保它是 datetime64[ns]
                if not pd.api.types.is_datetime64_any_dtype(df[col_name]):
                     df[col_name] = pd.to_datetime(df[col_name], errors='coerce')

        return df


    def extract_card_info_generic(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        [通用卡號提取邏輯]
        適用於：帳單結構為 "卡號標題列" -> "多筆交易" -> "卡號標題列" -> "多筆交易" 的形式。
        使用 ffill (Forward Fill) 將標題列資訊帶入交易列。
        
        Args:
            config (dict): 包含 'trigger', 'card_no', 'card_type' 的 Regex 設定
        """
        # 必要的欄位檢查
        if const.COL_MERCHANT not in df.columns:
            return df

        trigger = config.get('trigger')
        card_no_pattern = config.get('card_no')
        card_type_pattern = config.get('card_type')

        # 1. 標記 Master Rows (包含卡號資訊的標題列)
        # 使用 na=False 避免非字串資料報錯
        mask_master = df[const.COL_MERCHANT].astype(str).str.contains(trigger, na=False, regex=True)

        if mask_master.any():
            # logger.info(f"  🔍 偵測到 {mask_master.sum()} 個卡號群組，開始歸戶提取...")

            # 2. 擴散 (Propagate)
            # 建立暫存欄位，先把 Master 的內容填進去
            df['raw_master_info'] = df.loc[mask_master, const.COL_MERCHANT]
            # 向下填補 (Forward Fill)，讓下面的交易都知道自己屬於哪個 Master
            df['raw_master_info'] = df['raw_master_info'].ffill()

            # 3. 提取 (Extract)
            # 從暫存欄位中，用 Regex 抓出卡號與卡別
            df[const.COL_CARD_NO] = df['raw_master_info'].str.extract(card_no_pattern)
            
            if card_type_pattern:
                df[const.COL_CARD_TYPE] = df['raw_master_info'].str.extract(card_type_pattern)

            # 4. [Fix Issue] 繳款/轉帳資料防呆
            # 邏輯：繳款紀錄不屬於特定卡片消費，強制清空卡號
            mask_payment = df[const.COL_MERCHANT].astype(str).str.contains('繳款|轉帳', na=False, regex=True)
            if mask_payment.any():
                # logger.debug(f"    🛡️ 清除 {mask_payment.sum()} 筆繳款/轉帳紀錄的卡號關聯")
                df.loc[mask_payment, const.COL_CARD_NO] = None
                if const.COL_CARD_TYPE in df.columns:
                    df.loc[mask_payment, const.COL_CARD_TYPE] = None

            # 5. 清理戰場
            # 刪除原始的 Master Rows (它們不是交易)
            df = df[~mask_master].copy()
            # 刪除暫存欄位
            df = df.drop(columns=['raw_master_info'])

        return df

    def _clean_amount(self, df: pd.DataFrame, col_name: str) -> pd.Series:
        """標準化金額欄位：去除逗號，轉為浮點數"""
        if col_name not in df.columns:
            return pd.Series(0, index=df.index)
            
        # 1. 先轉字串，去除前後空白
        series = df[col_name].astype(str).str.strip()
        
        # 2. [關鍵修正] 去除千分位逗號 (1,868 -> 1868)
        series = series.str.replace(',', '', regex=False)
        
        # 3. 轉為數字 (無法轉換的變成 NaN，然後填 0)
        return pd.to_numeric(series, errors='coerce').fillna(0)

class BaseCsvParser(BaseBillParser):
    """
    [CSV 專用基底] 提供 CSV 智慧讀取功能
    """
    def read_csv_smart(self, filepath: str, encoding: str, header_keyword: str, stop_at_keyword: str = None) -> pd.DataFrame:
        content_buffer = []
        found_header = False
        
        try:
            with open(filepath, 'r', encoding=encoding, errors='replace') as f:
                all_lines = f.readlines()
            
            for line in all_lines:
                # 1. 尋找標題
                if not found_header:
                    if header_keyword and header_keyword in line:
                        found_header = True
                        content_buffer.append(line)
                    continue
                
                # 2. 檢查停止點
                if stop_at_keyword and stop_at_keyword in line:
                    break
                
                # 3. 加入內容
                content_buffer.append(line)
            
            if found_header and content_buffer:
                csv_str = "".join(content_buffer)
                return pd.read_csv(io.StringIO(csv_str), on_bad_lines='skip')
            else:
                logger.warning(f"⚠️ 找不到標題 '{header_keyword}'，嘗試直接讀取")
                return pd.read_csv(filepath, encoding=encoding, header=0, on_bad_lines='skip')
                
        except Exception as e:
            logger.error(f"❌ Smart Read 失敗 ({os.path.basename(filepath)}): {e}")
            return pd.DataFrame()
        
class BaseHtmlParser(BaseBillParser):
    """
    [HTML/XLS 專用基底] 
    專門處理公股銀行常見的 "假 Excel" (其實是 HTML Table)
    """
    def read_html_smart(self, filepath: str, encoding: str, header_keyword: str, stop_at_keyword: str = None) -> pd.DataFrame:
        """
        智慧讀取 HTML：
        1. 使用 BeautifulSoup 定位包含 header_keyword 的表格
        2. 轉換為 DataFrame
        3. 若有 stop_at_keyword，自動截斷後續資料
        """
        try:
            # 1. 讀取檔案內容
            with open(filepath, 'r', encoding=encoding, errors='replace') as f:
                soup = BeautifulSoup(f, 'lxml')
            
            # 2. 定位標題 (Header)
            # 搜尋包含 header_keyword 的文字節點
            header_node = soup.find(string=lambda t: t and header_keyword in t)
            
            if not header_node:
                logger.warning(f"⚠️ HTML 中找不到標題關鍵字 '{header_keyword}'")
                return pd.DataFrame()

            # 3. 抓取所在的 Table
            target_table = header_node.find_parent('table')
            if not target_table:
                logger.warning(f"⚠️ 找到標題但找不到父層表格")
                return pd.DataFrame()

            # 4. 轉為 DataFrame
            # 使用 io.StringIO 避免 pandas 警告
            dfs = pd.read_html(io.StringIO(str(target_table)), header=0)
            if not dfs:
                return pd.DataFrame()
            
            df = dfs[0]

            # 5. 清洗欄位名稱 (HTML 表格常有換行符號 \n 或多餘空白)
            # 例如 "消費\n明細" -> "消費明細"
            df.columns = ["".join(str(c).split()) for c in df.columns]

            # 6. 處理 Stop Keyword (截斷尾部雜訊)
            if stop_at_keyword:
                # 檢查每一列，是否任一欄位包含停止關鍵字
                #astype(str) 確保所有內容都是字串，避免報錯
                mask = df.astype(str).apply(lambda x: x.str.contains(stop_at_keyword, na=False)).any(axis=1)
                
                if mask.any():
                    stop_idx = mask.idxmax() # 找到第一筆出現的位置
                    # logger.info(f"  🛑 在第 {stop_idx} 行偵測到 '{stop_at_keyword}'，截斷後續資料。")
                    df = df.iloc[:stop_idx]

            return df

        except Exception as e:
            logger.error(f"❌ Smart HTML Read 失敗 ({os.path.basename(filepath)}): {e}")
            return pd.DataFrame()