# Version: 1.9 (Refactor: Extract ScheduleTable)
import flet as ft
from typing import Optional
from core.commons import (
    ROOT_DIR, MODULES_AVAILABLE, CODE_TO_NAME, WORK_TYPE_MAP_REVERSE, ScheduleHandler
)

# 分割した各コンポーネントをインポート
from views.components.schedule_settings import ScheduleSettings
from views.components.schedule_actions import ScheduleActions
from views.components.schedule_table import ScheduleTable

class ScheduleView(ft.Container):
    """勤務表作成画面のビュークラス。
    
    v1.9: テーブル・計算ロジックを ScheduleTable に分離し、リファクタリング完了。
          Viewはコンポーネントの配置とイベント仲介に専念。
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.padding = 10
        self.expand = True
        self.alignment = ft.alignment.top_center

        # 1. 設定コンポーネント
        self.settings_view = ScheduleSettings(page, on_change=self.handle_settings_change)

        # 2. アクションコンポーネント
        self.actions_view = ScheduleActions(
            page, 
            on_fetch=self.handle_fetch_data, 
            on_bulk_fill=self.handle_bulk_fill
        )

        # 3. テーブルコンポーネント (設定とアクションの状態を参照させる)
        self.table_view = ScheduleTable(page, self.settings_view, self.actions_view)

        self.submit_row = ft.Row([
            ft.ElevatedButton("登録を実行 (POST)", icon=ft.Icons.CLOUD_UPLOAD, bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE, height=50, on_click=self.handle_submit)
        ], alignment=ft.MainAxisAlignment.CENTER, visible=False)

        self.content = ft.Column([
            self.settings_view,
            ft.Divider(height=1),
            self.actions_view,
            self.table_view,
            self.submit_row,
            ft.Container(height=20)
        ], scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)

    def show_message(self, msg: str, color: str = ft.Colors.GREEN) -> None:
        if self.page:
            self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
            self.page.snack_bar.open = True
            self.page.update()

    # --- イベントハンドリング ---

    def handle_settings_change(self, e) -> None:
        """設定が変更されたらテーブルのカラム定義などを更新"""
        self.table_view.update_columns()
        self.table_view.refresh_table()

    def handle_fetch_data(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Webからデータを取得し、テーブルにセットする"""
        if not MODULES_AVAILABLE: return self.show_message("モジュールなし", ft.Colors.RED)
        if not self.settings_view.login_id or not self.settings_view.login_pw:
            return self.show_message("ログイン情報を入力してください", ft.Colors.RED)
        
        self.show_message("データ取得中...")
        try:
            with ScheduleHandler(ROOT_DIR) as handler:
                suc, msg = handler.login(self.settings_view.login_id, self.settings_view.login_pw)
                if not suc: return self.show_message(f"失敗: {msg}", ft.Colors.RED)
                
                suc, msg, data = handler.get_current_data()
                if suc:
                    # 休日設定などを反映
                    is_h_mode = (self.settings_view.holiday_behavior == "休日として扱う")
                    for row in data:
                        if row.get("workType", "99") == "99":
                            is_hol = row["youbi"] in ["土", "日"] or (is_h_mode and row.get("shukujitsu_bool", False))
                            row["workType"] = "休日" if is_hol else "稼働"
                        else:
                            row["workType"] = CODE_TO_NAME.get(row.get("workType"), row.get("workType"))
                    
                    # テーブルにデータを渡す
                    self.table_view.set_data(data)
                    self.submit_row.visible = True
                    self.submit_row.update()
                    self.show_message(f"取得成功: {len(data)}件")
                    
                    # PDF連携のために年をリロード
                    if self.actions_view.is_kishakai_mode and data:
                        try:
                            yd_str = data[0]["workDate"]
                            parts = yd_str.replace("-", "/").split("/")
                            if len(parts) >= 1 and len(parts[0]) == 4:
                                self.actions_view.reload_pdf_dates(int(parts[0]))
                        except:
                            pass
                else: 
                    self.show_message(f"失敗: {msg}", ft.Colors.RED)
        except Exception as ex: 
            self.show_message(f"エラー: {ex}", ft.Colors.RED)

    def handle_bulk_fill(self, e: ft.ControlEvent) -> None:
        """一括入力ボタンの処理"""
        # 帰社会モードならキャッシュ確認
        if self.actions_view.is_kishakai_mode and not self.actions_view.kishakai_dates:
             # 現在のデータから年を取得してリロードを試みる
             current_data = self.table_view.get_data()
             if current_data:
                try:
                     yd_str = current_data[0]["workDate"]
                     parts = yd_str.replace("-", "/").split("/")
                     if len(parts) >= 1 and len(parts[0]) == 4:
                        self.actions_view.reload_pdf_dates(int(parts[0]))
                except:
                    pass

        # テーブル側の一括入力メソッドを実行
        count = self.table_view.bulk_fill()
        if count > 0:
            self.show_message(f"{count}件 一括入力しました")
        else:
            self.show_message("対象行がありませんでした（またはデータなし）", ft.Colors.ORANGE)

    def handle_submit(self, e: ft.ControlEvent) -> None:
        """登録実行"""
        if not MODULES_AVAILABLE: return self.show_message("モジュールなし", ft.Colors.RED)
        
        # テーブルから最新データを取得
        current_data = self.table_view.get_data()
        if not current_data: return
        
        sub_data = [r.copy() for r in current_data]
        for r in sub_data: r["workType"] = WORK_TYPE_MAP_REVERSE.get(r.get("workType", "稼働"), "99")
        try:
            with ScheduleHandler(ROOT_DIR) as handler:
                if not handler.login(self.settings_view.login_id, self.settings_view.login_pw)[0]: return self.show_message("ログイン失敗", ft.Colors.RED)
                suc, msg, latest = handler.update_schedule(sub_data)
                if suc:
                    def close_dialog(e):
                        self.page.close(dlg)

                    dlg =ft.AlertDialog(
                        title=ft.Text("完了"),
                        content=ft.Text(msg),
                        actions=[ft.TextButton("OK", on_click=close_dialog)]
                    )
                    self.page.open(dlg)

                    if latest:
                        is_h = (self.settings_view.holiday_behavior == "休日として扱う")
                        for r in latest:
                            if r.get("workType") == "99":
                                is_hol = r["youbi"] in ["土", "日"] or (is_h and r.get("shukujitsu_bool", False))
                                r["workType"] = "休日" if is_hol else "稼働"
                            else: r["workType"] = CODE_TO_NAME.get(r.get("workType"), r.get("workType"))
                        
                        self.table_view.set_data(latest)
                else: self.show_message(f"登録失敗: {msg}", ft.Colors.RED)
        except Exception as ex: self.show_message(f"登録エラー: {ex}", ft.Colors.RED)