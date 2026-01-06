# --- csv_handler.py ---
# 役割: CSVファイルの読み込み・書き込みを担当する
# rev: Merge Logic Integrated

import logging
import os
import csv
import re 
from datetime import datetime 
from typing import List, Set, Tuple, Dict, Any, Union, Optional

logger = logging.getLogger(__name__)

def _safe_convert_to_float(value_str: Any, default_val: Any = None) -> Optional[float]:
    """数値変換ヘルパー"""
    if value_str == 'N/A' or value_str is None or value_str == "":
        return default_val
    try:
        legacy_str = str(value_str).replace('日', '').strip()
        return float(legacy_str)
    except (ValueError, TypeError):
        return default_val

def load_existing_csv(csv_path: str, key_name: str = "年月日") -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    CSVを読み込み、データリストと既得日付セットを返す。
    """
    if not os.path.exists(csv_path):
        logger.info(f"CSVなし(新規): {csv_path}")
        return [], set() 
        
    data_list: List[Dict[str, Any]] = []
    existing_dates: Set[str] = set() 
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # 給与・賞与共通で数値変換したいキー候補
            target_int_keys = ['総支給額', '差引支給額', '賞与額', '控除合計', '所得税', '社会保険料計']
            target_float_keys = ['総時間外', '有給消化時間', '有給使用日数', '有給残日数']
            
            for row in reader:
                # 整数変換
                for k in target_int_keys:
                    if k in row:
                        try: row[k] = int(str(row[k]).replace(',', ''))
                        except: row[k] = 0
                
                # 浮動小数点変換
                for k in target_float_keys:
                    if k in row:
                        legacy_val = row.get(k)
                        row[k] = _safe_convert_to_float(legacy_val, default_val=None)

                data_list.append(row)
                
                # 既得セット作成
                d_val = row.get(key_name)
                if d_val:
                    if key_name == "年月日":
                        # 給与明細の互換性維持 (前方8文字)
                        existing_dates.add(d_val[0:8] if len(d_val) >= 8 else d_val)
                    else:
                        # 賞与など (完全一致)
                        existing_dates.add(d_val)

        logger.info(f"load_existing_csv: {len(data_list)}件読込 ({csv_path})")
        return data_list, existing_dates
        
    except Exception as e:
        logger.error(f"CSV読込エラー: {e}")
        return [], set()

def _sort_key_for_csv(item: Dict[str, Any]) -> datetime:
    """日付ソートキー生成"""
    date_str = item.get('年月日') or item.get('支給日', '')
    
    # 1. 令和XX年XX月XX日 (賞与)
    match_full = re.search(r'令和(\d+)年(\d+)月(\d+)日', date_str)
    if match_full:
        try:
            y = int(match_full.group(1)) + 2018
            m = int(match_full.group(2))
            d = int(match_full.group(3))
            return datetime(y, m, d)
        except: pass

    # 2. 令和XX年XX月 (給与)
    match_month = re.search(r'令和(\d+)年(\d+)月', date_str)
    if match_month:
        try:
            y = int(match_month.group(1)) + 2018
            m = int(match_month.group(2))
            return datetime(y, m, 1)
        except: pass
        
    return datetime.min

def save_to_csv(
    data_list: List[Dict[str, Any]], 
    root_dir: str, 
    csv_filename: str, 
    key_order: Optional[List[str]] = None
) -> Optional[str]:
    """CSV保存 (単純保存・ソート付き)"""
    if not data_list: return None
        
    output_dir = os.path.join(root_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    csv_abs = os.path.join(output_dir, csv_filename)
    csv_rel = os.path.join("output", csv_filename)
    
    # ヘッダー決定ロジック
    if key_order:
        headers = key_order
    else:
        # デフォルト (給与用)
        headers = [
            '年月日', '総支給額', '差引支給額', 
            '総時間外', '有給消化時間', '有給使用日数', '有給残日数'
        ]

    try:
        sorted_data = sorted(data_list, key=_sort_key_for_csv)
        
        with open(csv_abs, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore') 
            writer.writeheader()
            writer.writerows(sorted_data)
            
        logger.info(f"CSV保存完了: {csv_abs} ({len(sorted_data)}件)")
        return csv_rel
        
    except Exception as e: 
        logger.error(f"CSV保存エラー: {e}")
        return None

def merge_and_save_csv(
    new_data: List[Dict[str, Any]], 
    root_dir: str, 
    csv_filename: str, 
    key_name: str
) -> Optional[str]:
    """
    既存CSVを読み込み、新規データをマージ(更新・追加)して保存する統合関数。
    UI側で行っていたロジックをここに移動。
    """
    if not new_data:
        logger.info("merge_and_save_csv: 新規データがないためスキップ")
        return None

    output_dir = os.path.join(root_dir, "output")
    csv_path = os.path.join(output_dir, csv_filename)

    # 既存データの読み込み
    existing_data, _ = load_existing_csv(csv_path, key_name)
    
    # マージ処理:
    # 辞書を使って { "キー値": 行データ } の形にすると、
    # 既存データを新規データで上書き(Update)するのが容易になります。
    merged_map = {}

    # 1. 既存データをマップに入れる
    for item in existing_data:
        val = item.get(key_name)
        if val:
            merged_map[str(val)] = item
    
    # 2. 新規データで上書き/追加
    for item in new_data:
        val = item.get(key_name)
        if val:
            merged_map[str(val)] = item

    merged_list = list(merged_map.values())

    # ヘッダー順序の決定 (新規データのキー順を優先)
    # 新規データが持つ項目(列)でCSVを作り直すことで、スクレイピング項目が増えても対応できる
    headers = list(new_data[0].keys())

    # 保存実行
    return save_to_csv(merged_list, root_dir, csv_filename, key_order=headers)