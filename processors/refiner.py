# processors/refiner.py
import pandas as pd
import logging
import const
from .mapper import CardMapper
from .merchant import MerchantNormalizer, PaymentProcessTagger
from .classifier import TransactionClassifier

logger = logging.getLogger(__name__)

class DataRefiner:
    def __init__(self, config_dir: str, configs: dict = None):
        configs = configs or {}
        self.mapper = CardMapper(config_dir, rules=configs.get('cards'))
        self.merchant_normalizer = MerchantNormalizer(config_dir, rules=configs.get('merchants'))
        self.payment_tagger = PaymentProcessTagger(config_dir, rules=configs.get('gateways'))
        self.classifier = TransactionClassifier(config_dir, config=configs.get('txn_types'))

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df

        # [4/13 待處理事項] 初始化 Merchant_Display 欄位，初始值等於原始 Merchant
        if const.COL_MERCHANT_DISPLAY not in df.columns:
            df[const.COL_MERCHANT_DISPLAY] = df[const.COL_MERCHANT]
        
        # 1. 卡片歸戶 (Mapper)
        #    標記卡別、部分 Mobile_Payment (如玉山 Wallet)
        df = self.mapper.process(df)
      
       
        # 2. 支付管道識別 (Payment Gateway)
        #    注意：這裡只會填入 _Temp_Prefix 和 Mobile_Payment
        #    不會修改 Merchant，所以不會影響 Step 5 的 Regex 匹配
        df = self.payment_tagger.process(df)
        
        # 3. 商家正規化 (Merchant Normalization)
        #    依據 merchants.csv 替換商家名稱，結果存入 Merchant_Display
        df = self.merchant_normalizer.process(df)
        
        # 4. [新增] 最終前綴合併
        #    將 "LinePay－" 接到 "Merchant_Display" 前面
        df = self._apply_final_prefixes(df)

        # 5. 交易分類 (Transaction Classification)
        #    根據 Merchant_Display (SSOT) 進行分類
        df = self.classifier.process(df)
        
        return df

    def _apply_final_prefixes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        [修正版] 將暫存的支付前綴合併回 Merchant_Display 商家名稱
        特色：
        1. 強制 fillna('') 處理 np.nan
        2. 強制 replace('nan', '') 處理字串型別的 "nan"
        3. 確保 Merchant_Display 欄位也是字串，防止浮點數相加錯誤
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
            # 準備清洗後的商家名稱 (同樣防止 Merchant_Display 裡有 nan)
            merchant_display_clean = (
                df.loc[mask, const.COL_MERCHANT_DISPLAY]
                .fillna('')
                .astype(str)
                .replace('nan', '', regex=False)
                .str.strip()
            )

            # 4. 安全合併
            df.loc[mask, const.COL_MERCHANT_DISPLAY] = (
                prefix_clean[mask] + merchant_display_clean
            )
            
            # log 記錄一下到底合併了幾筆 (方便除錯)
            logger.info(f"✅ 已為 {mask.sum()} 筆交易於 Merchant_Display 合併支付前綴 (如: LinePay－XXX)")

        # 5. 移除暫存欄位 (Clean up)
        df = df.drop(columns=['_Temp_Prefix'], errors='ignore')
        
        return df