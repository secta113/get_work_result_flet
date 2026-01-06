# --- summary_calculator.py ---
# 役割: 読み込んだデータリストに基づき、サマリー（集計）を行う

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Iterable, Union

logger = logging.getLogger(__name__)

def _parse_year_month_from_date_str(date_str: str) -> Optional[Tuple[int, int]]:
    """
    年月日文字列 (例: "令和05年03月度給与") から (西暦, 月) を抽出する。

    Args:
        date_str (str): '年月日' カラムの文字列。

    Returns:
        Optional[Tuple[int, int]]:
            (西暦, 月) のタプル。パース失敗時は None。
    """
    if not date_str:
        return None
    year_match = re.search(r'令和(\d+)年', date_str)
    month_match = re.search(r'年(\d+)月', date_str)
    if year_match and month_match:
        try:
            reiwa_year = int(year_match.group(1))
            year = reiwa_year + 2018 # 令和 -> 西暦
            month = int(month_match.group(1))
            return (year, month)
        except (ValueError, TypeError):
            pass
    logger.warning(f"_parse_year_month_from_date_str: パース失敗: {date_str}")
    return None

def _sum_safe(items: Iterable[Any]) -> Union[int, float]:
    """
    イテラブル内の数値 (int/float) のみを合計する。
    "N/A" や文字列、None などは無視 (0として加算) する。

    Args:
        items (Iterable[Any]): 合計対象のイテラブル (例: [100, "N/A", 50.5])。

    Returns:
        Union[int, float]: 合計値。
    """
    total = 0
    for item in items:
        if isinstance(item, (int, float)):
            total += item
    return total

def calculate_rekigun_summary(data_list_for_year: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    指定された年のデータリストに基づき、暦年 (1-12月) の集計を行う。
    
    Notes:
        この関数に渡されるリスト (data_list_for_year) は、
        計算用に "N/A" が 0.0 に変換済みのリストであることを前提とする。
        ただし、最新月の有給情報 (latest_*) は、呼び出し元 (main_controller) が
        "N/A" を保持したオリジナルデータで上書きすることを想定し、
        ここでは "N/A" (または 0.0) を設定する。

    Args:
        data_list_for_year (List[Dict[str, Any]]): 
            集計対象のデータリスト (UI指定年/1年分)。
            "N/A" は 0.0 に変換済みであること。

    Returns:
        Dict[str, Any]: 集計結果の辞書。
    """
    
    default_summary = {
        "total_pay": 0, "total_net_pay": 0, "total_overtime": 0.0, 
        "latest_paid_leave_time": "N/A",
        "latest_paid_leave_used_days": "N/A",
        "latest_paid_leave_remaining_days": "N/A"
    }
    
    if not data_list_for_year:
        logger.info("calculate_rekigun_summary: 対象データが0件のため、デフォルト値を返します。")
        return default_summary

    # --- 集計 (N/A は 0.0 変換済みのため、_sum_safe が安全に動作する) ---
    total_pay = _sum_safe(item.get('総支給額', 0) for item in data_list_for_year)
    total_net_pay = _sum_safe(item.get('差引支給額', 0) for item in data_list_for_year)
    total_overtime = _sum_safe(item.get('総時間外', 0) for item in data_list_for_year)
    
    # --- 最新月の情報取得 ---
    # (data_list_for_year はソート済みであることを前提とする)
    latest_item = data_list_for_year[-1]
    # "N/A" が 0.0 に変換されているため、ここで取得する値は 0.0 になる可能性がある
    latest_paid_leave_time = latest_item.get('有給消化時間', 'N/A')
    latest_paid_leave_used_days = latest_item.get('有給使用日数', 'N/A')
    latest_paid_leave_remaining_days = latest_item.get('有給残日数', 'N/A')

    summary_data = {
        "total_pay": total_pay, 
        "total_net_pay": total_net_pay, 
        "total_overtime": total_overtime, 
        "latest_paid_leave_time": latest_paid_leave_time,
        "latest_paid_leave_used_days": latest_paid_leave_used_days,
        "latest_paid_leave_remaining_days": latest_paid_leave_remaining_days
    }
    logger.info(f"暦年サマリー計算完了 (対象 {len(data_list_for_year)} 件): {summary_data}")
    return summary_data

def calculate_nendo_overtime(all_data_list: List[Dict[str, Any]], target_rekigun_year: int) -> float:
    """
    全期間データリストに基づき、指定された暦年 (target_rekigun_year) を基準とした
    「年度」(当年4月～翌年3月) の時間外合計を計算する。

    Args:
        all_data_list (List[Dict[str, Any]]): 
            全期間のデータリスト ("N/A" を含むオリジナル)。
        target_rekigun_year (int): 
            基準とする暦年 (UI指定年)。 (例: 2023)
            この場合、2023/4～2024/3 の集計が行われる。

    Returns:
        float: 年度時間外の合計時間。
    """
    nendo_overtime_total = 0.0
    
    if not all_data_list:
        return 0.0
        
    nendo_start_year = target_rekigun_year     # 2023年
    nendo_end_year = target_rekigun_year + 1  # 2024年
    
    logger.info(f"calculate_nendo_overtime: {nendo_start_year}年度 ( {nendo_start_year}/4～{nendo_end_year}/3 ) の集計を開始...")

    for item in all_data_list:
        date_str = item.get('年月日', '') 
        parsed_date = _parse_year_month_from_date_str(date_str)
        if not parsed_date:
            continue
        year, month = parsed_date

        overtime = item.get('総時間外', 0)
        # "N/A" や文字列は 0.0 として扱う
        if not isinstance(overtime, (int, float)): 
            overtime = 0.0

        # 当年 (2023年) の 4月～12月
        if year == nendo_start_year and (4 <= month <= 12):
            nendo_overtime_total += overtime
        # 翌年 (2024年) の 1月～3月
        elif year == nendo_end_year and (1 <= month <= 3):
            nendo_overtime_total += overtime
            
    logger.info(f"calculate_nendo_overtime: {nendo_start_year}年度 ( {nendo_start_year}/4～{nendo_end_year}/3 ) 集計完了: {nendo_overtime_total:.2f} 時間")
    return nendo_overtime_total