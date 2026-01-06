# Version: 1.0
import flet as ft
import datetime
import os
from typing import Dict, Any, Optional
from dotenv import set_key
from core.commons import (
    logger, ENV_PATH, ROOT_DIR, MODULES_AVAILABLE, CRYPTOGRAPHY_AVAILABLE,
    encrypt, decrypt, run_main_logic, FletStatusPlaceholder
)

try:
    from utils.csv_handler import merge_and_save_csv
except ImportError:
    logger.warning("csv_handler module not found.")
    def merge_and_save_csv(*args, **kwargs): return None

class PayslipView(ft.Container):
    """給与明細画面のビュークラス。

    Webサイトから給与明細データを取得し、サマリー表示およびCSV保存を行います。

    Args:
        page (ft.Page): Fletのページオブジェクト。
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        
        self.padding = 10
        self.expand = True
        self.alignment = ft.alignment.top_center

        self.payslip_id_val = decrypt(os.getenv("MY_LOGIN_ID", ""))
        self.payslip_pw_val = decrypt(os.getenv("MY_PASSWORD", ""))

        self.content = self._build_content()

    def _build_content(self) -> ft.Column:
        """UIコンポーネントを構築します。"""
        self.input_payslip_id = ft.TextField(label="ログインID", value=self.payslip_id_val, width=250)
        self.input_payslip_pw = ft.TextField(label="パスワード", password=True, value=self.payslip_pw_val, can_reveal_password=True, width=250)
        self.input_target_year = ft.TextField(value=str(datetime.date.today().year), width=80, text_align=ft.TextAlign.CENTER)
        
        self.txt_payslip_status = ft.Text("", color=ft.Colors.BLUE)
        self.payslip_result_container = ft.Column()

        def change_year_btn(delta, icon):
            return ft.IconButton(icon, on_click=lambda e: self.change_year(delta))

        return ft.Column([
            ft.Text("💰 給与明細 自動取得", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        self.input_payslip_id, 
                        self.input_payslip_pw, 
                        change_year_btn(-1, ft.Icons.REMOVE),
                        self.input_target_year,
                        change_year_btn(1, ft.Icons.ADD)
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([
                        ft.ElevatedButton("実行 (指定年)", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: self.handle_fetch_payslip(False)),
                        ft.ElevatedButton("全期間スキャン", icon=ft.Icons.HISTORY, on_click=lambda e: self.handle_fetch_payslip(True)),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    self.txt_payslip_status
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
                padding=20, bgcolor=ft.Colors.GREY_50, border_radius=10, width=1000 
            ),
            ft.Divider(),
            self.payslip_result_container
        ], scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)

    def change_year(self, delta: int) -> None:
        """対象年を変更します。

        Args:
            delta (int): 変更する年の増減値。
        """
        try:
            current_val = int(self.input_target_year.value)
            self.input_target_year.value = str(current_val + delta)
            self.input_target_year.update()
        except Exception: pass

    def change_year_and_fetch(self, delta: int) -> None:
        """対象年を変更し、その年のデータを再取得します。

        Args:
            delta (int): 変更する年の増減値。
        """
        self.change_year(delta)
        self.handle_fetch_payslip(is_full_scan=False)

    def handle_fetch_payslip(self, is_full_scan: bool) -> None:
        """給与明細データを取得するメイン処理を実行します。

        Args:
            is_full_scan (bool): 全期間取得を行う場合はTrue。
        """
        if not MODULES_AVAILABLE: return 
        lid, lpw = self.input_payslip_id.value, self.input_payslip_pw.value
        if not lid or not lpw: 
            self.input_payslip_id.error_text = "ID未入力" if not lid else None
            self.input_payslip_pw.error_text = "PW未入力" if not lpw else None
            self.input_payslip_id.update()
            self.input_payslip_pw.update()
            return
        
        try: target_year = int(self.input_target_year.value)
        except Exception: return

        ph = FletStatusPlaceholder(self.txt_payslip_status, self.page)
        ph.write("取得処理を開始します...")
        
        try:
            success, res = run_main_logic(lid, lpw, target_year, is_full_scan, ROOT_DIR, ENV_PATH, ph)
            if success:
                val_id = encrypt(lid) if CRYPTOGRAPHY_AVAILABLE else lid
                val_pw = encrypt(lpw) if CRYPTOGRAPHY_AVAILABLE else lpw
                set_key(ENV_PATH, "MY_LOGIN_ID", val_id)
                set_key(ENV_PATH, "MY_PASSWORD", val_pw)
                
                self.render_result(res, target_year)
                self.save_data_automatically(res, ph)
                
                ph.success("取得・保存完了")
            else:
                ph.error(f"失敗: {res.get('error')}")
        except Exception as ex:
            ph.error(f"実行エラー: {ex}")

    def save_data_automatically(self, res: Dict[str, Any], ph: Any) -> None:
        """取得したデータを既存CSVとマージして保存します。

        Args:
            res (Dict[str, Any]): 取得結果データ。
            ph (Any): ステータス表示用のプレースホルダーオブジェクト。
        """
        try:
            new_data = res.get("final_data_ui", [])
            if new_data:
                csv_filename = "年間サマリー_全期間.csv"
                key_name = "年月日"
                merge_and_save_csv(new_data, ROOT_DIR, csv_filename, key_name)

            new_bonus = res.get("bonus_data_ui", [])
            if new_bonus:
                csv_filename = "年間賞与_全期間.csv"
                key_name = "支給日"
                merge_and_save_csv(new_bonus, ROOT_DIR, csv_filename, key_name)

        except Exception as ex:
            logger.error(f"自動保存エラー: {ex}")
            ph.warning(f"データ表示は成功しましたが、CSV保存に失敗しました: {ex}")

    def render_result(self, res: Dict[str, Any], target_year: int) -> None:
        """取得結果を画面にレンダリングします。

        Args:
            res (Dict[str, Any]): 取得結果データ。
            target_year (int): 対象年。
        """
        self.payslip_result_container.controls.clear()
        
        summary = res.get("summary_data_rekigun", {})
        nendo_ot = res.get("summary_nendo_overtime", 0.0)
        
        def make_metric_card(title: str, value: Any, icon: str, color: str) -> ft.Container:
            """指標カードを作成するヘルパー関数。"""
            return ft.Container(
                content=ft.Column([
                    ft.Icon(icon, color=color, size=30),
                    ft.Text(title, size=14, color=ft.Colors.GREY_700),
                    ft.Text(str(value), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15, bgcolor=ft.Colors.WHITE, border_radius=10,
                border=ft.border.all(1, ft.Colors.GREY_200), width=180 
            )
        
        fmt_money = lambda x: f"{x:,} 円" if isinstance(x, (int, float)) else str(x)
        fmt_time = lambda x: f"{x:.2f} H" if isinstance(x, float) else str(x)

        cards = [
            make_metric_card("総支給 (暦年+賞与)", fmt_money(summary.get('total_pay', 0)), ft.Icons.MONEY, ft.Colors.GREEN),
            make_metric_card("差引支給 (暦年+賞与)", fmt_money(summary.get('total_net_pay', 0)), ft.Icons.ACCOUNT_BALANCE_WALLET, ft.Colors.BLUE),
            make_metric_card("賞与合計 (暦年)", fmt_money(summary.get('total_bonus', 0)), ft.Icons.CARD_GIFTCARD, ft.Colors.PURPLE), 
            make_metric_card("総時間外 (暦年)", fmt_time(summary.get('total_overtime', 0.0)), ft.Icons.ACCESS_TIME, ft.Colors.ORANGE),
            make_metric_card(f"年度時間外 ({target_year}/4~)", fmt_time(nendo_ot), ft.Icons.TIMELAPSE, ft.Colors.RED),
            make_metric_card("有給残 (最新)", f"{summary.get('latest_paid_leave_remaining_days')} 日", ft.Icons.BEACH_ACCESS, ft.Colors.CYAN),
        ]
        
        header_row = ft.Row([
            ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT, 
                icon_size=30,
                tooltip=f"{target_year-1}年へ",
                on_click=lambda e: self.change_year_and_fetch(-1)
            ),
            ft.Text(f"📊 {target_year}年 サマリー", size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT, 
                icon_size=30,
                tooltip=f"{target_year+1}年へ",
                on_click=lambda e: self.change_year_and_fetch(1)
            ),
        ], alignment=ft.MainAxisAlignment.CENTER)

        self.payslip_result_container.controls.append(ft.Container(height=20))
        self.payslip_result_container.controls.append(header_row)
        self.payslip_result_container.controls.append(ft.Row(cards, alignment=ft.MainAxisAlignment.CENTER, wrap=True, spacing=20, run_spacing=20))
        self.payslip_result_container.controls.append(ft.Divider())

        data_ui = res.get("final_data_ui") 
        if data_ui:
            keys = list(data_ui[0].keys())
            columns = [ft.DataColumn(ft.Text(k)) for k in keys]
            
            rows = []
            for item in data_ui:
                cells = [ft.DataCell(ft.Text(str(item.get(k, "")))) for k in keys]
                rows.append(ft.DataRow(cells=cells))
            
            dt = ft.DataTable(columns=columns, rows=rows, border=ft.border.all(1, ft.Colors.GREY_300))
            
            self.payslip_result_container.controls.append(ft.Text("詳細データ", size=18, weight=ft.FontWeight.BOLD))
            self.payslip_result_container.controls.append(ft.Row([dt], scroll=ft.ScrollMode.ALWAYS))

        bonus_data = res.get("bonus_data_ui")
        if bonus_data:
            self.payslip_result_container.controls.append(ft.Divider())
            self.payslip_result_container.controls.append(ft.Text("賞与データ", size=18, weight=ft.FontWeight.BOLD))
            
            if len(bonus_data) > 0:
                b_keys = list(bonus_data[0].keys())
                b_columns = [ft.DataColumn(ft.Text(k)) for k in b_keys]
                
                b_rows = []
                for item in bonus_data:
                    b_cells = [ft.DataCell(ft.Text(str(item.get(k, "")))) for k in b_keys]
                    b_rows.append(ft.DataRow(cells=b_cells))
                
                dt_bonus = ft.DataTable(columns=b_columns, rows=b_rows, border=ft.border.all(1, ft.Colors.GREY_300))
                self.payslip_result_container.controls.append(ft.Row([dt_bonus], scroll=ft.ScrollMode.ALWAYS))
            else:
                 self.payslip_result_container.controls.append(ft.Text("（対象年の賞与データはありません）", color=ft.Colors.GREY))

        self.payslip_result_container.update()