import const

# 建立別名簡化程式碼 (Alias)
TC = const.TransactionColumn

def ALL_TRANSACTION_COL_MAPPING():
    """
    主要用於 Parser 正規化後的標準欄位對應。
    這些 key 通常來自 const.py 中的定義。
    """
    return TC.get_mapping(
        TC.TXN_DATE, TC.POST_DATE, TC.CONV_DATE, TC.STAT_MON,
        TC.BANK_NAME, TC.CARD_TYPE, TC.CARD_NO, TC.MERCHANT,
        TC.MERCHANT_DISPLAY, TC.LOCATION, TC.CONSUMPTION_PLACE,
        TC.TXN_TYPE, TC.MOBILE_PAY, TC.VPC_NO, TC.VPC_TYPE,
        TC.CATEGORY, TC.SUB_CATEGORY, TC.CURRENCY, TC.CURR_AMOUNT,
        TC.PAY_CURR, TC.PAY_AMOUNT, TC.EC_PLATFORM
    )

def CARD_INFO_COL_MAPPING():
    """對應 dim_cards.csv"""
    return TC.get_mapping(
        TC.BANK_NAME, TC.CARD_TYPE, TC.CARD_NO, TC.IS_DUAL_CURRENCY, 
        TC.FX_TYPE, TC.CARD_START_DATE, TC.CARD_END_DATE,
        TC.ENABLE_REWARD_CALC
    )

def REWARD_PROGRAM_COL_MAPPING():
    """對應 dim_card_rewards_base.csv"""
    return TC.get_mapping(
        TC.BANK_NAME, TC.CARD_TYPE, TC.REWARD_PROGRAM, TC.BASE_REWARD_RATE,
        TC.MERCHANT_RATE, TC.REWARD_CYCLE, TC.CAP_AMOUNT, TC.REWARD_TYPE,
        TC.PROGRAM_START_DATE, TC.PROGRAM_END_DATE, TC.CALC_METHOD, TC.ROUND_STRATEGY
    )

def REWARD_CAMPAIGN_COL_MAPPING():
    """對應 dim_card_rewards_campaigns.csv"""
    return TC.get_mapping(
        TC.BANK_NAME, TC.CARD_TYPE, TC.CAMPAIGN_REWARD_PROGRAM, TC.CAMPAIGN_REWARD_RATE,
        TC.MERCHANT_RATE, TC.REWARD_CYCLE, TC.CAP_AMOUNT, TC.REWARD_TYPE,
        TC.PROGRAM_START_DATE, TC.PROGRAM_END_DATE, TC.CALC_METHOD, TC.ROUND_STRATEGY
    )

def MERCHANT_COL_MAPPING():
    """對應 dim_merchants.csv"""
    return TC.get_mapping(
        ('pattern', 'pattern'),                  # 單純字串覆蓋
        ('merchant', TC.MERCHANT_DISPLAY),       # CSV 欄位名稱映射為標準 SQL 名稱
        TC.PRIORITY, TC.CATEGORY, TC.SUB_CATEGORY, TC.RFM_EXCLUSION, TC.IS_NCCC_LISTED
    )

def PAYMENT_PROCESS_COL_MAPPING():
    """對應 dim_payment_process.csv"""
    return TC.get_mapping(
        TC.PROCESS_PATTERN, TC.PAYMENT_PROCESS, TC.PROCESS_PREFIX, TC.PRIORITY
    )

def EC_PLATFORM_COL_MAPPING():
    """對應 dim_ec_platform.csv"""
    return TC.get_mapping(
        TC.EC_PLATFORM_PATTERN, TC.EC_PLATFORM, TC.EC_PLATFORM_TYPE, TC.PRIORITY
    )

def REWARD_RULE_COL_MAPPING():
    """對應 bridge_reward_rules.csv"""
    return TC.get_mapping(
        TC.REWARD_PROGRAM, TC.MOBILE_PAY, TC.VPC_TYPE, TC.EC_PLATFORM, 
        TC.MERCHANT_DISPLAY, TC.PROGRAM_START_DATE, TC.PROGRAM_END_DATE, 
        TC.MERCHANT_RATE, TC.PRIORITY, TC.REWARD_CAL_BREAK
    )
