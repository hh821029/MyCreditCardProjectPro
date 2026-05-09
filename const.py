# const.py
import pandas as pd
import os

pd.set_option('future.no_silent_downcasting', True)


# ==========================================
# 1. 交易資料欄位 (Transactions)
# ==========================================
# 這些是我們希望在最終 CSV 看到的標準欄位名稱

# 交易日期資訊
COL_TXN_DATE = 'transaction_date'           # 交易日
COL_POST_DATE = 'posting_date'              # 入帳日
COL_CONV_DATE = 'conversion_date'          # 外幣折算日
COL_STAT_MON = 'statement_month'            # 帳單月份 (通常格式 YYYY-MM-01)

# 商店消費資訊
COL_MERCHANT = 'merchant'                   # (清洗前)交易說明/特店名稱
COL_MERCHANT_DISPLAY = 'merchant_display'   # (清洗後)交易說明/特店名稱
COL_LOCATION = 'merchant_location'          # 消費地 (國別)
COL_CONSUMPTION_PLACE = 'consumption_place' # (玉山專用) 原始消費地
COL_MOBILE_PAY = 'mobile_payment'           # 行動支付註記
COL_TXN_TYPE = 'transaction_type'           # 交易類別 (一般) 繳款、轉帳...
COL_CATEGORY = "category"                   # 消費類別 (食衣住行...)
COL_SUB_CATEGORY = "sub_category"           # 消費次類別 (點心、速食...)
COL_PROCESS_PATTERN = 'payment_process_pattern' # 支付平台/處理方式在帳單上的顯示名稱關鍵字 (如 LINE Pay, 街口)

# 消費金額資訊
COL_CURRENCY = 'currency_type'              # 原始幣別
COL_AMOUNT = 'amount'                       # 交易金額 (通用)
COL_CURR_AMOUNT = 'currency_amount'         # 外幣金額
COL_PAY_AMOUNT = 'payment_amount'           # 台幣應繳金額
COL_PAY_CURR = 'payment_currency'           # 繳款幣別

# 卡片資訊
COL_BANK_NAME = 'bank_name'                 # 銀行代碼
COL_CARD_NO = 'card_no'                     # 卡號末四碼
COL_CARD_TYPE = 'card_type'                 # 卡別(卡片名稱，目前無正附卡區分，後續可從規則定義中拆解)
COL_IS_DUAL_CURRENCY = 'is_dual_currency'   # 是否為雙幣卡
COL_FX_TYPE = 'fx_type'                     # 外幣交易類型 (一般消費、現金預借、分期付款)
COL_ACTIVE_STATUS = 'active_status'         # 卡片狀態 (啟用/停用)
COL_ENABLE_REWARD_CALC = 'enable_reward_calc'  # 是否啟用回饋計算
COL_VPC_ID = 'vpc_id'                       # 虛擬卡 ID (用於分辨同一張實體卡的不同虛擬卡)
COL_VPC_TYPE = 'vpc_type'                   # 虛擬卡類型 (如: Apple Pay, Google Pay, Samsung Pay)


# 其他資訊
COL_INS_PLN = 'installment_plan'            # 分期數(分期專用，預設為1代表不分期)
COL_PAYMENT_PROCESS = 'payment_process'     # 支付平台/處理方式名稱 (如 LINE Pay, 街口)
COL_PROCESS_PREFIX = 'process_prefix'       # 支付平台/處理方式前綴詞


# ==========================================
# 2. 回饋規則欄位 (Rewards Configs) - [新增]
# ==========================================
COL_REWARD_PROGRAM = 'reward_program'       # 紅利/回饋計畫名稱
COL_START_DATE = 'start_date'               # 適用起始日
COL_END_DATE = 'end_date'                   # 適用結束日
COL_REWARD_TYPE = 'reward_type'             # 回饋類型 (現金回饋、紅利點數、里程數等)
COL_REWARD_RATE = 'reward_rate'             # 回饋比率 (如一般消費的 0.01、網購的 0.02)
COL_REWARD_CYCLE = 'reward_cycle'           # 回饋計算週期 (如依帳單結帳週期、依消費日曆月、依消費日等)
COL_MERCHANT_RATE = 'merchant_rate'         # 特約商家回饋率 (同一個權益項目中，特店A回饋比率 0.02，特店B回饋比率 0.03)
COL_CAP_AMOUNT = 'cap_amount'               # 回饋上限
COL_CALC_METHOD = 'calc_method'             # 計算策略 (PER_ITEM / AGGREGATE)
COL_ROUND_STRATEGY = 'round_strategy'       # 四捨五入策略 (如無條件捨去、無條件進位、四捨五入到整數、四捨五入到小數點後兩位等)
COL_CONDITION = 'condition'                 # 條件標籤 (或 Regex 規則)



