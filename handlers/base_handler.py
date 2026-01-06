import logging
import os
from abc import ABC
from typing import Optional, Type
import requests

class BaseWebHandler(ABC):
    """Webサイト操作ハンドラの基底クラス。

    requests.Sessionの管理、共通ヘッダーの適用、および通信ログの出力機能を提供します。

    Attributes:
        root_dir (str): アプリケーションのルートディレクトリパス。
        session (requests.Session): HTTPセッションオブジェクト。
        logger (logging.Logger): ロガーインスタンス。
        log_path (str): 通信ログの出力先ファイルパス。
    """

    def __init__(self, root_dir: str) -> None:
        """BaseWebHandlerを初期化します。

        Args:
            root_dir (str): アプリケーションのルートディレクトリ。
        """
        self.root_dir: str = root_dir
        self.session: requests.Session = requests.Session()
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        
        # 共通ヘッダー設定
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        })
        
        self.log_path: str = ""
        self._setup_network_log()

    def _setup_network_log(self) -> None:
        """デバッグ用ネットワークログの出力先ディレクトリとファイルパスを設定します。"""
        try:
            output_dir = os.path.join(self.root_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            self.log_path = os.path.join(output_dir, "debug_network_log.txt")
        except OSError:
            pass

    def log_response(self, step_name: str, response: requests.Response) -> None:
        """通信結果をログファイルに記録します。

        Args:
            step_name (str): 処理のステップ名（ログの見出しに使用）。
            response (requests.Response): 記録対象のレスポンスオブジェクト。
        """
        response.encoding = response.apparent_encoding
        
        if not self.log_path:
            return
            
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [{self.__class__.__name__}] {step_name} ---\n")
                f.write(f"URL: {response.request.url}\n")
                f.write(f"Status: {response.status_code}\n")
                f.write("\n")
        except OSError:
            pass

    def close(self) -> None:
        """セッションを閉じ、リソースを解放します。"""
        self.session.close()

    def __enter__(self) -> "BaseWebHandler":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[any]) -> None:
        self.close()