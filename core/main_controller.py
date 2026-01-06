# --- main_controller.py ---
# 役割: UI (app.py) から呼び出され、全体の処理フローを制御する
# Ver: Refactored with Class Handlers (Fix Bonus Loop)

import logging
import os
import datetime
from typing import Tuple, Dict, Any

try:
    from utils.date_utils import generate_target_months, generate_target_months_for_full_scan
    from utils.csv_handler import load_existing_csv, save_to_csv, _sort_key_for_csv
    from utils.summary_calculator import calculate_rekigun_summary, calculate_nendo_overtime
    from dotenv import set_key 
    from utils.encryption_utils import encrypt, CRYPTOGRAPHY_AVAILABLE 
    
    from handlers.payslip_handler import PayslipHandler
    
except ImportError as e:
    logging.critical(f"モジュールのインポートに失敗しました: {e}")
    raise

logger = logging.getLogger(__name__)

CSV_FILENAME = "年間サマリー_全期間.csv"
BONUS_CSV_FILENAME = "年間賞与_全期間.csv"

def run_main_logic(
    login_id: str, 
    password: str, 
    ui_target_year: int, 
    run_mode_is_full_scan: bool, 
    root_dir: str, 
    env_path: str, 
    status_placeholder: Any
) -> Tuple[bool, Dict[str, Any]]:
    
    today = datetime.date.today()
    
    # 1. 給与対象月リスト
    if not run_mode_is_full_scan:
        logger.info(f"「実行 (指定年)」モード。ID: {login_id[:4]}***, UI指定年: {ui_target_year}")
        required_months_set = generate_target_months(today, ui_target_year)
    else:
        logger.info(f"「全期間スキャン」モード。ID: {login_id[:4]}***, UI指定年: {ui_target_year}")
        required_months_set = generate_target_months_for_full_scan(today) 
    
    # 処理対象年セット (ログイン後の賞与チェック対象年)
    target_years_to_run = set()
    for prefix in required_months_set: 
        try:
            target_years_to_run.add(int(prefix[2:4]) + 2018)
        except: pass
    target_years_to_run.add(ui_target_year)
    
    # 2. 既存データ読み込み
    csv_path_abs = os.path.join(root_dir, "output", CSV_FILENAME)
    all_existing_data, all_existing_dates_set = load_existing_csv(csv_path_abs, key_name="年月日")
    
    bonus_csv_path_abs = os.path.join(root_dir, "output", BONUS_CSV_FILENAME)
    all_existing_bonus, all_existing_bonus_dates_set = load_existing_csv(bonus_csv_path_abs, key_name="支給日")
    
    # 3. 差分計算 (給与)
    final_target_dates_set = required_months_set - all_existing_dates_set
    
    # 4. ネットワーク処理 (ハンドラ使用)
    http_success = True
    http_message = ""
    
    all_new_payslips = []
    all_new_bonuses = []
    
    if target_years_to_run:
        status_placeholder.info(f"データ更新を確認中... (対象: {len(target_years_to_run)}年分)")
        
        try:
            with PayslipHandler(root_dir) as handler:
                # ログイン
                is_logged_in, login_msg = handler.login(login_id, password)
                if not is_logged_in:
                    http_success = False
                    http_message = login_msg
                else:
                    # 給与取得 (リスト全体を一括で渡す)
                    if final_target_dates_set:
                        new_payslips = handler.fetch_salary_data(final_target_dates_set)
                        all_new_payslips.extend(new_payslips)
                    
                    # 賞与取得 (対象年ごとにチェック)
                    # ★修正: ループ内でセッションを維持し、最後にログアウトする
                    for year in sorted(list(target_years_to_run)):
                        reiwa_year_str = f"令和{year - 2018:02d}年"
                        new_bonuses = handler.fetch_bonus_data(reiwa_year_str, all_existing_bonus_dates_set)
                        all_new_bonuses.extend(new_bonuses)
                    
                    # 全処理終了後にログアウト
                    handler.logout()
                        
        except Exception as e:
            http_success = False
            http_message = f"通信処理中にエラーが発生: {e}"
            logger.error(http_message, exc_info=True)

    # 5. 結果保存
    if http_success:
        if all_new_payslips or all_new_bonuses:
            status_placeholder.success(f"更新完了: 給与+{len(all_new_payslips)}件, 賞与+{len(all_new_bonuses)}件")
            try:
                if CRYPTOGRAPHY_AVAILABLE:
                    set_key(env_path, "MY_LOGIN_ID", encrypt(login_id))
                    set_key(env_path, "MY_PASSWORD", encrypt(password))
                else:
                    set_key(env_path, "MY_LOGIN_ID", login_id)
                    set_key(env_path, "MY_PASSWORD", password)
            except: pass

            if all_new_payslips:
                all_existing_data.extend(all_new_payslips)
                save_to_csv(all_existing_data, root_dir, CSV_FILENAME)
            
            if all_new_bonuses:
                all_existing_bonus.extend(all_new_bonuses)
                bonus_headers = ["支給日", "賞与額", "差引支給額", "総支給額", "控除合計", "所得税", "社会保険料計"]
                save_to_csv(all_existing_bonus, root_dir, BONUS_CSV_FILENAME, key_order=bonus_headers)
        else:
            status_placeholder.success("データは最新です。")
    else:
        status_placeholder.error(f"エラー: {http_message}")
        return (False, {"error": http_message})
    
    # 6. UI用データ抽出 (指定年)
    reiwa_year_ui = ui_target_year - 2018
    target_reiwa_str = f"令和{reiwa_year_ui:02d}年"
    
    final_data_ui = [d for d in all_existing_data if target_reiwa_str in d.get("年月日", "")]
    final_data_ui.sort(key=_sort_key_for_csv)
    
    bonus_data_ui = [d for d in all_existing_bonus if target_reiwa_str in d.get("支給日", "")]
    bonus_data_ui.sort(key=lambda x: x.get("支給日", ""))

    # 7. サマリー計算
    summary_data_rekigun = {}
    summary_nendo_overtime = 0.0
    
    if final_data_ui:
        calc_list = []
        for item in final_data_ui:
            c = item.copy()
            for k in ['総支給額', '差引支給額', '総時間外']:
                if not isinstance(c.get(k), (int, float)): c[k] = 0.0
            calc_list.append(c)
        summary_data_rekigun = calculate_rekigun_summary(calc_list)
        
        latest = final_data_ui[-1]
        summary_data_rekigun['latest_paid_leave_remaining_days'] = latest.get('有給残日数', 'N/A')
    
    summary_nendo_overtime = calculate_nendo_overtime(all_existing_data, ui_target_year)
    
    # 賞与加算
    total_bonus_pay = 0.0
    total_bonus_net = 0.0
    
    if bonus_data_ui:
        for b in bonus_data_ui:
            try: b_pay = float(str(b.get("総支給額", 0)).replace(',', ''))
            except: b_pay = 0.0
            try: b_net = float(str(b.get("差引支給額", 0)).replace(',', ''))
            except: b_net = 0.0
            
            total_bonus_pay += b_pay
            total_bonus_net += b_net
            
    if 'total_pay' not in summary_data_rekigun: summary_data_rekigun['total_pay'] = 0.0
    if 'total_net_pay' not in summary_data_rekigun: summary_data_rekigun['total_net_pay'] = 0.0

    summary_data_rekigun['total_pay'] += total_bonus_pay
    summary_data_rekigun['total_net_pay'] += total_bonus_net
    summary_data_rekigun['total_bonus'] = total_bonus_pay

    result = {
        "csv_path": os.path.join("output", CSV_FILENAME),
        "ui_target_year": ui_target_year,
        "final_data_ui": final_data_ui,
        "bonus_data_ui": bonus_data_ui,
        "summary_data_rekigun": summary_data_rekigun,
        "summary_nendo_overtime": summary_nendo_overtime
    }
    
    return (True, result)