# ==========================================
# 3. 標準輸出欄位順序 (Schema Definition)
# ==========================================

# ==========================================
# 3-1. 寫入資料庫的交易資料標準欄位順序(Transactions Schema)
# ==========================================

STANDARD_COLUMNS = [
    COL_TXN_DATE, COL_POST_DATE, COL_STAT_MON, 
    COL_MERCHANT, COL_MERCHANT_DISPLAY, COL_LOCATION, 
    COL_CURRENCY, COL_CURR_AMOUNT, COL_CONV_DATE, 
    COL_PAY_AMOUNT, COL_PAY_CURR,
    COL_TXN_TYPE, COL_INS_PLN, COL_MOBILE_PAY, 
    COL_CARD_NO, COL_CARD_TYPE, COL_BANK_NAME
]




# ==========================================
# 4. 銀行關鍵字對照 (用來分派 Parser)
# ==========================================
BANK_KEYWORD_MAP = {
    '玉山': 'esun',
    '國泰': 'cube', '國泰世華': 'cube',
    '中信': 'ctbc', '中國信託': 'ctbc',
    '華南': 'hncb',
    '永豐': 'sinopac', 'DAWAY': 'sinopac'
}


# ==========================================
# 5. 統一型別定義表 (The Law / Schema)
# ==========================================
# 用於 BaseParser 或 Enforcer 統一強制轉型
# 格式: { 欄位名: '目標型別' }

COLUMN_TYPES = {
    # --- 數值區 (Float) ---
    # 消費金額相關
    COL_AMOUNT: 'float',
    COL_CURR_AMOUNT: 'float',
    COL_PAY_AMOUNT: 'float',
    
    # 回饋計算數字相關
    COL_REWARD_RATE: 'float',
    COL_MERCHANT_RATE: 'float',
    COL_CAP_AMOUNT: 'float',

    # 布林值區 (Boolean)
    COL_IS_DUAL_CURRENCY: 'bool',
    COL_ENABLE_REWARD_CALC: 'bool',

    # --- 字串區 (String) ---
    # 發卡銀行、卡號關聯資訊、虛擬卡資訊
    COL_CARD_NO: 'str',
    COL_CARD_TYPE: 'str',
    COL_FX_TYPE: 'str',
    COL_BANK_NAME: 'str',
    COL_VPC_ID: 'str',
    COL_VPC_TYPE: 'str',

    # 消費關聯資訊
    COL_MERCHANT: 'str',
    COL_MERCHANT_DISPLAY: 'str',
    COL_LOCATION: 'str',
    COL_CONSUMPTION_PLACE: 'str',
    COL_MOBILE_PAY: 'str',
    COL_PROCESS_PATTERN: 'str',
    COL_PAYMENT_PROCESS: 'str',
    COL_PROCESS_PREFIX: 'str',
    COL_CATEGORY: 'str',
    COL_SUB_CATEGORY: 'str',
    COL_CURRENCY: 'str',
    COL_PAY_CURR: 'str',
    COL_TXN_TYPE: 'str',
    COL_INS_PLN: 'str',

    # 消費回饋方案判斷相關
    COL_REWARD_PROGRAM: 'str',
    COL_REWARD_TYPE: 'str',
    COL_CALC_METHOD: 'str',
    COL_CONDITION: 'str',
    COL_REWARD_CYCLE: 'str',
    COL_ROUND_STRATEGY: 'str',

    # --- 日期區 (Date/Timestamp) ---
    # 消費日期相關
    COL_TXN_DATE: 'date',
    COL_POST_DATE: 'date',
    COL_CONV_DATE: 'date',
    COL_STAT_MON: 'date',
    
    # 回饋方案適用期間
    COL_START_DATE: 'date',
    COL_END_DATE: 'date'
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
