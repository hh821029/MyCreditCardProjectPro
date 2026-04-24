import const

def ALL_TRANSACTION_COL_MAPPING():
    return {
            const.COL_TXN_DATE: 'transaction_date',     # 消費日/消費授權日
            const.COL_POST_DATE: 'posting_date',        # 入帳日
            const.COL_CONV_DATE: 'conversion_date',     # 外幣交易的換算日期
            const.COL_STAT_MON: 'statement_month',      # 帳單月份
            const.COL_BANK_NAME: 'bank_name',           # 發卡銀行
            const.COL_CARD_TYPE: 'card_name',           # 卡別
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
        const.COL_CARD_NO: 'card_no',                   # 卡號末四碼
        const.COL_CARD_TYPE: 'card_name',               # 卡別
        const.COL_BANK_NAME: 'bank_name',               # 發卡銀行
        const.COL_IS_DUAL_CURRENCY: 'is_dual_currency', # 是否為雙幣卡
        const.COL_FX_TYPE: 'fx_type',                   # 外幣交易類型
        const.COL_VPC_ID: 'vpc_id',                     # 虛擬卡ID(如果有的話)
        const.COL_VPC_TYPE: 'vpc_type',                 # 虛擬卡類型(Apple Pay, Google Pay, Samsung Pay, etc.)
    }