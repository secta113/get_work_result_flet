# Version: 1.3
import flet as ft
import datetime
import calendar
import json
import os
import traceback
from typing import Dict, Any, Optional
from dotenv import set_key
from core.commons import logger, ENV_PATH, APP_BUNDLE_DIR, jpholiday
# 作成したユーティリティをインポート
from utils.json_utils import load_special_holidays, save_special_holidays

class EstimateView(ft.Container):
    """稼働見込計算画面のビュークラス。

    当月および次月の所定稼働日数を計算し、見込み稼働時間を算出します。
    ログ出力機能を強化し、休日判定の内訳（JSON/jpholiday）を確認可能です。

    Args:
        page (ft.Page): Fletのページオブジェクト。
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        # 初期化時にJSONロードを実行
        self.special_holidays_list: list = load_special_holidays()
        self.est_refs: Dict[str, ft.Control] = {}
        
        self.padding = 20
        self.alignment = ft.alignment.top_center
        self.expand = True

        self.def_std_work_val = os.getenv("DEF_STD_WORK", "0800")
        self.holiday_behavior_val = os.getenv("HOLIDAY_BEHAVIOR", "休日として扱う")
        
        self.content = self._build_content()
        
        # 初期計算
        self.recalc_workdays("cur")
        self.recalc_workdays("nxt")

    def get_std_work_hour_as_float(self) -> float:
        """設定された所定労働時間文字列をfloat型（時間単位）に変換します。

        Returns:
            float: 時間単位の所定労働時間。変換失敗時は8.0を返します。
        """
        s = self.def_std_work_val
        try:
            h = int(s[:2])
            m = int(s[2:])
            return float(h) + float(m) / 60.0
        except Exception: return 8.0

    def _build_content(self) -> ft.Column:
        """UIコンポーネントを構築します。"""
        initial_switch_val = (self.holiday_behavior_val == "稼働日として扱う")
        
        self.switch_estimate_holiday = ft.Switch(
            label="祝日を稼働日として扱う", value=initial_switch_val,
            on_change=self.handle_estimate_holiday_change
        )
        self.input_est_std_work = ft.TextField(
            label="所定労働時間 (HHMM)", value=self.def_std_work_val, width=180,
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self.handle_std_work_change
        )
        
        # パス表示用テキストの初期状態設定
        self.txt_special_holiday_path = ft.Text("未設定 (data/special_holidays.json を自動読込)", size=12, color=ft.Colors.GREY)
        # 初期表示時は画面に追加されていないため update=False を指定
        self._update_holiday_path_text(need_update=False)

        self.file_picker = ft.FilePicker(on_result=self.load_special_holidays_file)
        self.page.overlay.append(self.file_picker)

        now = datetime.datetime.now()
        cur_y, cur_m = now.year, now.month
        nxt_y, nxt_m = (cur_y, cur_m + 1) if cur_m < 12 else (cur_y + 1, 1)

        col_current = self.create_section("当月報告", "cur", cur_y, cur_m)
        col_next = self.create_section("次月報告", "nxt", nxt_y, nxt_m)

        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("⚙️ 計算機 初期設定", weight=ft.FontWeight.BOLD),
                    ft.Row([self.switch_estimate_holiday, ft.Container(width=20), self.input_est_std_work]),
                    ft.Row([
                        ft.ElevatedButton("特殊休暇ファイルを取り込む", icon=ft.Icons.FILE_OPEN, on_click=lambda _: self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["json"])),
                        self.txt_special_holiday_path
                    ])
                ]),
                padding=15, bgcolor=ft.Colors.GREY_50, border_radius=10, border=ft.border.all(1, ft.Colors.GREY_300)
            ),
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.Row([col_current, col_next], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.START, wrap=True)
        ], scroll=ft.ScrollMode.AUTO)

    def create_section(self, title: str, prefix: str, year: int, month: int) -> ft.Container:
        """月次報告用のUIセクションを作成します。"""
        now = datetime.datetime.now()
        dd_year = ft.Dropdown(options=[ft.dropdown.Option(str(y)) for y in range(now.year - 1, now.year + 2)], value=str(year), width=100, on_change=lambda e: self.recalc_workdays(prefix))
        dd_month = ft.Dropdown(options=[ft.dropdown.Option(str(m)) for m in range(1, 13)], value=str(month), width=90, on_change=lambda e: self.recalc_workdays(prefix))
        
        self.est_refs[f"{prefix}_year"] = dd_year
        self.est_refs[f"{prefix}_month"] = dd_month
        self.est_refs[f"{prefix}_days"] = ft.TextField(value="20", suffix_text="日", text_align=ft.TextAlign.RIGHT, width=120, on_change=lambda e: self.calc_estimate_total(prefix))
        self.est_refs[f"{prefix}_daily"] = ft.TextField(value=f"{self.get_std_work_hour_as_float():.2f}", suffix_text="H", text_align=ft.TextAlign.RIGHT, width=120, on_change=lambda e: self.calc_estimate_total(prefix))
        self.est_refs[f"{prefix}_res_total"] = ft.Text("0.00 H", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE)

        return ft.Container(
            content=ft.Column([
                ft.Container(content=ft.Row([ft.Text(title, color="white", size=18), ft.Container(expand=True), dd_year, ft.Text("年", color="white"), dd_month, ft.Text("月", color="white")], vertical_alignment=ft.CrossAxisAlignment.CENTER), bgcolor="green", padding=15, border_radius=8),
                ft.Row([ft.Text("所定労働日数 (自動)"), self.est_refs[f"{prefix}_days"]], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("1日の所定労働時間"), self.est_refs[f"{prefix}_daily"]], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),
                ft.Row([ft.Text("総稼働時間 (見込):"), self.est_refs[f"{prefix}_res_total"]], alignment=ft.MainAxisAlignment.END),
            ], spacing=10),
            border=ft.border.all(1, ft.Colors.GREY_300), border_radius=10, padding=20, width=450
        )

    def handle_std_work_change(self, e: ft.ControlEvent) -> None:
        """所定労働時間の変更を処理します。"""
        self.def_std_work_val = e.control.value
        set_key(ENV_PATH, "DEF_STD_WORK", self.def_std_work_val)
        float_str = f"{self.get_std_work_hour_as_float():.2f}"
        if 'cur_daily' in self.est_refs:
            self.est_refs['cur_daily'].value = float_str; self.est_refs['cur_daily'].update(); self.calc_estimate_total('cur')
        if 'nxt_daily' in self.est_refs:
            self.est_refs['nxt_daily'].value = float_str; self.est_refs['nxt_daily'].update(); self.calc_estimate_total('nxt')

    def handle_estimate_holiday_change(self, e: ft.ControlEvent) -> None:
        """祝日扱いの変更を処理します。"""
        self.holiday_behavior_val = "稼働日として扱う" if e.control.value else "休日として扱う"
        set_key(ENV_PATH, "HOLIDAY_BEHAVIOR", self.holiday_behavior_val)
        self.recalc_workdays("cur")
        self.recalc_workdays("nxt")
    
    def load_special_holidays_file(self, e: ft.FilePickerResultEvent) -> None:
        """ユーザーが選択したファイルから特別休暇設定を読み込み、保存します。"""
        if e.files:
            file_path = e.files[0].path
            try:
                # ユーザー選択ファイルを一度読み込む
                with open(file_path, "r", encoding="utf-8") as f:
                    new_data = json.load(f)
                
                if isinstance(new_data, list):
                    # データをメモリにセット
                    self.special_holidays_list = new_data
                    
                    # データをdataフォルダへ保存 (永続化)
                    if save_special_holidays(self.special_holidays_list):
                        logger.info("New special holidays file imported and saved.")
                        self.page.snack_bar = ft.SnackBar(ft.Text("特別休暇ファイルをインポートし保存しました"), bgcolor=ft.Colors.GREEN)
                    else:
                        logger.error("Failed to save imported holidays.")
                        self.page.snack_bar = ft.SnackBar(ft.Text("ファイルのインポートには成功しましたが、保存に失敗しました"), bgcolor=ft.Colors.ORANGE)
                    
                    self.page.snack_bar.open = True
                    self.page.update()

                    self._update_holiday_path_text()
                    self.recalc_workdays("cur")
                    self.recalc_workdays("nxt")
                else:
                    raise ValueError("JSON形式がリストではありません")

            except Exception as ex:
                logger.error(f"Error importing special holidays: {ex}")
                self.txt_special_holiday_path.value = f"エラー: {str(ex)}"
                self.txt_special_holiday_path.color = ft.Colors.RED
                self.txt_special_holiday_path.update()

    def _update_holiday_path_text(self, need_update: bool = True):
        """特別休暇ファイルの読み込み状態テキストを更新します。"""
        if self.special_holidays_list:
            self.txt_special_holiday_path.value = f"設定済み (自動保存): {len(self.special_holidays_list)}件"
            self.txt_special_holiday_path.color = ft.Colors.GREEN
        else:
            self.txt_special_holiday_path.value = "未設定 (data/special_holidays.json が見つかりません)"
            self.txt_special_holiday_path.color = ft.Colors.GREY
        
        if need_update:
            self.txt_special_holiday_path.update()

    def recalc_workdays(self, prefix: str) -> None:
        """指定されたセクション（当月/次月）の所定労働日数を再計算します。（ログ出力強化版）"""
        try:
            # jpholidayライブラリのチェック
            if not jpholiday:
                logger.warning("【注意】jpholiday ライブラリが読み込まれていません。祝日判定がスキップされます。")

            y_str = self.est_refs[f"{prefix}_year"].value
            m_str = self.est_refs[f"{prefix}_month"].value
            
            # まだ値が入っていない場合はスキップ
            if not y_str or not m_str:
                return

            y = int(y_str)
            m = int(m_str)
            
            _, last_day = calendar.monthrange(y, m)
            work_days = 0
            is_work_hol = self.switch_estimate_holiday.value # Trueなら祝日も稼働
            
            logger.info(f"--- {y}年{m}月 稼働日計算開始 (祝日稼働設定: {is_work_hol}) ---")

            for d in range(1, last_day + 1):
                dt = datetime.date(y, m, d)
                dt_str = dt.strftime("%Y-%m-%d")
                
                # 1. 特別休暇リスト (JSON) の判定
                if dt_str in self.special_holidays_list:
                    logger.info(f"[-] {dt_str}: 特別休暇(JSON)により除外")
                    continue
                
                # 2. 土日判定
                if dt.weekday() >= 5:
                    # 土日はログが多すぎるので通常はスキップ
                    continue
                
                # 3. 祝日判定 (jpholiday)
                if jpholiday and jpholiday.is_holiday(dt):
                    holiday_name = jpholiday.is_holiday_name(dt)
                    if is_work_hol:
                        logger.info(f"[+] {dt_str}: {holiday_name} ですが、設定により稼働日とします")
                    else:
                        logger.info(f"[-] {dt_str}: {holiday_name} (祝日) のため除外")
                        continue
                
                # ここまで来たら稼働日
                work_days += 1
            
            logger.info(f"=== {y}年{m}月 計算結果: {work_days}日 ===")

            self.est_refs[f"{prefix}_days"].value = str(work_days)
            if self.est_refs[f"{prefix}_days"].page: 
                self.est_refs[f"{prefix}_days"].update()
            self.calc_estimate_total(prefix)
            
        except Exception as e:
            logger.error(f"再計算中にエラーが発生しました: {e}")
            logger.error(traceback.format_exc())

    def calc_estimate_total(self, prefix: str) -> None:
        """見込総稼働時間を再計算します。"""
        try:
            d = float(self.est_refs[f"{prefix}_days"].value or 0)
            h = float(self.est_refs[f"{prefix}_daily"].value or 0)
            self.est_refs[f"{prefix}_res_total"].value = f"{d * h:.2f} H"
            if self.est_refs[f"{prefix}_res_total"].page:
                self.est_refs[f"{prefix}_res_total"].update()
        except Exception: pass