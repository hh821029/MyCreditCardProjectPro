# const.py
import pandas as pd
import os
from enum import Enum

pd.set_option('future.no_silent_downcasting', True)

# ==========================================
# 1. 資料定義枚舉 (Enum) 
# ==========================================

class TransactionColumn(Enum):
    # 定義格式: (csv_col_name, data_type, max_length, sql_name)
    # 包含交易資料的各個資料型態，欄位名稱，以及對應的 SQL 欄位名稱
    # 另外也定義回饋規則相關的欄位，方便後續擴展和統一管理

    # 交易日期資訊
    TXN_DATE = ('transaction_date', 'date', None, 'transaction_date')
    POST_DATE = ('posting_date', 'date', None, 'posting_date')
    CONV_DATE = ('conversion_date', 'date', None, 'conversion_date')
    STAT_MON = ('statement_month', 'date', None, 'statement_month')
    
    # 商店消費資訊
    MERCHANT = ('merchant', 'str', 500, 'merchant_name')
    MERCHANT_PATTERN = ('merchant_pattern', 'str', 500, 'merchant_pattern') # 用於規則匹配的商家名稱欄位
    MERCHANT_DISPLAY = ('merchant_display', 'str', 500, 'merchant_display')
    LOCATION = ('merchant_location', 'str', 2, 'merchant_location')
    CONSUMPTION_PLACE = ('consumption_place', 'str', 255, 'consumption_place')
    MOBILE_PAY = ('mobile_payment', 'str', 50, 'mobile_payment')
    TXN_TYPE = ('transaction_type', 'str', 50, 'transaction_type')
    CATEGORY = ('category', 'str', 100, 'category')
    SUB_CATEGORY = ('sub_category', 'str', 100, 'sub_category')
    PROCESS_PATTERN = ('payment_process_pattern', 'str', 100, 'payment_process_pattern')
    PAYMENT_PROCESS = ('payment_process', 'str', 100, 'payment_process')
    PROCESS_PREFIX = ('process_prefix', 'str', 50, 'process_prefix')
    EC_PLATFORM = ('ec_platform', 'str', 100, 'ec_platform')
    EC_PLATFORM_PATTERN = ('ec_platform_pattern', 'str', 100, 'ec_platform_pattern')

    # 消費金額資訊
    CURRENCY = ('currency_type', 'str', 3, 'currency_type')
    CURR_AMOUNT = ('currency_amount', 'float', None, 'currency_amount')
    PAY_AMOUNT = ('payment_amount', 'float', None, 'payment_amount')
    PAY_CURR = ('payment_currency', 'str', 3, 'payment_currency')
    AMOUNT = ('amount', 'float', None, 'amount')

    # 卡片資訊
    BANK_NAME = ('bank_name', 'str', 50, 'bank_name')
    CARD_NO = ('card_no', 'str', 4, 'card_no')
    CARD_TYPE = ('card_type', 'str', 100, 'card_type')
    IS_DUAL_CURRENCY = ('is_dual_currency', 'bool', None, 'is_dual_currency')
    FX_TYPE = ('fx_type', 'str', 5, 'fx_type')
    ACTIVE_STATUS = ('active_status', 'str', 20, 'active_status')
    ENABLE_REWARD_CALC = ('enable_reward_calc', 'bool', None, 'enable_reward_calc')
    VPC_NO = ('vpc_no', 'str', 4, 'vpc_no')
    VPC_TYPE = ('vpc_type', 'str', 50, 'vpc_type')
    CARD_START_DATE = ('card_start_date', 'date', None, 'card_start_date')
    CARD_END_DATE = ('card_end_date', 'date', None, 'card_end_date')

    # 回饋資訊
    BASE_REWARD_PROGRAM = ('base_reward_program', 'str', 100, 'base_reward_program')
    BASE_REWARD_RATE = ('base_reward_rate', 'float', None, 'base_reward_rate')
    REWARD_PROGRAM = ('reward_program', 'str', 100, 'reward_program')
    REWARD_RATE = ('reward_rate', 'float', None, 'reward_rate')
    REWARD_CYCLE = ('reward_cycle', 'str', 50, 'reward_cycle')
    CAP_AMOUNT = ('cap_amount', 'float', None, 'cap_amount')
    PROGRAM_START_DATE = ('start_date', 'date', None, 'start_date')
    PROGRAM_END_DATE = ('end_date', 'date', None, 'end_date')
    MAX_POSTING_DATE = ('max_posting_date', 'date', None, 'max_posting_date')
    REWARD_TYPE = ('reward_type', 'str', 50, 'reward_type')
    CALC_METHOD = ('calc_method', 'str', 50, 'calc_method')
    ROUND_STRATEGY = ('round_strategy', 'str', 50, 'round_strategy')
    CAMPAIGN_REWARD_PROGRAM = ('campaign_reward_program', 'str', 100, 'campaign_reward_program')
    CAMPAIGN_REWARD_RATE = ('campaign_reward_rate', 'float', None, 'campaign_reward_rate')
    RULES_REWARD_PROGRAM = ('rules_reward_program', 'str', 100, 'rules_reward_program')
    MERCHANT_RATE = ('merchant_rate', 'float', None, 'merchant_rate')
    REWARD_CAL_BREAK = ('reward_cal_break', 'bool', None, 'reward_cal_break')
    CONDITION = ('condition', 'str', 255, 'condition')

    # 維度表與控制輔助欄位
    PRIORITY = ('priority', 'int', None, 'priority')
    RFM_EXCLUSION = ('rfm_exclusion', 'bool', None, 'rfm_exclusion')
    IS_NCCC_LISTED = ('is_nccc_listed', 'bool', None, 'is_nccc_listed')
    EC_PLATFORM_TYPE = ('ec_platform_type', 'str', 50, 'ec_platform_type')

    # 其他資訊(像是分期資訊等)
    INS_PLN = ('installment_plan', 'str', 100, 'installment_plan')
    REMARK = ('remark', 'str', 1000, 'remark')
    FX_RATE = ('exchange_rate', 'float', None, 'exchange_rate')
 
    # 暫存/運算用欄位 (Virtual Columns，不寫入資料庫)
    # 將 sql_name 設為 None，讓 mapping 自動攔截
    # TEMP_CALC_FLAG = ('temp_calc_flag', 'bool', None, None)
 

    @property
    def col_name(self): return self.value[0]
    @property
    def dtype(self): return self.value[1]
    @property
    def max_length(self): return self.value[2]
    @property
    def sql_name(self): return self.value[3]

    @classmethod
    def get_mapping(cls, *members):
        """
        動態產生欄位的映射表 (csv_col_name -> sql_name)。
        - 傳入 Enum 成員：自動建立 col_name -> sql_name
        - 傳入 Tuple (source, target)：建立 source -> target 的客製化映射 (用於處理改名邏輯)
        """
        mapping = {}
        for item in members:
            if isinstance(item, tuple) and len(item) == 2:
                src, tgt = item
                src_name = src.col_name if isinstance(src, cls) else src
                tgt_name = tgt.sql_name if isinstance(tgt, cls) else tgt
                if tgt_name is not None:
                    mapping[src_name] = tgt_name
            elif isinstance(item, cls):
                if item.sql_name is not None:
                    mapping[item.col_name] = item.sql_name
            else:
                # 攔截預期外的輸入型態（防呆機制）
                raise TypeError(f"不支援的傳入參數型態: {type(item)}")
        return mapping

