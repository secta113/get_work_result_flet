# --- date_utils.py ---
# 役割: 処理対象月のリスト生成を担当する

import datetime
import logging
from typing import Set

logger = logging.getLogger(__name__)

def generate_target_months(today: datetime.date, ui_year: int) -> Set[str]:
    """
    指定された年（UIで選択された年）に基づいて、処理対象月のセットを生成する。
    
    ロジック:
    - (A) UI指定年が本年の場合:
        前年3月～当月（または前月）までを対象とする。
        （12日未満なら当月は対象外）
    - (B) UI指定年が本年以外（過去年）の場合:
        指定年の1月～12月までを対象とする。

    Args:
        today (datetime.date): 実行日の日付オブジェクト。
        ui_year (int): ユーザーがUIで指定した西暦年。

    Returns:
        Set[str]: 処理対象月の年月プレフィックス (例: "令和05年03月") のセット。
    """
    target_set: Set[str] = set() 
    
    if ui_year == today.year:
        # (A) 本年の場合
        logger.info(f"generate_target_months: UI指定年={ui_year} (本年) のため、前年3月～ のロジックを実行します。")
        end_year = today.year
        end_month = today.month
        
        # 12日未満は当月の明細が未発行とみなし、対象外とする
        if today.day < 12:
            logger.info(f"generate_target_months: 本日({today})が12日未満のため、当月({end_month}月)は対象外とします。")
            if end_month == 1:
                end_year -= 1
                end_month = 12
            else:
                end_month -= 1
        else:
             logger.info(f"generate_target_months: 本日({today})が12日以降のため、当月({end_month}月)を対象に含めます。")
        
        # 開始は前年の3月固定
        start_year = today.year - 1
        start_month = 3
    
    else:
        # (B) 本年以外の場合
        logger.info(f"generate_target_months: UI指定年={ui_year} (本年以外) のため、指定年の1月～12月を対象とします。")
        start_year = ui_year
        start_month = 1
        end_year = ui_year
        end_month = 12
        
    logger.info(f"generate_target_months: 取得対象期間(A): {start_year}年{start_month}月 ～ {end_year}年{end_month}月")
    
    current_year = start_year
    current_month = start_month
    
    # 期間内の年月をセットに追加
    while True:
        if current_year > end_year or (current_year == end_year and current_month > end_month):
            break
        
        reiwa_year = current_year - 2018 # 西暦から令和へ
        reiwa_str_prefix = f"令和{reiwa_year:02d}年{current_month:02d}月" 
        target_set.add(reiwa_str_prefix)
        
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
            
    return target_set

def generate_target_months_for_full_scan(today: datetime.date) -> Set[str]:
    """
    全期間スキャン用の処理対象月セットを生成する (2019年1月～当月/前月)。
    
    ロジック:
    - 2019年1月 (固定) から開始。
    - 終了月は `generate_target_months` と同様に12日未満ルールを適用。

    Args:
        today (datetime.date): 実行日の日付オブジェクト。

    Returns:
        Set[str]: 処理対象月の年月プレフィックス (例: "令和05年03月") のセット。
    """
    target_set: Set[str] = set() 
    logger.info("generate_target_months_for_full_scan: 全期間スキャンが実行されました。")
    
    start_year = 2019 # サービス開始年に基づく固定値
    start_month = 1
    
    end_year = today.year
    end_month = today.month
    
    # 12日未満は当月の明細が未発行とみなし、対象外とする
    if today.day < 12:
        logger.info(f"generate_target_months (全期間): 本日({today})が12日未満のため、当月({end_month}月)は対象外とします。")
        if end_month == 1:
            end_year -= 1
            end_month = 12
        else:
            end_month -= 1
    else:
            logger.info(f"generate_target_months (全期間): 本日({today})が12日以降のため、当月({end_month}月)を対象に含めます。")
    
    logger.info(f"generate_target_months (全期間): 取得対象期間(A): {start_year}年{start_month}月 ～ {end_year}年{end_month}月")
    
    current_year = start_year
    current_month = start_month
    
    # 期間内の年月をセットに追加
    while True:
        if current_year > end_year or (current_year == end_year and current_month > end_month):
            break
        
        reiwa_year = current_year - 2018 # 西暦から令和へ
        reiwa_str_prefix = f"令和{reiwa_year:02d}年{current_month:02d}月"
        target_set.add(reiwa_str_prefix)
        
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
            
    return target_set