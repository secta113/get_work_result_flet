# Version: 1.1
import os
import sys
import logging
from dotenv import load_dotenv

import flet as ft

# --- パス設定 ---
# 実行環境(exeかscriptか)に応じてルートディレクトリを決定
if getattr(sys, 'frozen', False):
    # PyInstallerでexe化されている場合
    APP_BUNDLE_DIR = os.path.abspath(os.getcwd()) # または os.path.dirname(sys.executable)
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    # 通常のPythonスクリプト実行の場合
    APP_BUNDLE_DIR = os.path.abspath(os.getcwd())
    ROOT_DIR = os.path.abspath(os.path.join(APP_BUNDLE_DIR, ".."))

ENV_PATH = os.path.join(APP_BUNDLE_DIR, ".env")
load_dotenv(ENV_PATH)

# --- ログ設定 ---
# outputフォルダの作成（存在しない場合）
LOG_DIR = os.path.join(APP_BUNDLE_DIR, "output")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

# ログ設定：コンソールとファイルの両方に出力
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),               # コンソール出力
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')  # ファイル出力(output/app.log)
    ]
)
logger = logging.getLogger(__name__)


# --- 定数定義 ---
WORK_TYPE_OPTIONS = ["稼働", "休日", "有給", "半休", "欠勤", "遅早"]
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAYS_NO_WEEKEND = ["月", "火", "水", "木", "金"] 

WORK_TYPE_MAP_REVERSE = {
    "稼働": "99", "休日": "99", "有給": "12", "半休": "81", "欠勤": "11", "遅早": "85"
}
CODE_TO_NAME = {v: k for k, v in WORK_TYPE_MAP_REVERSE.items() if v != "99"}

# --- 外部モジュール (モック対応) ---
try:
    import jpholiday
except ImportError:
    jpholiday = None

try:
    from utils.encryption_utils import decrypt, encrypt, CRYPTOGRAPHY_AVAILABLE
    from handlers.schedule_handler import ScheduleHandler
    from core.main_controller import run_main_logic
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"外部モジュールが見つかりません: {e}")
    MODULES_AVAILABLE = False
    CRYPTOGRAPHY_AVAILABLE = False
    def decrypt(x): return x
    def encrypt(x): return x
    class ScheduleHandler: # Mock
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def login(self, i, p): return False, "モジュール未ロード"
    def run_main_logic(*args): return False, {"error": "モジュール未ロード"}

try:
    from icon_data import APP_ICON_BASE64
except ImportError:
    APP_ICON_BASE64 = None

# --- 共通ヘルパークラス ---
class FletStatusPlaceholder:
    def __init__(self, text_control: ft.Text, page: ft.Page):
        self.text_control = text_control
        self.page = page

    def _update(self, msg, color):
        if self.text_control:
            self.text_control.value = str(msg)
            self.text_control.color = color
            self.text_control.update() 

    def info(self, msg): self._update(msg, ft.Colors.BLUE)
    def success(self, msg): self._update(msg, ft.Colors.GREEN)
    def warning(self, msg): self._update(msg, ft.Colors.ORANGE)
    def error(self, msg): self._update(msg, ft.Colors.RED)
    def write(self, msg): self._update(msg, ft.Colors.BLACK)
    def empty(self): self._update("", ft.Colors.BLACK)