class TransactionType(Enum):
    PAYMENT = '繳款'
    REDEMPTION = '紅利折抵'
    FEE = '各項費用'
    REFUND = '退刷'
    FOREIGN = '一般國外交易'
    FOREIGN_TWD = '台幣跨境交易'
    FOREIGN_DUAL = '一般雙幣交易'
    GENERAL = '交易'
    VERIFY = '驗證/零元'
    UNKNOWN = '未分類'

    @property
    def label(self):
        return self.value

class Location(Enum):
    TW = ('TW', 'TWN')
    US = ('US', 'USA')
    JP = ('JP', 'JPN')
    KR = ('KR', 'KOR')
    HK = ('HK', 'HKG')
    SG = ('SG', 'SGP')
    GB = ('GB', 'GBR')
    CN = ('CN', 'CHN')
    IE = ('IE', 'IRL')
    DE = ('DE', 'DEU')
    FR = ('FR', 'FRA')
    AU = ('AU', 'AUS')
    VN = ('VN', 'VNM')
    TH = ('TH', 'THA')
    MY = ('MY', 'MYS')
    ID = ('ID', 'IDN')

    @property
    def alpha_2(self):
        """兩碼國別代碼 (ISO 3166-1 alpha-2)"""
        return self.value[0]

    @property
    def alpha_3(self):
        """三碼國別代碼 (ISO 3166-1 alpha-3)"""
        return self.value[1]

    @classmethod
    def _missing_(cls, value):
        """支援智慧查找：輸入兩碼或三碼均可匹配到成員"""
        # 預防性檢查：若是 None 或非字串，直接回傳 None (由 Enum 丟出 ValueError 或由 normalize 處理)
        if not isinstance(value, str) or not value.strip():
            return None
        
        c = value.upper().strip()
        for member in cls:
            if c == member.alpha_2 or c == member.alpha_3:
                return member
        return None

    @classmethod
    def normalize(cls, code):
        """標準化輸出：將任意格式國別轉為兩碼。若無法識別或為空則回傳原值。"""
        if pd.isna(code) or str(code).strip() == '' or str(code).upper() == 'NONE':
            return code
        
        try:
            loc = cls(code) # 會觸發 _missing_
            return loc.alpha_2 if loc else code
        except (ValueError, TypeError):
            return code

