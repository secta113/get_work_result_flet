# v2.0 (Feature: Support JSON file upload for Kishakai schedule)
import flet as ft
import os
import shutil
import datetime
import json
from typing import Optional, Callable, Set, List
from dotenv import set_key
from core.commons import logger, ENV_PATH, ROOT_DIR

try:
    from utils.pdf_schedule_reader import get_kishakai_dates
except ImportError:
    logger.warning("utils.pdf_schedule_reader not found. PDF feature disabled.")
    get_kishakai_dates = None

class ScheduleActions(ft.Container):
    """スケジュール作成画面のアクション部分を管理するコンポーネント。

    データの取得(Web)、一括入力、および帰社会日程ファイル（PDF/JSON）の
    取り込み機能を提供します。

    Attributes:
        page (ft.Page): Fletのページオブジェクト。
        on_fetch (Optional[Callable]): データ取得ボタン押下時のコールバック関数。
        on_bulk_fill (Optional[Callable]): 一括入力ボタン押下時のコールバック関数。
        pdf_save_dir (str): ファイル（PDF/JSON）の保存先ディレクトリパス。
        kishakai_dates_cache (Set[str]): 読み込まれた帰社会の日付セット（YYYY/MM/DD形式）。
        kishakai_file_name (str): 現在設定されているファイル名。
        is_file_loaded (bool): ファイルの読み込み試行が完了しているかどうかのフラグ。
    """

    def __init__(
        self, 
        page: ft.Page, 
        on_fetch: Optional[Callable] = None, 
        on_bulk_fill: Optional[Callable] = None
    ):
        """ScheduleActionsコンポーネントを初期化します。

        Args:
            page (ft.Page): アプリケーションのページオブジェクト。
            on_fetch (Optional[Callable], optional): データ取得時のイベントハンドラ。 Defaults to None.
            on_bulk_fill (Optional[Callable], optional): 一括入力時のイベントハンドラ。 Defaults to None.
        """
        super().__init__()
        self.page = page
        self.on_fetch = on_fetch
        self.on_bulk_fill = on_bulk_fill
        
        # ファイル保存用ディレクトリ（変数名はpdf_save_dirのままだがJSONもここに保存）
        self.pdf_save_dir: str = os.path.join(ROOT_DIR, "data", "Internal_meeting")
        os.makedirs(self.pdf_save_dir, exist_ok=True)
        
        self.kishakai_dates_cache: Set[str] = set()
        # 環境変数名は互換性のため KISHAKAI_PDF_NAME を継続使用するが、中身はJSONの場合もある
        self.kishakai_file_name: str = os.getenv("KISHAKAI_PDF_NAME", "")
        
        # 読み込み試行済みフラグ
        self.is_file_loaded: bool = False

        # 初期化
        self.kishakai_initial_value: bool = False
        self._load_and_reset_status()

        # FilePicker初期化: PDFとJSONを許可
        self.file_picker = ft.FilePicker(on_result=self._handle_file_picked)
        if self.page:
            self.page.overlay.append(self.file_picker)

        self.padding = 5
        self.border = ft.border.all(1, ft.Colors.TRANSPARENT)
        
        self.content = self._build_ui()
        
        self._update_file_status(run_update=False)
        
        if self.kishakai_initial_value:
            self._load_kishakai_data(run_update=False)

    def _load_and_reset_status(self) -> None:
        """保存された設定を読み込み、月が変わっていたら状態をリセットします。"""
        saved_month = os.getenv("KISHAKAI_LAST_MONTH", "")
        saved_checked = os.getenv("KISHAKAI_IS_CHECKED", "False").lower() == "true"
        current_month = datetime.datetime.now().strftime("%Y%m")
        
        if saved_month == current_month:
            self.kishakai_initial_value = saved_checked
        else:
            self.kishakai_initial_value = False
            self._save_status(False)

    def _save_status(self, is_checked: bool) -> None:
        """現在の帰社会参加チェック状態と年月を保存します。

        Args:
            is_checked (bool): チェックボックスの状態。
        """
        current_month = datetime.datetime.now().strftime("%Y%m")
        try:
            set_key(ENV_PATH, "KISHAKAI_IS_CHECKED", str(is_checked))
            set_key(ENV_PATH, "KISHAKAI_LAST_MONTH", current_month)
        except Exception as e:
            logger.error(f"Failed to save kishakai status: {e}")

    def _build_ui(self) -> ft.Row:
        """UIコンポーネントを構築して返します。

        Returns:
            ft.Row: アクションボタンと設定項目を含む行コンポーネント。
        """
        self.chk_kishakai = ft.Checkbox(
            label="帰社会に参加",
            value=self.kishakai_initial_value,
            tooltip="ONにすると、指定されたファイル(PDF/JSON)から日程を読み込み、休憩時間(+1h)とコメントを自動反映します。",
            on_change=self._handle_kishakai_check_change
        )
        
        self.btn_select_file = ft.ElevatedButton(
            "ファイルを選択",
            icon=ft.Icons.UPLOAD_FILE,
            tooltip="帰社会スケジュール(PDFまたはJSON)を取り込む",
            on_click=lambda _: self.file_picker.pick_files(
                allow_multiple=False, 
                allowed_extensions=["pdf", "json"]
            )
        )
        
        self.txt_file_status = ft.Text("ファイル未設定", size=12, color=ft.Colors.GREY)

        return ft.Row([
            ft.ElevatedButton("データ取得 (Web)", icon=ft.Icons.CLOUD_DOWNLOAD, on_click=self._handle_fetch_click),
            ft.Container(width=20),
            ft.ElevatedButton("一括入力 (未入力行)", icon=ft.Icons.AUTO_FIX_HIGH, on_click=self._handle_bulk_fill_click),
            ft.Container(width=20),
            ft.Container(
                content=ft.Row([
                    self.chk_kishakai,
                    self.btn_select_file,
                    self.txt_file_status
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                border=ft.border.all(1, ft.Colors.GREY_300),
                border_radius=5,
                padding=ft.padding.only(left=10, right=15, top=5, bottom=5),
                bgcolor=ft.Colors.GREY_50
            )
        ], alignment=ft.MainAxisAlignment.CENTER)

    def show_message(self, msg: str, color: str = ft.Colors.GREEN) -> None:
        """スナックバーでメッセージを表示します。"""
        if self.page:
            self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
            self.page.snack_bar.open = True
            self.page.update()

    # --- ヘルパーメソッド ---

    def _update_file_status(self, run_update: bool = True) -> None:
        """ファイルの状態表示テキストを更新します。

        Args:
            run_update (bool, optional): UIの即時更新を行うか。 Defaults to True.
        """
        if self.kishakai_file_name:
            status_text = f"設定済: {self.kishakai_file_name}"
            if self.kishakai_dates_cache:
                status_text += f" ({len(self.kishakai_dates_cache)}件)"
            elif self.is_file_loaded:
                status_text += " (0件/読込済)"
            
            self.txt_file_status.value = status_text
            self.txt_file_status.color = ft.Colors.GREEN
        else:
            self.txt_file_status.value = "ファイル未設定"
            self.txt_file_status.color = ft.Colors.GREY
        
        if run_update:
            self.txt_file_status.update()

    def _load_kishakai_data(self, run_update: bool = True) -> None:
        """設定されたファイルから帰社会データをロードします。
        
        拡張子(.pdf/.json)に応じて処理を分岐します。
        """
        if not self.kishakai_file_name:
            if run_update:
                self.show_message("ファイルが設定されていません。", ft.Colors.ORANGE)
                self.chk_kishakai.value = False
                self.chk_kishakai.update()
                self._update_file_status(run_update=True)
            return

        file_path = os.path.join(self.pdf_save_dir, self.kishakai_file_name)
        if not os.path.exists(file_path):
            if run_update:
                self.show_message("設定されたファイルが見つかりません。", ft.Colors.RED)
                self._update_file_status(run_update=True)
            return

        # 拡張子による分岐
        ext = os.path.splitext(self.kishakai_file_name)[1].lower()

        try:
            if ext == ".json":
                self._load_from_json(file_path)
            elif ext == ".pdf":
                if get_kishakai_dates:
                    # PDF読み込み (自動検出ロジック)
                    self.kishakai_dates_cache = get_kishakai_dates(file_path)
                else:
                    raise ImportError("PDF読み込みモジュールが無効です")
            else:
                raise ValueError(f"サポートされていない形式です: {ext}")

            self.is_file_loaded = True
            if run_update:
                self.show_message(f"日程を読み込みました: {len(self.kishakai_dates_cache)}件")
            self._update_file_status(run_update=run_update)

        except Exception as ex:
            logger.error(f"File Read Error: {ex}")
            self.is_file_loaded = False
            if run_update:
                self.show_message(f"読み込みエラー: {ex}", ft.Colors.RED)

    def _load_from_json(self, path: str) -> None:
        """JSONファイルから日付リストを読み込みます。

        Format: ["YYYY-MM-DD", ...] -> Cache: {"YYYY/MM/DD", ...}
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, list):
            raise ValueError("JSON形式が無効です。リスト形式である必要があります。")
            
        # 正規化してセットに格納
        self.kishakai_dates_cache = set()
        for date_str in data:
            if isinstance(date_str, str):
                # "YYYY-MM-DD" -> "YYYY/MM/DD"
                normalized = date_str.replace("-", "/")
                self.kishakai_dates_cache.add(normalized)
        
        logger.info(f"Loaded {len(self.kishakai_dates_cache)} dates from JSON.")

    # --- イベントハンドラ ---
    
    def _handle_fetch_click(self, e: ft.ControlEvent) -> None:
        """データ取得ボタンクリック時の処理。"""
        if self.on_fetch:
            self.on_fetch(e)

    def _handle_bulk_fill_click(self, e: ft.ControlEvent) -> None:
        """一括入力ボタンクリック時の処理。"""
        if self.on_bulk_fill:
            self.on_bulk_fill(e)

    def _handle_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """ファイル選択時の処理。ファイルを保存し、設定を更新します。"""
        if e.files:
            try:
                f = e.files[0]
                src_path = f.path
                file_name = f.name
                dst_path = os.path.join(self.pdf_save_dir, file_name)
                
                # 同名ファイル上書き保存
                shutil.copy2(src_path, dst_path)
                
                set_key(ENV_PATH, "KISHAKAI_PDF_NAME", file_name)
                self.kishakai_file_name = file_name
                self.show_message(f"ファイルを保存しました: {file_name}")
                
                self.chk_kishakai.value = True
                self.chk_kishakai.update()
                
                self.is_file_loaded = False 
                self._save_status(True)
                self._load_kishakai_data(run_update=True)
                
            except Exception as ex:
                logger.error(f"File Save Error: {ex}")
                self.show_message(f"ファイル保存エラー: {ex}", ft.Colors.RED)

    def _handle_kishakai_check_change(self, e: ft.ControlEvent) -> None:
        """帰社会チェックボックス変更時の処理。"""
        is_checked = self.chk_kishakai.value
        self._save_status(is_checked)
        if is_checked:
            self._load_kishakai_data(run_update=True)
        else:
            self._update_file_status(run_update=True)

    # --- 公開メソッド/プロパティ ---

    @property
    def is_kishakai_mode(self) -> bool:
        """帰社会モード（チェックボックス）の状態を返します。"""
        return self.chk_kishakai.value

    @property
    def kishakai_dates(self) -> Set[str]:
        """キャッシュされている帰社会の日付セットを返します。"""
        return self.kishakai_dates_cache

    @property
    def is_pdf_loaded(self) -> bool:
        """互換性用プロパティ: is_file_loaded のエイリアス"""
        return self.is_file_loaded

    def reload_pdf_dates(self, target_year: Optional[int] = None) -> None:
        """ファイルの再読み込みを外部から実行します。

        JSONファイルの場合は target_year は無視されます。

        Args:
            target_year (Optional[int], optional): 読み込む年(PDF用)。 Defaults to None.
        """
        if not self.is_kishakai_mode:
            return
            
        if not self.kishakai_file_name:
            self.is_file_loaded = False
            return

        file_path = os.path.join(self.pdf_save_dir, self.kishakai_file_name)
        if not os.path.exists(file_path):
            self.is_file_loaded = False
            return
            
        try:
            ext = os.path.splitext(self.kishakai_file_name)[1].lower()
            if ext == ".json":
                # JSONは年指定不要（ファイル内の日付を正とする）
                self._load_from_json(file_path)
            elif ext == ".pdf":
                if get_kishakai_dates:
                    self.kishakai_dates_cache = get_kishakai_dates(file_path, target_year)
                else:
                    raise ImportError("PDF module missing")
            
            self.is_file_loaded = True
            logger.info(f"File reloaded: {len(self.kishakai_dates_cache)} dates")
            self._update_file_status(run_update=True)
        except Exception as e:
            self.is_file_loaded = False
            logger.error(f"Reload error: {e}")