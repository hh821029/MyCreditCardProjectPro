import os
import pandas as pd
import yaml
import logging
from typing import Optional, Union, Dict, Any
from loaders.schema_enforcer import SchemaEnforcer

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    通用配置載入器，遵循 GEMINI.md 規範：
    1. 編碼嘗試：UTF-8 -> Big5 -> cp950
    2. 支援私有檔合併策略 (Append / Replace)
    """

    @staticmethod
    def _read_csv_with_encoding(file_path: str) -> pd.DataFrame:
        """依序嘗試編碼讀取 CSV"""
        encodings = ['utf-8', 'big5', 'cp950']
        for enc in encodings:
            try:
                # 測試讀取前幾行，看是否會報 UnicodeDecodeError
                df = pd.read_csv(file_path, encoding=enc)
                logger.info(f"✅ 成功使用 {enc} 讀取: {os.path.basename(file_path)}")
                return df
            except (UnicodeDecodeError, LookupError):
                continue
            except Exception as e:
                logger.error(f"❌ 讀取 {file_path} 時發生非預期錯誤 ({enc}): {e}")
                break
        
        logger.error(f"❌ 無法識別 {file_path} 的編碼 (嘗試過 UTF-8, Big5, cp950)")
        return pd.DataFrame()

    @classmethod
    def load_config(cls, config_dir: str, base_name: str, strategy: str = 'append') -> pd.DataFrame:
        """
        載入配置的主入口
        :param config_dir: 設定檔目錄
        :param base_name: 基礎檔名 (不含副檔名，如 'dim_merchants')
        :param strategy: 'append' (合併) 或 'replace' (私有檔優先且取代)
        :return: 合併後的 DataFrame
        """
        base_file = os.path.join(config_dir, f"{base_name}.csv")
        private_file = os.path.join(config_dir, f"{base_name}_private.csv")
        
        df_base = pd.DataFrame()
        if os.path.exists(base_file):
            df_base = cls._read_csv_with_encoding(base_file)
        else:
            logger.warning(f"⚠️ 找不到基礎設定檔: {base_file}")

        # 若無私有檔，直接對基礎檔執法並回傳
        if not os.path.exists(private_file):
            return SchemaEnforcer.enforce(df_base)

        # 處理私有檔
        df_private = cls._read_csv_with_encoding(private_file)
        if df_private.empty:
            return SchemaEnforcer.enforce(df_base)

        # 根據策略決定最終 DataFrame
        if strategy.lower() == 'replace':
            logger.info(f"🔄 使用 Replace 策略：{base_name}_private 取代基礎檔")
            final_df = df_private
        else:
            logger.info(f"➕ 使用 Append 策略：合併 {base_name} 與 {base_name}_private")
            final_df = pd.concat([df_base, df_private], ignore_index=True)

        # 統一執行型別執法
        return SchemaEnforcer.enforce(final_df)

    @classmethod
    def load_yaml(cls, config_dir: str, file_name: str) -> Dict[str, Any]:
        """載入 YAML 設定 (目前暫不支援 Append/Replace，僅做編碼處理)"""
        file_path = os.path.join(config_dir, file_name)
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ 找不到 YAML 設定檔: {file_path}")
            return {}

        encodings = ['utf-8', 'big5', 'cp950']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    data = yaml.safe_load(f)
                    logger.info(f"✅ 成功使用 {enc} 讀取 YAML: {file_name}")
                    return data or {}
            except (UnicodeDecodeError, yaml.YAMLError):
                continue
        
        logger.error(f"❌ 無法讀取 YAML: {file_name}")
        return {}