class Currency(Enum):
    TWD = ('TWD', 'NTD', '新臺幣')
    USD = ('USD', 'US DOLLAR', '美元')
    JPY = ('JPY', 'YEN', '日圓')
    EUR = ('EUR', 'EURO', '歐元')
    HKD = ('HKD', 'HK DOLLAR', '港幣')
    GBP = ('GBP', 'POUND', '英鎊')
    AUD = ('AUD', 'AU DOLLAR', '澳幣')
    CAD = ('CAD', 'CA DOLLAR', '加拿大元')
    CHF = ('CHF', 'SWISS FRANC', '瑞士法郎')
    CNY = ('CNY', 'RMB', '人民幣')
    THB = ('THB', 'BAHT', '泰銖')
    KRW = ('KRW', 'WON', '韓元')
    IDR = ('IDR', 'RUPIAH', '印尼盾')

    @property
    def code(self):
        """標準三碼幣別代碼 (ISO 4217)"""
        return self.value[0]

    @classmethod
    def _missing_(cls, value):
        """支援智慧查找：支援別名 (如 NTD) 或中文名稱"""
        if not isinstance(value, str) or not value.strip():
            return None
        
        c = value.upper().strip()
        for member in cls:
            if c == member.code or c in member.value:
                return member
        return None

    @classmethod
    def normalize(cls, value):
        """標準化輸出：將各種幣別寫法轉為標準三碼。若無法識別或為空則回傳原值。"""
        if pd.isna(value) or str(value).strip() == '' or str(value).upper() == 'NONE':
            return value
            
        try:
            curr = cls(value)
            return curr.code if curr else value
        except (ValueError, TypeError):
            return value

class Bank(Enum):
    ESUN = ('esun','808',['玉山','esun'])
    CATHAY = ('cube','013',['國泰','國泰世華','cathay','cube','CUBE'])
    CTBC = ('ctbc','822',['中信','中國信託','ctbc'])
    HNCB = ('hncb','008',['華南','hncb'])
    SINOPAC = ('sinopac','807',['永豐','DAWHO','DAWAY','sinopac'])

    @property
    def bank_id(self):
        return self.value[0]
    
    @property
    def bank_code(self):
        return self.value[1]

    @property
    def bank_keywords_mapping(self):
        return self.value[2]

    @classmethod
    def from_keyword(cls, text):
        """
        根據輸入字串(如檔名、銀行名)自動匹配對應的 Bank 成員。
        取代原本 const.py 中的 BANK_KEYWORD_MAP。
        """
        if not text or not isinstance(text, str):
            return None
        
        # 轉小寫進行匹配，增加容錯率
        search_text = text.lower()
        for bank in cls:
            if any(kw.lower() in search_text for kw in bank.bank_keywords_mapping):
                return bank
        return None


