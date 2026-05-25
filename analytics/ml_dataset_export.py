import pandas as pd
import os
import logging
import sys

# 將專案根目錄加入 sys.path 以便引用 const
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import const

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_training_data(processed_file_path: str, output_path: str):
    """
    從已經過 Rule-based 處理的歷史帳單中，萃取機器學習訓練資料。
    
    :param processed_file_path: 已經處理完畢的帳單明細 (CSV/Excel)
    :param output_path: 輸出的訓練資料集路徑
    """
    if not os.path.exists(processed_file_path):
        logger.error(f"找不到處理後的帳單檔案: {processed_file_path}")
        return
        
    # 1. 讀取歷史資料
    logger.info(f"讀取歷史資料: {processed_file_path}")
    if processed_file_path.endswith('.csv'):
        df = pd.read_csv(processed_file_path)
    else:
        df = pd.read_excel(processed_file_path)
        
    # 2. 篩選出「由規則引擎 (Rule-based)」成功處理的資料
    # 排除原本就被判定為 ML_Fallback 的資料，避免模型學到自己猜錯的結果 (Feedback Loop 污染)
    if 'Data_Source' in df.columns:
        df = df[df['Data_Source'] != 'ML_Fallback']
        
    # 3. 定義 X (特徵) 與 Y (標籤)
    # X: 原始商家名稱 (Merchant)
    # Y1: 正規化後的商家名稱 (Merchant_Display)
    # Y2: 交易分類 (Transaction_Type)
    features = [const.COL_MERCHANT]
    targets = [const.COL_MERCHANT_DISPLAY, const.COL_TXN_TYPE, const.COL_CATEGORY]
    
    # 確保欄位存在
    available_cols = [col for col in features + targets if col in df.columns]
    ml_df = df[available_cols].copy()
    assert isinstance(ml_df, pd.DataFrame), "ml_df must be a pandas DataFrame"
    
    # 去除空值 (只取有成功標記的資料)
    ml_df = ml_df.dropna(subset=[const.COL_MERCHANT])
    
    # 4. 匯出 Dataset
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ml_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    logger.info(f"✅ 成功匯出 {len(ml_df)} 筆訓練資料至: {output_path}")

if __name__ == "__main__":
    # 替換為你實際處理後的帳單輸出路徑
    export_training_data(
        processed_file_path=r'd:\記帳用EXCEL\MyCreditCardProjectPro\output\processed_bills.csv',
        output_path=r'd:\記帳用EXCEL\MyCreditCardProjectPro\data\ml_training_dataset.csv'
    )