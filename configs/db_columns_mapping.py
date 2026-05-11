import const

def ALL_TRANSACTION_COL_MAPPING():
    """
    主要用於 Parser 正規化後的標準欄位對應。
    這些 key 通常來自 const.py 中的定義。
    """
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
            const.COL_VPC_NO: 'vpc_no',                 # 虛擬卡 No
            const.COL_VPC_TYPE: 'vpc_type',             # 虛擬卡類型
            const.COL_CATEGORY: 'category',             # 商業分類欄位
            const.COL_SUB_CATEGORY: 'sub_category',     # 商業次分類欄位
            const.COL_CURRENCY: 'currency_type',        # 消費幣別
            const.COL_CURR_AMOUNT: 'currency_amount',   # 消費幣別金額
            const.COL_PAY_CURR: 'payment_currency',     # 繳款幣別(繳信用卡款的指定幣別)
            const.COL_PAY_AMOUNT: 'payment_amount',     # 繳款金額(繳信用卡款的指定金額)
    }

def CARD_INFO_COL_MAPPING():
    """對應 dim_cards.csv"""
    return {
        'bank_name': 'bank_name',
        'card_type': 'card_type',
        'is_dual_currency': 'is_dual_currency',
        'fx_type': 'fx_type',
        'card_no': 'card_no',
        'is_active': 'is_active',
        'enable_reward_calc': 'enable_reward_calc',
        'vpc_no': 'vpc_no',
        'vpc_type': 'vpc_type'
    }

def REWARD_PROGRAM_COL_MAPPING():
    """對應 dim_card_rewards_base.csv"""
    return {
        'bank_name': 'bank_name',
        'card_type': 'card_type',
        'reward_program': 'reward_program',
        'base_rate': 'reward_rate',
        'merchant_rate': 'merchant_rate',
        'reward_cycle': 'reward_cycle',
        'cap_amount': 'cap_amount',
        'reward_unit': 'reward_type',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'calc_method': 'calc_method',
        'round_strategy': 'round_strategy'
    }

def REWARD_CAMPAIGN_COL_MAPPING():
    """對應 dim_card_rewards_campaigns.csv"""
    return {
        'bank_name': 'bank_name',
        'card_type': 'card_type',
        'campaign_name': 'campaign_name',
        'reward_rate': 'reward_rate',
        'reward_cycle': 'reward_cycle',
        'cap_amount': 'cap_amount',
        'reward_unit': 'reward_type',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'calc_method': 'calc_method',
        'round_strategy': 'round_strategy'
    }

def MERCHANT_COL_MAPPING():
    """對應 dim_merchants.csv"""
    return {
        'pattern': 'pattern',
        'merchant': 'merchant_display',
        'priority': 'priority',
        'category': 'category',
        'sub_category': 'sub_category',
        'rfm_exclusion': 'rfm_exclusion',
        'is_nccc_listed': 'is_nccc_listed'
    }

def PAYMENT_PROCESS_COL_MAPPING():
    """對應 dim_payment_process.csv"""
    return {
        'payment_process_pattern': 'payment_process_pattern',
        'payment_process': 'payment_process',
        'process_prefix': 'process_prefix',
        'priority': 'priority'
    }

def REWARD_RULE_COL_MAPPING():
    """對應 bridge_reward_rules.csv"""
    return {
        'reward_program': 'reward_program',
        'mobile_payment': 'mobile_payment',
        'vpc_type': 'vpc_type',
        'merchant_display': 'merchant_display',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'merchant_rate': 'merchant_rate',
        'priority': 'priority',
        'reward_cal_break': 'reward_cal_break'
    }


