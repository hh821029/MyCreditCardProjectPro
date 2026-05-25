# processors/ml_fallback.py
import pandas as pd
import logging
from typing import Optional
import const

logger = logging.getLogger(__name__)

class MLMerchantPredictor:
    """
    [機器學習 Fallback 預測器]
    負責處理規則引擎無法匹配的未知商家，並給出預測結果。
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.is_ready = False
        self._load_model()

    def _load_model(self):
        """載入 scikit-learn 預先訓練好的模型與 TF-IDF 向量化器"""
        try:
            # 這裡放置實際載入 model 的邏輯 (例如 joblib.load)
            # self.model = joblib.load(self.model_path)
            # self.vectorizer = joblib.load('vectorizer.pkl')
            self.is_ready = True
            logger.info("✅ ML Merchant Predictor 模型載入成功")
        except Exception as e:
            logger.warning(f"⚠️ 找不到 ML 模型或載入失敗，將關閉 ML Fallback 功能: {e}")
            self.is_ready = False

    def process(self, df: pd.DataFrame, target_mask: pd.Series) -> pd.DataFrame:
        """
        :param df: 原始 DataFrame
        :param target_mask: 只有為 True 的列才需要進行預測
        """
        if not self.is_ready or not target_mask.any():
            return df
            
        # 擷取需要預測的資料 (例如原始商家名稱)
        unknown_merchants = df.loc[target_mask, const.COL_MERCHANT].astype(str).str.strip()
        
        # ==========================================
        # [模擬] 實際使用時，這裡是特徵提取與預測邏輯
        # X = self.vectorizer.transform(unknown_merchants)
        # preds = self.model.predict(X)
        # confidences = self.model.predict_proba(X).max(axis=1)
        # ==========================================
        
        # 假設預測結果 (模擬)
        df.loc[target_mask, const.COL_MERCHANT_DISPLAY] = unknown_merchants + " (ML預測)"
        
        # 標記來源與信心度，幫助人工覆核
        df.loc[target_mask, 'Data_Source'] = 'ML_Fallback'
        df.loc[target_mask, 'ML_Confidence'] = 0.85 # 填入真實信心度
        
        logger.info(f"🤖 已透過機器學習模型完成 {target_mask.sum()} 筆未知商家的預測")
        return df