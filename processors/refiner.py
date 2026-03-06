# processors/refiner.py
import pandas as pd
import logging
import re
import const
from .mapper import CardMapper
from .merchant import MerchantNormalizer, PaymentGatewayTagger
from .classifier import TransactionClassifier

logger = logging.getLogger(__name__)

class DataRefiner:
    def __init__(self, config_dir: str):
        self.mapper = CardMapper(config_dir)
        self.merchant_normalizer = MerchantNormalizer(config_dir)
        self.payment_tagger = PaymentGatewayTagger(config_dir)
        self.classifier = TransactionClassifier(config_dir)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        
        # 1. 卡片歸戶 (Mapper)
        #    標記卡別、部分 Mobile_Payment (如玉山 Wallet)
        df = self.mapper.process(df)
      
       
        # 2. 支付管道識別 (Payment Gateway)
        #    注意：這裡只會填入 _Temp_Prefix 和 Mobile_Payment
        #    不會修改 Merchant，所以不會影響 Step 5 的 Regex 匹配
        df = self.payment_tagger.process(df)
        
        # 3. 商家正規化 (Merchant Normalization)
        #    依據 merchants.csv 替換商家名稱 (e.g. "MOMO" -> "MOMO購物網")
        df = self.merchant_normalizer.process(df)
        
        # 4. [新增] 最終前綴合併
        #    將 "LinePay－" 接到 "MOMO購物網" 前面
        df = self._apply_final_prefixes(df)

        # 5. 交易分類 (Transaction Classification)
        #    根據 transaction_types.yaml 定義的關鍵字，對交易進行分類，填入 Transaction_Type
        df = self.classifier.process(df)
        
        return df

    def _apply_final_prefixes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        [修正版] 將暫存的支付前綴合併回商家名稱
        特色：
        1. 強制 fillna('') 處理 np.nan
        2. 強制 replace('nan', '') 處理字串型別的 "nan"
        3. 確保 Merchant 欄位也是字串，防止浮點數相加錯誤
        """
        # 1. 預防性建立欄位
        if '_Temp_Prefix' not in df.columns:
            df['_Temp_Prefix'] = ''

        # 2. 核彈級清洗前綴欄位 (關鍵修正)
        # 先填補真正的空值 -> 轉字串 -> 把轉出來的 "nan" 字串殺掉 -> 去除頭尾空白
        prefix_clean = (
            df['_Temp_Prefix']
            .fillna('')
            .astype(str)
            .replace('nan', '', regex=False)  # 這是這段最重要的修正
            .str.strip()
        )

        # 3. 找出真正有內容的前綴 (過濾掉空字串)
        mask = prefix_clean != ''

        if mask.any():
            # 準備商家名稱 (同樣防止 Merchant 裡有 nan)
            merchant_clean = (
                df.loc[mask, const.COL_MERCHANT]
                .fillna('')
                .astype(str)
                .replace('nan', '', regex=False)
                .str.strip()
            )

            # 4. 安全合併
            df.loc[mask, const.COL_MERCHANT] = (
                prefix_clean[mask] + merchant_clean
            )
            
            # log 記錄一下到底合併了幾筆 (方便除錯)
            logger.info(f"✅ 已為 {mask.sum()} 筆交易合併支付前綴 (如: LinePay－XXX)")

        # 5. 移除暫存欄位 (Clean up)
        df = df.drop(columns=['_Temp_Prefix'], errors='ignore')
        
        return df