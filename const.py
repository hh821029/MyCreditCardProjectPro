# const.py

# ==========================================
# 1. 交易資料欄位 (Transactions)
# ==========================================
# 這些是我們希望在最終 CSV 看到的標準欄位名稱

# 交易日期資訊
COL_TXN_DATE = 'Transaction_Date'           # 交易日
COL_POST_DATE = 'Posting_Date'              # 入帳日
COL_CONV_DATE = 'Conversion_Date'          # 外幣折算日
COL_STAT_MON = 'Statement_Month'            # 帳單月份 (通常格式 YYYY-MM-01)

# 商店消費資訊
COL_MERCHANT = 'Merchant'                   # (清洗前)交易說明/特店名稱
COL_MERCHANT_DISPLAY = 'Merchant_Display'   # (清洗後)交易說明/特店名稱
COL_LOCATION = 'Merchant_Location'          # 消費地 (國別)
COL_CONSUMPTION_PLACE = 'Consumption_Place' # (玉山專用) 原始消費地
COL_MOBILE_PAY = 'Mobile_Payment'           # 行動支付註記
COL_TXN_TYPE = 'Transaction_Type'           # 交易類別 (一般) 繳款、轉帳...
COL_CATEGORY = "Category"                   # 消費類別 (食衣住行...)
COL_SUB_CATEGORY = "Sub_Category"           # 消費次類別 (點心、速食...)

# 消費金額資訊
COL_CURRENCY = 'Currency_Type'              # 原始幣別
COL_AMOUNT = 'Amount'                       # 交易金額 (通用)
COL_CURR_AMOUNT = 'Currency_Amount'         # 外幣金額
COL_PAY_AMOUNT = 'Payment_Amount'           # 台幣應繳金額
COL_PAY_CURR = 'Payment_Currency'           # 繳款幣別

# 卡片資訊
COL_BANK_NAME = 'Bank_Name'                 # 銀行代碼
COL_CARD_NO = 'Card_No'                     # 卡號末四碼
COL_CARD_TYPE = 'Card_Type'                 # 卡別(卡片名稱，目前無正附卡區分，後續可從規則定義中拆解)

# 其他資訊
COL_INS_PLN = 'Installment_Plan'            # 分期數(分期專用，預設為1代表不分期)


# ==========================================
# 2. 回饋規則欄位 (Rewards Configs) - [新增]
# ==========================================
COL_RULE_NAME = 'Rule_Name'                 # 規則名稱 (如: 基礎回饋、網購加碼)
COL_START_DATE = 'Start_Date'               # 適用起始日
COL_END_DATE = 'End_Date'                   # 適用結束日
COL_REWARD_RATE = 'Reward_Rate'             # 回饋比率 (如 0.01)
COL_CAP_AMOUNT = 'Cap_Amount'               # 回饋上限金額
COL_CALC_METHOD = 'Calc_Method'             # 計算策略 (PER_ITEM / AGGREGATE)
COL_CONDITION = 'Condition'                 # 條件標籤 (或 Regex 規則)
COL_TARGET_CARD = 'Target_Card'             # 目標卡號 (用於規則對齊)
COL_TARGET_BANK = 'Target_Bank'             # 目標銀行


# ==========================================
# 3. 標準輸出欄位順序 (Schema Definition)
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
    COL_AMOUNT: 'float',
    COL_CURR_AMOUNT: 'float',
    COL_PAY_AMOUNT: 'float',
    COL_REWARD_RATE: 'float',
    COL_CAP_AMOUNT: 'float',

    # --- 字串區 (String) ---
    COL_MERCHANT: 'str',
    COL_MERCHANT_DISPLAY: 'str',
    COL_LOCATION: 'str',
    COL_CONSUMPTION_PLACE: 'str',
    COL_MOBILE_PAY: 'str',
    COL_CATEGORY: 'str',
    COL_SUB_CATEGORY: 'str',
    COL_CURRENCY: 'str',
    COL_PAY_CURR: 'str',
    COL_CARD_NO: 'str',
    COL_CARD_TYPE: 'str',
    COL_BANK_NAME: 'str',
    COL_TXN_TYPE: 'str',
    COL_INS_PLN: 'str',
    COL_RULE_NAME: 'str',
    COL_CALC_METHOD: 'str',
    COL_CONDITION: 'str',
    COL_TARGET_CARD: 'str',
    COL_TARGET_BANK: 'str',

    # --- 日期區 (Date/Timestamp) ---
    COL_TXN_DATE: 'date',
    COL_POST_DATE: 'date',
    COL_CONV_DATE: 'date',
    COL_STAT_MON: 'date',
    COL_START_DATE: 'date',
    COL_END_DATE: 'date'
}


# ==========================================
# 6. 統一路徑配置 (Paths)
# ==========================================
import os

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
