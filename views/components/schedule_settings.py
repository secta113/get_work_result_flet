# v1.2 (Fix: Correctly initialize controls for ft.Column)
import flet as ft
import os
import json
from typing import Dict, Optional, Callable
from dotenv import set_key
from core.commons import (
    logger, ENV_PATH, CRYPTOGRAPHY_AVAILABLE, WEEKDAYS_NO_WEEKEND,
    encrypt, decrypt
)

class ScheduleSettings(ft.Column):
    """
    スケジュール作成画面の設定部分（ログイン情報、デフォルト値、拡張設定）を管理するコンポーネント。
    """

    def __init__(self, page: ft.Page, on_change: Optional[Callable] = None):
        # 変数初期化（親クラスの初期化前に必要なため）
        self.page = page
        self.on_change = on_change
        self.advanced_settings_inputs: Dict[str, Dict[str, ft.Control]] = {}
        self.is_settings_expanded: bool = False
        
        # 設定値のロード
        self._load_env_settings()

        # --- UI構築 ---
        self.input_login_id = ft.TextField(label="ログインID", value=self.login_id_val, width=250, on_change=self.clear_error)
        self.input_login_pw = ft.TextField(label="パスワード", value=self.login_pw_val, password=True, can_reveal_password=True, width=250, on_change=self.clear_error)
        
        self.radio_holiday = ft.RadioGroup(
            content=ft.Row([ft.Radio(value="休日として扱う", label="休日として扱う"), ft.Radio(value="稼働日として扱う", label="稼働日として扱う")]),
            value=self.holiday_behavior_val, on_change=lambda e: setattr(self, 'holiday_behavior_val', e.control.value) or self.save_settings()
        )
        
        self.input_def_start = ft.TextField(label="開始", value=self.def_start_val, width=100, on_change=self.save_settings)
        self.input_def_end = ft.TextField(label="終了", value=self.def_end_val, width=100, on_change=self.save_settings)
        self.input_def_rest = ft.TextField(label="休憩", value=self.def_rest_val, width=100, on_change=self.save_settings)
        self.input_def_mid = ft.TextField(label="深夜休憩", value=self.def_mid_val, width=100, disabled=not self.show_midnight_val, on_change=self.save_settings)
        
        def handle_std_work_sync(e):
            self.def_std_work_val = e.control.value
            self.save_settings()
        self.input_def_std_work = ft.TextField(label="所定稼働", value=self.def_std_work_val, width=100, tooltip="残業計算の基準 (HHMM)", on_change=handle_std_work_sync)

        self.switch_midnight = ft.Switch(label="深夜休憩を表示", value=self.show_midnight_val, on_change=self._handle_midnight_change)
        self.switch_advanced = ft.Switch(label="拡張設定(曜日別)を使用", value=self.use_advanced_val, on_change=self._handle_advanced_change)
        
        self.container_advanced = ft.Container(visible=self.use_advanced_val)
        self._build_advanced_settings_ui()
        
        self.container_default_inputs = ft.Container(
            content=ft.Column([
                ft.Text("▼ 一括入力のデフォルト値", weight=ft.FontWeight.BOLD),
                ft.Row([self.input_def_start, self.input_def_end, self.input_def_rest, self.input_def_mid])
            ]),
            visible=not self.use_advanced_val 
        )

        settings_tile = ft.ExpansionTile(
            title=ft.Text("詳細設定 (デフォルト値・休日設定など)", weight=ft.FontWeight.BOLD),
            subtitle=ft.Text("入力値は自動保存されます", size=12, color=ft.Colors.GREEN),
            initially_expanded=self.is_settings_expanded,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Text("祝日の扱い:", weight=ft.FontWeight.BOLD), ft.Row([self.radio_holiday], alignment=ft.MainAxisAlignment.CENTER), ft.Divider(),
                        ft.Text("所定稼働時間 (残業計算用):", weight=ft.FontWeight.BOLD), ft.Row([self.input_def_std_work], alignment=ft.MainAxisAlignment.CENTER), ft.Divider(),
                        ft.Row([self.switch_midnight, self.switch_advanced], alignment=ft.MainAxisAlignment.CENTER),
                        self.container_default_inputs, ft.Divider(), self.container_advanced,
                    ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20, bgcolor=ft.Colors.GREY_50
                )
            ]
        )
        
        # --- 親クラス(Column)の初期化 ---
        # ここで controls 引数にリストを渡すことで、確実に表示されるようになります
        super().__init__(
            controls=[
                ft.Container(content=ft.Row([self.input_login_id, self.input_login_pw], alignment=ft.MainAxisAlignment.CENTER), width=1000),
                ft.Container(content=settings_tile, width=1000)
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, # 中央寄せ
            spacing=10
        )

    def _load_env_settings(self) -> None:
        """環境変数から設定を読み込みます。"""
        self.login_id_val = decrypt(os.getenv("SCHEDULE_LOGIN_ID", ""))
        self.login_pw_val = decrypt(os.getenv("SCHEDULE_LOGIN_PW", ""))
        self.def_start_val = os.getenv("DEF_START", "0930")
        self.def_end_val = os.getenv("DEF_END", "1800")
        self.def_rest_val = os.getenv("DEF_REST", "0100")
        self.def_mid_val = os.getenv("DEF_MID", "0000")
        self.def_std_work_val = os.getenv("DEF_STD_WORK", "0800")
        self.show_midnight_val = os.getenv("SHOW_MIDNIGHT", "false").lower() == "true"
        self.use_advanced_val = os.getenv("USE_ADVANCED_SETTINGS", "false").lower() == "true"
        self.holiday_behavior_val = os.getenv("HOLIDAY_BEHAVIOR", "休日として扱う")
        
        adv_json = os.getenv("ADVANCED_SETTINGS_JSON", "")
        default_map = {
            w: {"曜日": w, "開始": "0930", "終了": "1800", "休憩": "0100", "深夜": "0000", "在宅勤務": False, "コメント": ""}
            for w in WEEKDAYS_NO_WEEKEND
        }
        try:
            if adv_json:
                loaded = json.loads(adv_json)
                if isinstance(loaded, list):
                    for item in loaded:
                        w = item.get("曜日")
                        if w in default_map: default_map[w].update(item)
        except Exception: 
            pass
        self.advanced_settings_data = default_map

    def save_settings(self, e: Optional[ft.ControlEvent] = None) -> None:
        """現在の設定を環境変数（.envファイル）に保存します。"""
        try:
            set_key(ENV_PATH, "DEF_START", self.input_def_start.value)
            set_key(ENV_PATH, "DEF_END", self.input_def_end.value)
            set_key(ENV_PATH, "DEF_REST", self.input_def_rest.value)
            set_key(ENV_PATH, "DEF_STD_WORK", self.def_std_work_val)
            if self.show_midnight_val:
                set_key(ENV_PATH, "DEF_MID", self.input_def_mid.value)
            
            set_key(ENV_PATH, "SHOW_MIDNIGHT", str(self.show_midnight_val).lower())
            set_key(ENV_PATH, "USE_ADVANCED_SETTINGS", str(self.use_advanced_val).lower())
            set_key(ENV_PATH, "HOLIDAY_BEHAVIOR", self.holiday_behavior_val)
            
            val_id = encrypt(self.input_login_id.value) if CRYPTOGRAPHY_AVAILABLE else self.input_login_id.value
            val_pw = encrypt(self.input_login_pw.value) if CRYPTOGRAPHY_AVAILABLE else self.input_login_pw.value
            set_key(ENV_PATH, "SCHEDULE_LOGIN_ID", val_id)
            set_key(ENV_PATH, "SCHEDULE_LOGIN_PW", val_pw)

            if self.use_advanced_val and self.advanced_settings_inputs:
                save_list = []
                for w in WEEKDAYS_NO_WEEKEND:
                    inputs = self.advanced_settings_inputs[w]
                    save_list.append({
                        "曜日": w,
                        "開始": inputs["start"].value,
                        "終了": inputs["end"].value,
                        "休憩": inputs["rest"].value,
                        "深夜": inputs["mid"].value,
                        "在宅勤務": inputs["wfh"].value,
                        "コメント": inputs["template"].value
                    })
                set_key(ENV_PATH, "ADVANCED_SETTINGS_JSON", json.dumps(save_list, ensure_ascii=False))

            # 親に変更を通知（計算処理などが走る可能性があるため）
            if self.on_change:
                self.on_change(e)

        except Exception as ex:
            logger.error(f"Save Error: {ex}")

    def _build_advanced_settings_ui(self) -> None:
        rows = [ft.Row([ft.Text("曜日", width=50, weight=ft.FontWeight.BOLD), ft.Text("開始", width=80), ft.Text("終了", width=80), ft.Text("休憩", width=80), ft.Text("深夜", width=80), ft.Text("在宅", width=50), ft.Text("定型文", width=150)], alignment=ft.MainAxisAlignment.CENTER)]
        for w in WEEKDAYS_NO_WEEKEND:
            data = self.advanced_settings_data.get(w, {})
            i_start = ft.TextField(value=data.get("開始"), width=80, content_padding=5, text_size=13, on_change=self.save_settings)
            i_end = ft.TextField(value=data.get("終了"), width=80, content_padding=5, text_size=13, on_change=self.save_settings)
            i_rest = ft.TextField(value=data.get("休憩"), width=80, content_padding=5, text_size=13, on_change=self.save_settings)
            i_mid = ft.TextField(value=data.get("深夜"), width=80, content_padding=5, text_size=13, disabled=not self.show_midnight_val, on_change=self.save_settings)
            i_wfh = ft.Checkbox(value=data.get("在宅勤務", False), on_change=self.save_settings)
            i_template = ft.TextField(value=data.get("コメント", ""), width=150, content_padding=5, text_size=13, on_change=self.save_settings)
            self.advanced_settings_inputs[w] = {"start": i_start, "end": i_end, "rest": i_rest, "mid": i_mid, "wfh": i_wfh, "template": i_template}
            rows.append(ft.Row([ft.Text(w, width=50), i_start, i_end, i_rest, i_mid, i_wfh, i_template], alignment=ft.MainAxisAlignment.CENTER))
        self.container_advanced.content = ft.Column(rows, spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _handle_midnight_change(self, e: ft.ControlEvent) -> None:
        self.show_midnight_val = e.control.value
        self.save_settings()
        self.input_def_mid.disabled = not self.show_midnight_val
        self.input_def_mid.update()
        if self.use_advanced_val:
            for inputs in self.advanced_settings_inputs.values():
                inputs["mid"].disabled = not self.show_midnight_val
                inputs["mid"].update()
        
        # 親Viewに変更通知（カラムの表示切替などが必要なため）
        if self.on_change:
            self.on_change(e)

    def _handle_advanced_change(self, e: ft.ControlEvent) -> None:
        self.use_advanced_val = e.control.value
        self.save_settings()
        self.container_advanced.visible = self.use_advanced_val
        self.container_default_inputs.visible = not self.use_advanced_val
        self.container_advanced.update()
        self.container_default_inputs.update()
        
        if self.on_change:
            self.on_change(e)

    def clear_error(self, e: ft.ControlEvent) -> None:
        e.control.error_text = None
        e.control.update()

    # --- 親クラスからアクセスするためのプロパティ ---
    @property
    def login_id(self): return self.input_login_id.value
    @property
    def login_pw(self): return self.input_login_pw.value
    @property
    def holiday_behavior(self): return self.holiday_behavior_val
    @property
    def default_start(self): return self.input_def_start.value
    @property
    def default_end(self): return self.input_def_end.value
    @property
    def default_rest(self): return self.input_def_rest.value
    @property
    def default_mid(self): return self.input_def_mid.value
    @property
    def default_std_work(self): return self.input_def_std_work.value
    @property
    def show_midnight(self): return self.show_midnight_val
    @property
    def use_advanced_settings(self): return self.use_advanced_val