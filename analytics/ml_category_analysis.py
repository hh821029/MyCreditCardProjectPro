import pandas as pd
import os
import glob

def analyze_merchant_categories(config_dir: str):
    """
    讀取 config 目錄下的 dim_merchants.csv 與 dim_merchants_private.csv，
    統計並分析目前的 Category 分佈狀況，幫助制定統一的分類策略。
    """
    print(f"🔍 開始盤點 {config_dir} 下的商家分類...")
    
    # 尋找所有 merchant 相關的規則表
    target_files = glob.glob(os.path.join(config_dir, 'dim_merchants*.csv'))
    
    if not target_files:
        print("⚠️ 找不到任何 dim_merchants*.csv 檔案")
        return
        
    dfs = []
    for file in target_files:
        try:
            df = pd.read_csv(file)
            # 統一欄位名稱，避免大小寫不一致
            df.columns = df.columns.str.strip().str.lower()
            if 'category' in df.columns:
                df['source_file'] = os.path.basename(file)
                dfs.append(df[['category', 'source_file']])
        except Exception as e:
            print(f"❌ 讀取 {file} 失敗: {e}")
            
    if not dfs:
        print("⚠️ 檔案中找不到 category 欄位")
        return
        
    # 合併所有資料
    all_categories = pd.concat(dfs, ignore_index=True)
    
    # 清洗分類名稱 (去空白)
    all_categories['category'] = all_categories['category'].astype(str).str.strip()
    # 排除空值
    all_categories = all_categories[~all_categories['category'].isin(['nan', 'None', ''])]
    
    # 統計數量
    stats = all_categories['category'].value_counts().reset_index()
    stats.columns = ['Category', 'Rule_Count']
    
    print("\n📊 目前的分類統計 (依規則數量排序):")
    print("-" * 40)
    print(stats.to_string(index=False))
    print("-" * 40)
    print(f"💡 總共發現 {len(stats)} 種不同的分類。建議將數量極少 (<= 3) 的分類往上合併，並將總分類數控制在 10 ~ 15 種以內，以利機器學習訓練。")

if __name__ == "__main__":
    # 請確認這是你的 configs 資料夾路徑
    config_dir = r'd:\記帳用EXCEL\MyCreditCardProjectPro\configs'
    analyze_merchant_categories(config_dir)