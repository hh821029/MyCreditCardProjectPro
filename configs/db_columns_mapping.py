import const

def ALL_TRANSACTION_COL_MAPPING():
    return {
            const.COL_TXN_DATE: 'transaction_date',     # 消費日/消費授權日
            const.COL_POST_DATE: 'posting_date',        # 入帳日
            const.COL_CONV_DATE: 'conversion_date',     # 外幣交易的換算日期
            const.COL_STAT_MON: 'statement_month',      # 帳單月份
            const.COL_BANK_NAME: 'bank_name',           # 發卡銀行
            const.COL_CARD_TYPE: 'card_type',           # 卡別
            const.COL_CARD_NO: 'card_no',               # 卡號末四碼
            const.COL_MERCHANT: 'merchant_name',        # 商家名稱
            const.COL_MERCHANT_DISPLAY: 'merchant_display', # 清洗後商家名稱
            const.COL_LOCATION: 'merchant_location',    # 消費地
            const.COL_CONSUMPTION_PLACE: 'consumption_place',
            const.COL_TXN_TYPE: 'transaction_type',
            const.COL_MOBILE_PAY: 'mobile_payment',     # 行動支付註記
            const.COL_CATEGORY: 'category',             # 商業分類欄位
            const.COL_SUB_CATEGORY: 'sub_category',     # 商業次分類欄位
            const.COL_CURRENCY: 'currency_type',        # 消費幣別
            const.COL_CURR_AMOUNT: 'currency_amount',   # 消費幣別金額
            const.COL_PAY_CURR: 'payment_currency',     # 繳款幣別(繳信用卡款的指定幣別)
            const.COL_PAY_AMOUNT: 'payment_amount',     # 繳款金額(繳信用卡款的指定金額)
    }

def CARD_INFO_COL_MAPPING():
    return {
        'Bank_Name': 'bank_name',
        'Card_Type': 'card_type',
        'Is_Dual_Currency': 'is_dual_currency',
        'FX_type': 'fx_type',                           # 修正 CSV 中的小寫 t
        'Card_No': 'card_no',
        'Is_Active': 'is_active',
        'Enable_Reward_Calc': 'enable_reward_calc',
        'VPC_ID': 'vpc_id',
        'VPC_Type': 'vpc_type'
    }

def REWARD_PROGRAM_COL_MAPPING():
    return {
        'Bank_Name': 'bank_name',
        'Card_Type': 'card_type',
        'Reward_Program': 'reward_program',
        'Base_Rate': 'reward_rate',                     # CSV 裡是 Base_Rate
        'Merchant_Rate': 'merchant_rate',
        'Reward_Cycle': 'reward_cycle',
        'Cap_Amount': 'cap_amount',
        'Reward_Unit': 'reward_type',                   # CSV 裡是 Reward_Unit
        'Start_Date': 'start_date',
        'End_Date': 'end_date',
        'Calc_Method': 'calc_method',
        'Round_Strategy': 'round_strategy'
    }

def MERCHANT_COL_MAPPING():
    return {
        'Pattern': 'pattern',                           # 必備：正則匹配規則
        'Merchant': 'merchant_display',                 # 清洗後商家名稱 (Replacement)
        'Priority': 'priority',                         # 優先順序
        'Category': 'category',                         # 商業分類
        'Sub_Category': 'sub_category',                 # 商業次分類
        'RFM_Exclusion': 'rfm_exclusion',               # RFM 排除註記
        'IS_NCCC_Listed': 'is_nccc_listed'              # NCCC 名單註記
    }

def PAYMENT_GATEWAY_COL_MAPPING():
    return {
        'Pattern': 'gateway_display',                   # 支付平台在帳單上的顯示名稱關鍵字 (Regex)
        'GateWay': 'gateway_name',                      # 支付平台名稱 (如 LINE Pay, 街口)
        'Prefix_Label': 'gateway_prefix',               # 清洗後要增加的前綴詞
        'Priority': 'priority'                          # 處理優先順序
    }

def REWARD_RULE_COL_MAPPING():
    return {
        'Reward_Program': 'reward_program',
        'mobile_payment': 'mobile_payment',
        'merchant_display': 'merchant_display',
        'Start_Date': 'start_date',
        'End_Date': 'end_date',
        'Merchant_Rate': 'merchant_rate',
        'Priority': 'priority',
        'Reward_Cal_Break': 'reward_cal_break'
    }

def mapping_3to2():
    return {
        
        'TWN': 'TW', 'USA': 'US', 'JPN': 'JP', 'KOR': 'KR',
        'HKG': 'HK', 'SGP': 'SG', 'GBR': 'GB', 'CHN': 'CN',
        'IRL': 'IE', 'DEU': 'DE', 'FRA': 'FR', 'AUS': 'AU',
        'VNM': 'VN', 'THA': 'TH', 'MYS': 'MY', 'IDN': 'ID'
    }
    