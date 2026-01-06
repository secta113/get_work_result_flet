# Version: 1.0
import json
import os
from typing import List
from core.commons import logger, APP_BUNDLE_DIR

# 定数の定義
DATA_DIR = os.path.join(APP_BUNDLE_DIR, "data")
JSON_FILE_NAME = "special_holidays.json"
JSON_PATH = os.path.join(DATA_DIR, JSON_FILE_NAME)

def ensure_data_dir_exists():
    """dataディレクトリが存在しない場合は作成します。"""
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
            logger.info(f"Created data directory: {DATA_DIR}")
        except OSError as e:
            logger.error(f"Failed to create data directory: {e}")

def load_special_holidays() -> List[str]:
    """特別休暇設定ファイル(JSON)を読み込みます。

    Returns:
        List[str]: 日付文字列(YYYY-MM-DD)のリスト。読み込み失敗時は空リストを返します。
    """
    if not os.path.exists(JSON_PATH):
        logger.info(f"Special holidays file not found at: {JSON_PATH}")
        return []

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.info(f"Loaded {len(data)} special holidays from {JSON_PATH}")
                return data
            else:
                logger.warning(f"Invalid format in {JSON_PATH}: Expected a list.")
                return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from {JSON_PATH}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading special holidays: {e}")
        return []

def save_special_holidays(data: List[str]) -> bool:
    """特別休暇データをJSONファイルに保存します。

    Args:
        data (List[str]): 保存する日付文字列のリスト。

    Returns:
        bool: 保存に成功した場合はTrue、失敗した場合はFalse。
    """
    ensure_data_dir_exists()
    
    try:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved {len(data)} special holidays to {JSON_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to save special holidays to {JSON_PATH}: {e}")
        return False