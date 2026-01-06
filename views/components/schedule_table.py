# v2.4 (Docstring & TypeHint applied)
import flet as ft
import datetime
from typing import List, Dict, Any, Optional
from core.commons import WORK_TYPE_OPTIONS

class ScheduleTable(ft.Column):
    """スケジュール作成画面のテーブル（カレンダー）と集計部分を管理するコンポーネント。

    Attributes:
        page (ft.Page): Fletのページオブジェクト。
        settings_view (Any): 設定コンポーネント（所定時間設定などへのアクセス用）。
        actions_view (Any): アクションコンポーネント（帰社会モード設定などへのアクセス用）。
        schedule_data (List[Dict[str, Any]]): テーブルに表示するスケジュールデータのリスト。
        rows_controls (List[Dict[str, Any]]): 各行の入力コントロールへの参照リスト。
    """

    def __init__(self, page: ft.Page, settings_view: Any, actions_view: Any):
        """ScheduleTableコンポーネントを初期化します。

        Args:
            page (ft.Page): アプリケーションのページオブジェクト。
            settings_view (Any): 設定情報を持つViewコンポーネント。
            actions_view (Any): アクション操作を持つViewコンポーネント。
        """
        super().__init__()
        self.page = page
        self.settings_view = settings_view 
        self.actions_view = actions_view   
        
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.schedule_data: List[Dict[str, Any]] = [] 
        self.rows_controls: List[Dict[str, Any]] = []

        # --- UI構築 ---
        self.schedule_table = ft.DataTable(
            columns=[], 
            column_spacing=10, 
            heading_row_height=40, 
            data_row_min_height=50, 
            border=ft.border.all(1, ft.Colors.GREY_300), 
            vertical_lines=ft.border.all(1, ft.Colors.GREY_200), 
            visible=False
        )

        self.txt_summary_work = ft.Text("稼働時間: 0.00h", size=16, weight=ft.FontWeight.BOLD)
        self.txt_summary_overtime = ft.Text("残業時間: 0.00h", size=16, weight=ft.FontWeight.BOLD)
        self.txt_summary_alert = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED)
        
        self.summary_container = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TIMELAPSE, color=ft.Colors.BLUE), self.txt_summary_work, ft.Container(width=20),
                ft.Icon(ft.Icons.ACCESS_TIME_FILLED, color=ft.Colors.ORANGE), self.txt_summary_overtime, ft.Container(width=20), self.txt_summary_alert
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=15, bgcolor=ft.Colors.BLUE_50, border_radius=8, border=ft.border.all(1, ft.Colors.BLUE_100), width=800, visible=False
        )

        self.controls = [
            ft.Row([self.schedule_table], scroll=ft.ScrollMode.AUTO, alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(height=1),
            self.summary_container,
            ft.Container(height=10)
        ]
        
        self.update_columns(run_update=False)

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """外部からデータをセットし、テーブルを再描画します。

        Args:
            data (List[Dict[str, Any]]): 表示するスケジュールデータのリスト。
        """
        self.schedule_data = data
        self.schedule_table.visible = True
        self.summary_container.visible = True
        self.refresh_table()

    def get_data(self) -> List[Dict[str, Any]]:
        """現在の編集データを返します。

        Returns:
            List[Dict[str, Any]]: 現在のスケジュールデータリスト。
        """
        return self.schedule_data

    def update_columns(self, run_update: bool = True) -> None:
        """設定に基づいてテーブルのカラム定義を更新します。

        深夜時間の表示有無などの設定変更に対応します。

        Args:
            run_update (bool, optional): 即座にUI更新を行うかどうか。 Defaults to True.
        """
        cols = [
            ft.DataColumn(ft.Text("日付")), ft.DataColumn(ft.Text("曜")), ft.DataColumn(ft.Text("区分")), ft.DataColumn(ft.Text("自動入力")),
            ft.DataColumn(ft.Text("開時")), ft.DataColumn(ft.Text("開分")), ft.DataColumn(ft.Text("終時")), ft.DataColumn(ft.Text("終分")),
            ft.DataColumn(ft.Text("休時")), ft.DataColumn(ft.Text("休分")),
        ]
        if self.settings_view.show_midnight:
            cols.extend([ft.DataColumn(ft.Text("深時")), ft.DataColumn(ft.Text("深分"))])
        cols.extend([ft.DataColumn(ft.Text("コメント")), ft.DataColumn(ft.Text("クリア"))])
        self.schedule_table.columns = cols
        if run_update: self.schedule_table.update()

    def refresh_table(self) -> None:
        """テーブルの行コントロールを再生成して描画します。

        `schedule_data` に基づいて `DataRow` を生成し、テーブルにセットします。
        """
        if not self.schedule_data: return
        self.rows_controls = [] 
        new_rows = []
        for i, row in enumerate(self.schedule_data):
            dd_type = ft.Dropdown(value=row.get("workType", "稼働"), options=[ft.dropdown.Option(o) for o in WORK_TYPE_OPTIONS], width=85, content_padding=5, text_size=13, border_color=ft.Colors.TRANSPARENT, on_change=lambda e, idx=i: self._update_row_data(idx, "workType", e.control.value))
            btn_apply = ft.Container(content=ft.Icon(ft.Icons.KEYBOARD_DOUBLE_ARROW_RIGHT, color=ft.Colors.BLUE), tooltip="設定を自動入力", on_click=lambda e, idx=i: self.apply_row_logic(idx) or self.calculate_summary(), padding=10, ink=False)
            
            def mk_tf(key): return ft.TextField(value=row.get(key, ""), width=40, content_padding=5, text_size=13, text_align=ft.TextAlign.CENTER, border=ft.InputBorder.NONE, filled=False, max_length=2, on_change=lambda e, idx=i, k=key: self._update_row_data(idx, k, e.control.value))
            tf_sh, tf_sm, tf_eh, tf_em, tf_rh, tf_rm = mk_tf("start_h"), mk_tf("start_m"), mk_tf("end_h"), mk_tf("end_m"), mk_tf("rest_h"), mk_tf("rest_m")
            tf_cmt = ft.TextField(value=row.get("comment", ""), content_padding=5, text_size=13, border=ft.InputBorder.NONE, on_change=lambda e, idx=i: self._update_row_data(idx, "comment", e.control.value))
            btn_clear = ft.Container(content=ft.Icon(ft.Icons.CLEAR, color=ft.Colors.RED_400), tooltip="クリア", on_click=lambda e, idx=i: self._clear_row(idx), padding=10, ink=False)
            
            cells = [ft.DataCell(ft.Text(row["workDate"])), ft.DataCell(ft.Text(row["youbi"])), ft.DataCell(dd_type), ft.DataCell(btn_apply), ft.DataCell(tf_sh), ft.DataCell(tf_sm), ft.DataCell(tf_eh), ft.DataCell(tf_em), ft.DataCell(tf_rh), ft.DataCell(tf_rm)]
            if self.settings_view.show_midnight:
                tf_mh, tf_mm = mk_tf("mid_h"), mk_tf("mid_m")
                cells.extend([ft.DataCell(tf_mh), ft.DataCell(tf_mm)])
            cells.extend([ft.DataCell(ft.Container(content=tf_cmt, width=600)), ft.DataCell(btn_clear)])
            
            bg_col = ft.Colors.WHITE
            if row["youbi"] == "土": bg_col = ft.Colors.BLUE_50
            elif row["youbi"] == "日" or row.get("workType") == "休日": bg_col = ft.Colors.RED_50
            
            ctrls = {"type": dd_type, "sh": tf_sh, "sm": tf_sm, "eh": tf_eh, "em": tf_em, "rh": tf_rh, "rm": tf_rm, "cmt": tf_cmt}
            if self.settings_view.show_midnight: ctrls.update({"mh": tf_mh, "mm": tf_mm})
            
            self.rows_controls.append(ctrls)
            new_rows.append(ft.DataRow(cells=cells, color=bg_col))
        
        self.schedule_table.rows = new_rows
        self.schedule_table.update()
        self.calculate_summary()

    def apply_row_logic(self, idx: int) -> bool:
        """指定行に設定（デフォルト値・曜日設定・帰社会情報）を適用します。

        Args:
            idx (int): 適用する行のインデックス。

        Returns:
            bool: 処理が成功した場合はTrue。
        """
        row = self.schedule_data[idx]
        youbi = row["youbi"]
        work_date = row.get("workDate", "")
        
        # 1. 設定値取得
        if self.settings_view.use_advanced_settings and youbi in self.settings_view.advanced_settings_inputs:
            inps = self.settings_view.advanced_settings_inputs[youbi]
            t_s, t_e, t_r, t_m = inps["start"].value, inps["end"].value, inps["rest"].value, inps["mid"].value
            t_c = (f"在宅勤務 {inps['template'].value}" if inps['template'].value else "在宅勤務") if inps["wfh"].value else ""
        else:
            t_s, t_e, t_r, t_m, t_c = self.settings_view.default_start, self.settings_view.default_end, self.settings_view.default_rest, self.settings_view.default_mid, ""
        
        # 2. 帰社会ロジック
        if self.actions_view.is_kishakai_mode:
            # まだロードしていなければ自動ロード
            if not self.actions_view.is_pdf_loaded:
                self.actions_view.reload_pdf_dates()

            if self.actions_view.kishakai_dates:
                target_md = None
                try:
                    parts = work_date.replace("-", "/").split("/")
                    if len(parts) >= 2:
                        target_md = f"{int(parts[-2]):02d}/{int(parts[-1]):02d}"
                except: pass

                if target_md:
                    is_match = False
                    for k_date in self.actions_view.kishakai_dates:
                        try:
                            k_parts = k_date.replace("-", "/").split("/")
                            if len(k_parts) >= 2:
                                k_md = f"{int(k_parts[-2]):02d}/{int(k_parts[-1]):02d}"
                                if target_md == k_md:
                                    is_match = True
                                    break
                        except: continue

                    if is_match:
                        append_msg = "帰社会参加"
                        if append_msg not in t_c:
                            t_c = f"{t_c} {append_msg}" if t_c else append_msg

        # 3. データ更新
        row.update({"start_h": t_s[:2], "start_m": t_s[2:], "end_h": t_e[:2], "end_m": t_e[2:], "rest_h": t_r[:2], "rest_m": t_r[2:], "mid_h": t_m[:2], "mid_m": t_m[2:], "workType": "稼働"})
        if t_c: row["comment"] = t_c
        
        # 4. UI更新
        c = self.rows_controls[idx]
        c["type"].value = "稼働"
        c["sh"].value, c["sm"].value = t_s[:2], t_s[2:]
        c["eh"].value, c["em"].value = t_e[:2], t_e[2:]
        c["rh"].value, c["rm"].value = t_r[:2], t_r[2:]
        if "mh" in c: c["mh"].value, c["mm"].value = t_m[:2], t_m[2:]
        if t_c: c["cmt"].value = t_c
        for k in c.values(): k.update()
        return True

    def bulk_fill(self) -> int:
        """未入力行に対して一括入力を実行します。

        未来の日付はスキップします。

        Returns:
            int: 入力が適用された行数。
        """
        if not self.schedule_data: return 0
        
        if self.actions_view.is_kishakai_mode and not self.actions_view.is_pdf_loaded:
            self.actions_view.reload_pdf_dates()

        count = 0
        today = datetime.date.today()
        current_year = today.year
        
        for i, row in enumerate(self.schedule_data):
            w_date_str = row.get("workDate", "").replace("-", "/")
            try:
                parts = w_date_str.split("/")
                if len(parts) >= 3:
                     dt_obj = datetime.datetime.strptime(w_date_str, "%Y/%m/%d").date()
                elif len(parts) == 2:
                     dt_obj = datetime.date(current_year, int(parts[0]), int(parts[1]))
                else: continue
                
                if dt_obj > today: continue 
            except ValueError: continue

            if row.get("workType") != "休日" and not row.get("start_h"):
                self.apply_row_logic(i)
                count += 1
        
        if count > 0:
            self.calculate_summary()
            self.schedule_table.update()
        return count

    def _update_row_data(self, idx: int, key: str, value: Any) -> None:
        """行データを更新し、集計を再計算します。"""
        self.schedule_data[idx][key] = value
        self.calculate_summary()

    def _clear_row(self, idx: int) -> None:
        """指定行の入力内容をクリアします。"""
        row = self.schedule_data[idx]
        for k in ["start_h", "start_m", "end_h", "end_m", "rest_h", "rest_m", "mid_h", "mid_m", "comment"]: row[k] = ""
        row["workType"] = "稼働"
        c = self.rows_controls[idx]
        for k in c.values(): 
            if isinstance(k, ft.Dropdown): k.value = "稼働"
            else: k.value = ""
            k.update()
        self.calculate_summary()

    def calculate_summary(self) -> None:
        """稼働時間と残業時間を再計算してUIを更新します。"""
        total_min, count = 0, 0
        def to_min(h, m): return (int(h) * 60 + int(m)) if (h and m) else 0
        std_val = self.settings_view.default_std_work
        std_min = (int(std_val[:2]) * 60 + int(std_val[2:])) if len(std_val) == 4 else 480
        
        for row in self.schedule_data:
            if row.get("workType") == "稼働":
                actual = to_min(row.get("end_h"), row.get("end_m")) - to_min(row.get("start_h"), row.get("start_m")) - to_min(row.get("rest_h"), row.get("rest_m")) - to_min(row.get("mid_h"), row.get("mid_m"))
                if actual > 0: total_min += actual; count += 1
        
        total_std = count * std_min
        over = max(0, total_min - total_std)
        self.txt_summary_work.value = f"稼働時間: {total_min/60:.2f}h"
        self.txt_summary_overtime.value = f"残業時間: {over/60:.2f}h"
        self.txt_summary_alert.value = "⚠️ 36提出してますか？" if (over/60 > 40) else ""
        self.txt_summary_overtime.color = ft.Colors.RED if (over/60 > 40) else ft.Colors.BLACK
        self.txt_summary_work.update()
        self.txt_summary_overtime.update()
        self.txt_summary_alert.update()