class RewardType(Enum):
    # 格式: (reward_unit_name, conversion_rate, rounding_strategy, rounding_digits)
    CASHBACK_FLOOR = ('cashback', 1, 'floor', 0)     # 1 cashback = 1 TWD
    CASHBACK_ROUND = ('cashback', 1, 'round', 0)     # 1 cashback = 1 TWD
    TREEPOINTS = ('tree_points', 1, 'round', 0)      # 1 tree point = 1 TWD
    ESUNPOINT_FLOOR = ('e_points', 1, 'floor', 0)    # 1 e-point = 1 TWD
    ESUNPOINT_ROUND = ('e_points', 1, 'round', 0)    # 1 e-point = 1 TWD
    OPENPOINT = ('openpoint', 1, 'round', 2)         # 1 openpoint = 1 TWD, 但允許小數點後兩位
    LINEPOINT = ('line_points', 1, 'round', 0)       # 1 line point = 1 TWD
    HAMIPOINT = ('hami_points', 1, 'round', 0)       # 1 hami point = 1 TWD

    @property
    def reward_unit_name(self):
        return self.value[0]
    
    @property
    def conversion_rate(self):  
        return self.value[1]

    @property
    def rounding_strategy(self):
        return self.value[2]
    
    @property
    def rounding_digits(self):
        return self.value[3]

    @classmethod
    def to_records(cls):
        """
        動態產生所有回饋類型的配置列表 (List of Dicts)。
        非常適合直接轉為 DataFrame 並寫入資料庫做為維度表 (dim_reward_types)。
        """
        return [
            {
                'reward_type_name': member.name,
                'reward_unit_name': member.reward_unit_name,
                'conversion_rate': member.conversion_rate,
                'rounding_strategy': member.rounding_strategy,
                'rounding_digits': member.rounding_digits
            }
            for member in cls
        ]

    @classmethod
    def get_lookup_map(cls):
        """
        動態產生 lookup dictionary，方便在計算引擎中直接透過字串名稱查找對應設定。
        格式：{'CASHBACK_FLOOR': {'reward_unit_name': 'cashback', ...}, ...}
        """
        return {
            member.name: {
                'reward_unit_name': member.reward_unit_name,
                'conversion_rate': member.conversion_rate,
                'rounding_strategy': member.rounding_strategy,
                'rounding_digits': member.rounding_digits
            } 
            for member in cls
        }

# ==========================================
# 2. 交易資料欄位 (Transactions)
# ==========================================
# 這些是我們希望在最終 CSV 看到的標準欄位名稱

# 交易日期資訊
COL_TXN_DATE = TransactionColumn.TXN_DATE.col_name
COL_POST_DATE = TransactionColumn.POST_DATE.col_name
COL_CONV_DATE = TransactionColumn.CONV_DATE.col_name
COL_STAT_MON = TransactionColumn.STAT_MON.col_name

# 商店消費資訊
COL_MERCHANT = TransactionColumn.MERCHANT.col_name
COL_MERCHANT_DISPLAY = TransactionColumn.MERCHANT_DISPLAY.col_name
COL_LOCATION = TransactionColumn.LOCATION.col_name
COL_CONSUMPTION_PLACE = TransactionColumn.CONSUMPTION_PLACE.col_name
COL_MOBILE_PAY = TransactionColumn.MOBILE_PAY.col_name
COL_TXN_TYPE = TransactionColumn.TXN_TYPE.col_name
COL_CATEGORY = TransactionColumn.CATEGORY.col_name
COL_SUB_CATEGORY = TransactionColumn.SUB_CATEGORY.col_name
COL_PROCESS_PATTERN = TransactionColumn.PROCESS_PATTERN.col_name

# 消費金額資訊
COL_CURRENCY = TransactionColumn.CURRENCY.col_name
COL_AMOUNT = TransactionColumn.AMOUNT.col_name
COL_CURR_AMOUNT = TransactionColumn.CURR_AMOUNT.col_name
COL_PAY_AMOUNT = TransactionColumn.PAY_AMOUNT.col_name
COL_PAY_CURR = TransactionColumn.PAY_CURR.col_name

# 卡片資訊
COL_BANK_NAME = TransactionColumn.BANK_NAME.col_name
COL_CARD_NO = TransactionColumn.CARD_NO.col_name
COL_CARD_TYPE = TransactionColumn.CARD_TYPE.col_name
COL_IS_DUAL_CURRENCY = TransactionColumn.IS_DUAL_CURRENCY.col_name
COL_FX_TYPE = TransactionColumn.FX_TYPE.col_name
COL_ACTIVE_STATUS = TransactionColumn.ACTIVE_STATUS.col_name
COL_ENABLE_REWARD_CALC = TransactionColumn.ENABLE_REWARD_CALC.col_name
COL_VPC_NO = TransactionColumn.VPC_NO.col_name
COL_VPC_TYPE = TransactionColumn.VPC_TYPE.col_name

