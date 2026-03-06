# const.py

# ==========================================
# 1. 欄位名稱常數 (Single Source of Truth)
# ==========================================
# 這些是我們希望在最終 CSV 看到的標準欄位名稱
COL_TXN_DATE = 'Transaction_Date'           # 交易日
COL_POST_DATE = 'Posting_Date'              # 入帳日
COL_MERCHANT = 'Merchant'                   # 交易說明/特店名稱
COL_LOCATION = 'Merchant_Location'          # 消費地 (國別)
COL_CONSUMPTION_PLACE = 'Consumption_Place' # (玉山專用) 原始消費地
COL_CONV_DATE = 'Conversion_Date'           # 外幣折算日
COL_CURRENCY = 'Currency_Type'              # 原始幣別
COL_AMOUNT = 'Amount'                       # 交易金額 (通用)
COL_CURR_AMOUNT = 'Currency_Amount'         # 外幣金額
COL_PAY_AMOUNT = 'Payment_Amount'           # 台幣應繳金額
COL_PAY_CURR = 'Payment_Currency'           # 繳款幣別
COL_CARD_NO = 'Card_No'                     # 卡號末四碼
COL_CARD_TYPE = 'Card_Type'                 # 卡別 (正/附)
COL_TXN_TYPE = 'Transaction_Type'           # 交易類別 (一般)
COL_INS_PLN = 'Installment_Plan'            # 分期數(分期專用，預設為1代表不分期)
COL_MOBILE_PAY = 'Mobile_Payment'           # 行動支付註記
COL_BANK_NAME = 'Bank_Name'                 # 銀行代碼
COL_CATEGORY = "Category"                   # 消費類別 (食衣住行...)
COL_SUB_CATEGORY = "Sub_Category"           # 消費次類別 (點心、速食...)


# ==========================================
# 2. 標準輸出欄位順序 (Schema Definition)
# ==========================================
# 所有 Parser 輸出時，建議依照此順序排列 (或至少包含這些欄位)
STANDARD_COLUMNS = [
    COL_TXN_DATE, COL_POST_DATE, COL_MERCHANT, COL_LOCATION, 
    COL_CURRENCY, COL_CURR_AMOUNT, COL_CONV_DATE, 
    COL_PAY_AMOUNT, COL_PAY_CURR,
    COL_TXN_TYPE, COL_INS_PLN, COL_MOBILE_PAY, 
    COL_CARD_NO, COL_CARD_TYPE, COL_BANK_NAME

]

# ==========================================
# 3. 銀行關鍵字對照 (用來分派 Parser)
# ==========================================
BANK_KEYWORD_MAP = {
    '玉山': 'esun',
    '國泰': 'cube', '國泰世華': 'cube',
    '中信': 'ctbc', '中國信託': 'ctbc',
    '華南': 'hncb',
    '永豐': 'sinopac', 'DAWAY': 'sinopac'
}

# ==========================================
# 4. 資料型別定義 (Schema Definition)
# ==========================================
# 用於 BaseParser 統一強制轉型，避免 pd.concat 發生警告
# 格式: { 欄位名: '目標型別' }

COLUMN_TYPES = {
    # --- 數值區 (會強制轉為 float，處理逗號) ---
    COL_AMOUNT: 'float',
    COL_CURR_AMOUNT: 'float',   # 消費金額，一般國外交易和台幣跨境交易時會有值
    COL_PAY_AMOUNT: 'float',    # 繳款金額，通常是台幣金額，或是外幣交易的原幣金額

    # --- 字串區 (會強制轉為 string，並保留 None) ---
    # ----- 商店消費關聯 -----
    COL_MERCHANT: 'str',        # 交易說明/特店名稱
    COL_LOCATION: 'str',        # 消費地 (國別)
    COL_CONSUMPTION_PLACE: 'str',   # 消費地補充
    COL_MOBILE_PAY: 'str',      # 行動支付標記 (LinePay、ApplePay...)
    COL_CATEGORY: 'str',        # 消費分類
    COL_SUB_CATEGORY: 'str',    # 消費次分類
    # ----- 消費幣別關聯 -----
    COL_CURRENCY: 'str',        # 消費幣別
    COL_PAY_CURR: 'str',        # 繳款幣別
    # ----- 卡片資訊 -----
    COL_CARD_NO: 'str',         # 卡號末四碼，必須是字串
    COL_CARD_TYPE: 'str',       # 卡片類別
    COL_BANK_NAME: 'str',       # 銀行名稱 (用來分派 Parser，或是後續分析用)
    # ----- 其他 -----
    COL_TXN_TYPE: 'str',        # 交易類別 (一般、繳款、轉帳...)
    COL_INS_PLN: 'str',         # 分期期數通常當字串處理較方便 (e.g. "3/12")

    # --- 日期區 (主要由 transform_common_dates 處理，這裡僅作標記) ---
    COL_TXN_DATE: 'date',       # 交易日
    COL_POST_DATE: 'date',      # 入帳日
    COL_CONV_DATE: 'date'       # 外幣折算日
}