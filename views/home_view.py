# Version: 1.0
import flet as ft
from typing import Callable
from core.commons import logger

class HomeView(ft.Container):
    """ホーム画面を表示するビュークラス。

    機能選択のためのカード型メニューを提供します。

    Args:
        on_navigate (Callable[[int], None]): タブ遷移を行うためのコールバック関数。
    """

    def __init__(self, on_navigate: Callable[[int], None]):
        super().__init__()
        self.on_navigate = on_navigate
        
        self.padding = 50
        self.alignment = ft.alignment.center
        self.expand = True

        self.content = self._build_content()

    def _build_content(self) -> ft.Column:
        """画面コンテンツを構築します。

        Returns:
            ft.Column: 構築されたUIコンポーネント。
        """
        def card(icon: str, title: str, desc: str, target_index: int, color: str) -> ft.Container:
            """メニューカードを作成するヘルパー関数。

            Args:
                icon (str): アイコン名。
                title (str): タイトル。
                desc (str): 説明文。
                target_index (int): 遷移先のタブインデックス。
                color (str): アイコンの色。

            Returns:
                ft.Container: カードUIコンポーネント。
            """
            return ft.Container(
                content=ft.Column([
                    ft.Icon(icon, size=50, color=color),
                    ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(desc, text_align=ft.TextAlign.CENTER),
                    ft.ElevatedButton("開く", on_click=lambda _: self.on_navigate(target_index))
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                padding=20, bgcolor=ft.Colors.BLUE_50, border_radius=10, 
                expand=True, ink=True, on_click=lambda _: self.on_navigate(target_index)
            )

        return ft.Column([
            ft.Text("業務効率化ツール 🚀", size=30, weight=ft.FontWeight.BOLD),
            ft.Text("利用したい機能を選択してください。", size=16),
            ft.Divider(),
            ft.Row([
                # Index: 1=給与, 2=勤務, 3=稼働
                card(ft.Icons.ATTACH_MONEY, "給与明細 取得", "Web明細サイトからデータを取得し\nサマリーを作成します。", 1, ft.Colors.ORANGE),
                card(ft.Icons.CALENDAR_MONTH, "勤務表 作成", "Web勤怠サイトへデータを\n一括入力します。", 2, ft.Colors.BLUE),
                card(ft.Icons.CALCULATE, "稼働見込 計算", "当月・次月の所定稼働時間\nを自動計算します。", 3, ft.Colors.GREEN),
            ], spacing=20)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=30)