# 其他資訊
COL_INS_PLN = TransactionColumn.INS_PLN.col_name
COL_PAYMENT_PROCESS = TransactionColumn.PAYMENT_PROCESS.col_name
COL_PROCESS_PREFIX = TransactionColumn.PROCESS_PREFIX.col_name
COL_EC_PLATFORM = TransactionColumn.EC_PLATFORM.col_name


# ==========================================
# 3. 回饋規則欄位 (Rewards Configs) - [新增]
# ==========================================
COL_REWARD_PROGRAM = TransactionColumn.REWARD_PROGRAM.col_name       # 紅利/回饋計畫名稱
COL_START_DATE = TransactionColumn.PROGRAM_START_DATE.col_name       # 適用起始日
COL_END_DATE = TransactionColumn.PROGRAM_END_DATE.col_name           # 適用結束日
COL_REWARD_TYPE = TransactionColumn.REWARD_TYPE.col_name             # 回饋類型 (現金回饋、紅利點數、里程數等)
COL_REWARD_RATE = TransactionColumn.REWARD_RATE.col_name             # 回饋比率 (如一般消費的 0.01、網購的 0.02)
COL_REWARD_CYCLE = TransactionColumn.REWARD_CYCLE.col_name           # 回饋計算週期 (如依帳單結帳週期、依消費日曆月、依消費日等)
COL_MERCHANT_RATE = TransactionColumn.MERCHANT_RATE.col_name         # 特約商家回饋率 (同一個權益項目中，特店A回饋比率 0.02，特店B回饋比率 0.03)
COL_CAP_AMOUNT = TransactionColumn.CAP_AMOUNT.col_name               # 回饋上限
COL_CALC_METHOD = TransactionColumn.CALC_METHOD.col_name             # 計算策略 (PER_ITEM / AGGREGATE)
COL_ROUND_STRATEGY = TransactionColumn.ROUND_STRATEGY.col_name       # 四捨五入策略 (如無條件捨去、無條件進位、四捨五入到整數、四捨五入到小數點後兩位等)
COL_CONDITION = TransactionColumn.CONDITION.col_name                 # 條件標籤 (或 Regex 規則)



# ==========================================
# 4. 標準輸出欄位順序 (Schema Definition)
# ==========================================

# ==========================================
# 4-1. 寫入資料庫的交易資料標準欄位順序(Transactions Schema)
# ==========================================

STANDARD_COLUMNS = [
    COL_TXN_DATE, COL_POST_DATE, COL_STAT_MON, 
    COL_MERCHANT, COL_MERCHANT_DISPLAY, COL_LOCATION, 
    COL_CURRENCY, COL_CURR_AMOUNT, COL_CONV_DATE, 
    COL_PAY_AMOUNT, COL_PAY_CURR,
    COL_TXN_TYPE, COL_INS_PLN, COL_MOBILE_PAY, 
    COL_CARD_NO, COL_CARD_TYPE, COL_BANK_NAME,
    COL_VPC_NO, COL_VPC_TYPE, COL_EC_PLATFORM
]

# ==========================================
# 5. 統一型別定義表 (The Law / Schema)
# ==========================================
# 用於 BaseParser 或 Enforcer 統一強制轉型
# 格式: { 欄位名: '目標型別' }

# 動態從 TransactionColumn 提取資料型態映射
# 避免與上方定義手動重複維護，確保資料唯一性 (Single Source of Truth)
COLUMN_TYPES = {
    col.col_name: col.dtype 
    for col in TransactionColumn
}


# ==========================================
# 6. 統一路徑配置 (Paths)
# ==========================================


# 專案根目錄 (假設 const.py 就在根目錄)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 核心目錄
DATA_DIR = os.path.join(ROOT_DIR, 'data')          # 輸入區
OUTPUT_DIR = os.path.join(ROOT_DIR, 'output')      # 輸出區
CONFIG_DIR = os.path.join(ROOT_DIR, 'configs')     # 規則設定檔區

# 資料庫路徑
DB_PATH = os.path.join(OUTPUT_DIR, 'Bills.db')

# 確保輸出目錄存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
