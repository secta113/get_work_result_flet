import os
from typing import Dict, Any, Tuple, List, Set, Optional
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

from .base_handler import BaseWebHandler

class PayslipHandler(BaseWebHandler):
    """給与・賞与明細サイト (ASP.NET) 操作用ハンドラ。

    ASP.NETのViewStateを管理しながら画面遷移を行い、明細データを取得します。

    Attributes:
        BASE_URL (str): 明細サイトのベースURL。
        current_form_data (Dict[str, str]): 現在のViewState等を含むフォームデータ。
        current_url (str): 現在のページURL。
        menu_url (str): メニュー画面のURL（遷移の起点）。
        menu_form_data (Dict[str, str]): メニュー画面のフォームデータ。
    """
    
    BASE_URL: str = "https://meisai.palma-svc.co.jp/users"
    
    def __init__(self, root_dir: str) -> None:
        """PayslipHandlerを初期化します。

        Args:
            root_dir (str): アプリケーションのルートディレクトリ。
        """
        super().__init__(root_dir)
        self.current_form_data: Dict[str, str] = {}
        self.current_url: str = ""
        self.menu_url: str = ""
        self.menu_form_data: Dict[str, str] = {}

    # =================================================================
    # ヘルパーメソッド (内部利用)
    # =================================================================
    
    def _update_aspnet_state(self, soup: BeautifulSoup, url: str) -> None:
        """レスポンスHTMLからASP.NETのViewState等を抽出し、内部状態を更新します。

        Args:
            soup (BeautifulSoup): 解析対象のHTML。
            url (str): 現在のURL。
        """
        self.current_url = url
        try:
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            event_val = soup.find('input', {'name': '__EVENTVALIDATION'})
            view_gen = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            
            self.current_form_data = {
                "__VIEWSTATE": viewstate.get('value', '') if viewstate else "",
                "__EVENTVALIDATION": event_val.get('value', '') if event_val else "",
                "__VIEWSTATEGENERATOR": view_gen.get('value', '') if view_gen else ""
            }
        except Exception:
            self.logger.warning("ASP.NET Stateの抽出に失敗しました")
            self.current_form_data = {}

    def _get_timestamp_from_url(self, url: str) -> Optional[str]:
        """URLクエリパラメータからtimestampを取得します。

        Args:
            url (str): 解析対象のURL。

        Returns:
            Optional[str]: タイムスタンプ文字列。存在しない場合はNone。
        """
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            return query.get('timestamp', [None])[0]
        except Exception:
            return None

    def _parse_detail_salary(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """給与詳細HTMLをパースしてデータを抽出します。

        Args:
            soup (BeautifulSoup): 解析対象のHTML。

        Returns:
            Dict[str, Any]: 抽出された給与データの辞書。
        """
        data = {k: "N/A" for k in ["総支給額", "差引支給額", "総時間外", "有給消化時間", "有給使用日数", "有給残日数"]}
        try:
            html_div = soup.find('div', id='Html')
            if html_div:
                for dl in html_div.find_all('dl'):
                    dt = dl.find('dt')
                    dd = dl.find('dd')
                    if dt and dd:
                        key = dt.get_text(strip=True)
                        val_str = dd.get_text(strip=True).replace(',', '')
                        try:
                            val_num = float(val_str) if '.' in val_str else int(val_str)
                        except ValueError:
                            val_num = val_str
                        
                        mapping = {
                            '総支給額': '総支給額', '差引支給額': '差引支給額', '総時間外': '総時間外',
                            '有給消化時間': '有給消化時間', '有休使用日数': '有給使用日数', '有休残日数': '有給残日数'
                        }
                        if key in mapping:
                            data[mapping[key]] = val_num
        except Exception:
            pass
        return data

    def _parse_detail_bonus(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """賞与詳細HTMLをパースしてデータを抽出します。

        Args:
            soup (BeautifulSoup): 解析対象のHTML。

        Returns:
            Dict[str, Any]: 抽出された賞与データの辞書。
        """
        data = {k: "N/A" for k in ["賞与額", "控除合計", "差引支給額", "総支給額", "所得税", "社会保険料計"]}
        try:
            html_div = soup.find('div', id='Html')
            if html_div:
                for dl in html_div.find_all('dl'):
                    dt = dl.find('dt')
                    dd = dl.find('dd')
                    if dt and dd:
                        key = dt.get_text(strip=True)
                        val_str = dd.get_text(strip=True).replace(',', '')
                        try: val_num = int(val_str)
                        except ValueError: val_num = val_str
                        
                        if key in data:
                            data[key] = val_num
        except Exception:
            pass
        return data

    # =================================================================
    # パブリックメソッド (操作フロー)
    # =================================================================

    def login(self, login_id: str, password: str) -> Tuple[bool, str]:
        """明細サイトへログインします。

        Args:
            login_id (str): ログインID。
            password (str): パスワード。

        Returns:
            Tuple[bool, str]: (成功フラグ, メッセージ)。
        """
        company_code = os.getenv("LOGIN_COMPANY_CODE")
        if not company_code:
            return False, "環境変数 'LOGIN_COMPANY_CODE' が未設定です"

        login_url = f"{self.BASE_URL}/Login.aspx?c={company_code}"
        
        try:
            # GET
            resp = self.session.get(login_url)
            self.log_response("Login Page GET", resp)
            soup = BeautifulSoup(resp.text, 'html.parser')
            self._update_aspnet_state(soup, resp.url)
            
            # POST
            payload = {
                "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                **self.current_form_data,
                "HiddenField1": "JavaScript On!", "CheckWidth": "99999",
                "txtLoginID": login_id, "txtLoginPW": password,
                "cmdSubmit": "ログイン"
            }
            resp = self.session.post(login_url, data=payload)
            self.log_response("Login POST", resp)
            
            if "PMenu.aspx" not in resp.url:
                return False, "ログインに失敗しました"
            
            # メニュー画面の状態を保存
            soup = BeautifulSoup(resp.text, 'html.parser')
            self._update_aspnet_state(soup, resp.url)
            self.menu_url = resp.url
            self.menu_form_data = self.current_form_data.copy()
            
            return True, "ログイン成功"
            
        except Exception as e:
            return False, f"ログインエラー: {e}"

    def logout(self) -> None:
        """ログアウト処理を実行します。"""
        if not self.menu_url:
            return
        try:
            payload = {
                "__EVENTTARGET": "cmdLogOut", "__EVENTARGUMENT": "",
                **self.current_form_data
            }
            resp = self.session.post(self.current_url, data=payload, headers={"Referer": self.current_url})
            self.log_response("Logout", resp)
        except Exception as e:
            self.logger.error(f"ログアウト中にエラー: {e}")

    def fetch_salary_data(self, target_dates_set: Set[str]) -> List[Dict[str, Any]]:
        """対象月の給与明細を取得します。

        Args:
            target_dates_set (Set[str]): 取得対象の日付文字列セット（例: {"令和07年07月..."}）。

        Returns:
            List[Dict[str, Any]]: 取得した給与データのリスト。
        """
        results = []
        if not target_dates_set:
            return results

        self.logger.info(">>> 給与明細の取得開始")
        try:
            # メニュー -> 給与一覧
            payload = {
                "__EVENTTARGET": "cmdShowSalary", "__EVENTARGUMENT": "",
                **self.menu_form_data
            }
            resp = self.session.post(self.menu_url, data=payload, headers={"Referer": self.menu_url})
            self.log_response("To Salary List", resp)
            
            list_soup = BeautifulSoup(resp.text, 'html.parser')
            self._update_aspnet_state(list_soup, resp.url)
            list_url = resp.url
            list_form = self.current_form_data.copy()

            targets = []
            table = list_soup.find('table', {'id': 'tdb'})
            if table:
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) < 3: continue
                    d_text = cells[2].get_text(strip=True)
                    if d_text[0:8] in target_dates_set:
                        btn = cells[1].find('input')
                        if btn: targets.append((d_text, btn.get('name')))

            for d_text, btn_name in targets:
                p_load = {
                    "__EVENTTARGET": btn_name, "__EVENTARGUMENT": "",
                    **list_form
                }
                resp = self.session.post(list_url, data=p_load, headers={"Referer": list_url})
                self.log_response(f"Salary Detail {d_text}", resp)
                
                det_soup = BeautifulSoup(resp.text, 'html.parser')
                data = self._parse_detail_salary(det_soup)
                data["年月日"] = d_text
                results.append(data)
                
                # 戻る
                self._update_aspnet_state(det_soup, resp.url)
                ts = self._get_timestamp_from_url(resp.url)
                b_load = {
                    "__EVENTTARGET": "cmdGoBack", "__EVENTARGUMENT": "",
                    **self.current_form_data,
                    "timestamp": ts
                }
                resp = self.session.post(resp.url, data=b_load, headers={"Referer": resp.url})
                
                list_soup = BeautifulSoup(resp.text, 'html.parser')
                self._update_aspnet_state(list_soup, resp.url)
                list_url = resp.url
                list_form = self.current_form_data.copy()

            # メニューに戻る
            b_load = {
                "__EVENTTARGET": "cmdGoBack", "__EVENTARGUMENT": "",
                **list_form
            }
            resp = self.session.post(list_url, data=b_load, headers={"Referer": list_url})
            self.log_response("Back to Menu", resp)
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            self._update_aspnet_state(soup, resp.url)
            self.menu_url = resp.url
            self.menu_form_data = self.current_form_data.copy()

        except Exception as e:
            self.logger.error(f"給与取得エラー: {e}")
        
        return results

    def fetch_bonus_data(self, target_reiwa_year: str, existing_dates: Set[str]) -> List[Dict[str, Any]]:
        """指定年の賞与明細を取得します。

        Args:
            target_reiwa_year (str): 対象の令和年（例: "令和07年"）。
            existing_dates (Set[str]): 既に取得済みの支給日セット。

        Returns:
            List[Dict[str, Any]]: 取得した賞与データのリスト。
        """
        results = []
        self.logger.info(">>> 賞与明細の取得開始")
        
        try:
            # メニュー -> 賞与一覧
            payload = {
                "__EVENTTARGET": "cmdShowBonus", "__EVENTARGUMENT": "",
                **self.menu_form_data
            }
            resp = self.session.post(self.menu_url, data=payload, headers={"Referer": self.menu_url})
            self.log_response("To Bonus List", resp)
            
            if "PShowSB.aspx" not in resp.url:
                self.logger.info("賞与ページへ遷移できませんでした")
                return results

            list_soup = BeautifulSoup(resp.text, 'html.parser')
            self._update_aspnet_state(list_soup, resp.url)
            list_url = resp.url
            list_form = self.current_form_data.copy()

            targets = []
            table = list_soup.find('table', {'id': 'tdb'})
            if table:
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) < 3: continue
                    d_text = cells[2].get_text(strip=True)
                    
                    if target_reiwa_year in d_text and d_text not in existing_dates:
                        btn = cells[1].find('input')
                        if btn: targets.append((d_text, btn.get('name')))
            
            for d_text, btn_name in targets:
                p_load = {
                    "__EVENTTARGET": btn_name, "__EVENTARGUMENT": "",
                    **list_form
                }
                resp = self.session.post(list_url, data=p_load, headers={"Referer": list_url})
                self.log_response(f"Bonus Detail {d_text}", resp)
                
                det_soup = BeautifulSoup(resp.text, 'html.parser')
                data = self._parse_detail_bonus(det_soup)
                data["支給日"] = d_text
                results.append(data)
                
                # 戻る
                self._update_aspnet_state(det_soup, resp.url)
                ts = self._get_timestamp_from_url(resp.url)
                b_load = {
                    "__EVENTTARGET": "cmdGoBack", "__EVENTARGUMENT": "",
                    **self.current_form_data,
                    "timestamp": ts
                }
                resp = self.session.post(resp.url, data=b_load, headers={"Referer": resp.url})
                
                list_soup = BeautifulSoup(resp.text, 'html.parser')
                self._update_aspnet_state(list_soup, resp.url)
                list_url = resp.url
                list_form = self.current_form_data.copy()
            
            # メニューに戻る
            b_load = {
                "__EVENTTARGET": "cmdGoBack", "__EVENTARGUMENT": "",
                **list_form
            }
            resp = self.session.post(list_url, data=b_load, headers={"Referer": list_url})
            self.log_response("Back to Menu (Bonus End)", resp)

            soup = BeautifulSoup(resp.text, 'html.parser')
            self._update_aspnet_state(soup, resp.url)
            self.menu_url = resp.url
            self.menu_form_data = self.current_form_data.copy()
            
        except Exception as e:
            self.logger.error(f"賞与取得エラー: {e}")
            
        return results