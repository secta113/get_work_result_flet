# Version: 1.0
import flet as ft
from core.commons import APP_ICON_BASE64
from views.home_view import HomeView
from views.payslip_view import PayslipView
from views.schedule_view import ScheduleView
from views.estimate_view import EstimateView

class TimeCardApp:
    """アプリケーションのメインクラス。

    タブ構成のGUIアプリケーションを初期化し、実行します。

    Attributes:
        page (ft.Page): Fletのページオブジェクト。
        home_view (HomeView): ホーム画面のビュー。
        payslip_view (PayslipView): 給与明細画面のビュー。
        schedule_view (ScheduleView): 勤務表作成画面のビュー。
        estimate_view (EstimateView): 稼働見込計算画面のビュー。
        tabs (ft.Tabs): 画面切り替え用のタブコントロール。
    """

    def run(self, page: ft.Page) -> None:
        """アプリケーションを実行し、UIを構築します。

        Args:
            page (ft.Page): Fletのページオブジェクト。
        """
        self.page = page
        versuion = "2.3.1"
        self.page.title = "業務効率化ツール (V{versuion})".format(versuion=versuion)
        
        if APP_ICON_BASE64:
            self.page.window_icon = "app_icon.ico"
        
        self.page.padding = 10
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 1280
        self.page.window_height = 900 

        self.home_view = HomeView(on_navigate=self.navigate_to)
        self.payslip_view = PayslipView(page)
        self.schedule_view = ScheduleView(page)
        self.estimate_view = EstimateView(page)

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            on_change=self.handle_tab_change,
            tabs=[
                ft.Tab(text="ホーム", icon=ft.Icons.HOME, content=self.home_view),
                ft.Tab(text="給与明細", icon=ft.Icons.ATTACH_MONEY, content=self.payslip_view),
                ft.Tab(text="勤務表作成", icon=ft.Icons.CALENDAR_MONTH, content=self.schedule_view),
                ft.Tab(text="稼働見込", icon=ft.Icons.CALCULATE, content=self.estimate_view),
            ],
            expand=True,
        )

        self.page.add(self.tabs)

    def navigate_to(self, index: int) -> None:
        """指定されたインデックスのタブへ遷移します。

        Args:
            index (int): 遷移先のタブインデックス。
        """
        self.tabs.selected_index = index
        self.tabs.update()
        
        if index == 2: # Schedule
            self.schedule_view.handle_fetch_data()
        elif index == 3: # Estimate
            self.estimate_view.recalc_workdays("cur")
            self.estimate_view.recalc_workdays("nxt")

    def handle_tab_change(self, e: ft.ControlEvent) -> None:
        """タブが変更された際のイベントハンドラ。

        Args:
            e (ft.ControlEvent): イベントオブジェクト。
        """
        idx = e.control.selected_index
        if idx == 2:
            self.schedule_view.handle_fetch_data()
        elif idx == 3:
            self.estimate_view.recalc_workdays("cur")
            self.estimate_view.recalc_workdays("nxt")

if __name__ == "__main__":
    app = TimeCardApp()
    ft.app(target=app.run)