import logging
import re
import os
from typing import Dict, List, Tuple, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from datetime import datetime, date

from .base_handler import BaseWebHandler

class ScheduleHandler(BaseWebHandler):
    """勤務表サイト (ts.wjtime.jp) 操作用ハンドラ。

    ログイン、データ取得、および勤務データの更新処理を行います。

    Attributes:
        current_url (str): 現在保持しているページURL。
        LOGIN_URL (str): ログインページのURL。
        ORIGIN (str): Originヘッダー用のURL。
    """
    
    def __init__(self, root_dir: str) -> None:
        """ScheduleHandlerを初期化します。

        環境変数から接続先URL設定を読み込みます。

        Args:
            root_dir (str): アプリケーションのルートディレクトリ。
        """
        super().__init__(root_dir)
        self.current_url: str = ""

        # 環境変数から設定を読み込み (デフォルト値なしでNone許容)
        self.LOGIN_URL: Optional[str] = os.getenv("SCHEDULE_LOGIN_URL")
        self.ORIGIN: Optional[str] = os.getenv("SCHEDULE_ORIGIN")

        # 設定値のチェック
        if not self.LOGIN_URL or not self.ORIGIN:
            self.logger.error("環境変数の取得に失敗しました: SCHEDULE_LOGIN_URL または SCHEDULE_ORIGIN が設定されていません。")
            raise ValueError("環境変数の設定エラー")
        
    def login(self, login_id: str, password: str) -> Tuple[bool, str]:
        """勤務表サイトへログインします。

        Args:
            login_id (str): ログインID。
            password (str): パスワード。

        Returns:
            Tuple[bool, str]: (成功フラグ, メッセージ)。
        """

        payload = {
            "loginId": login_id,
            "password": password,
            "weblogin": "WEBログイン",
            "mobile": ""
        }
        try:
            self.logger.info(f"勤務表サイトへログインを試行します: {self.LOGIN_URL}")
            
            headers = {"Origin": self.ORIGIN}
            
            resp = self.session.post(self.LOGIN_URL, data=payload, headers=headers)
            self.log_response("Schedule Login", resp)
            resp.raise_for_status()
            
            if "/auth/" in resp.url:
                return False, "ログイン失敗: ID/PWを確認してください"
            
            self.current_url = resp.url
            self.logger.info(f"ログイン成功。現在のURL: {self.current_url}")
            return True, "ログイン成功"
        except Exception as e:
            self.logger.error(f"ログイン処理中にエラーが発生しました: {e}", exc_info=True)
            return False, f"ログインエラー: {e}"

    def get_current_data(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """現在のページから勤務データをパースして取得します。

        Returns:
            Tuple[bool, str, List[Dict[str, Any]]]: (成功フラグ, メッセージ, 勤務データのリスト)。
        """
        try:
            resp = self.session.get(self.current_url)
            self.log_response("Get Schedule Page", resp)
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            data = self._parse_schedule_rows(soup)
            self.logger.info(f"データパース結果: {len(data)}件のデータを取得しました。")
            
            if len(data) == 0:
                self.logger.warning("警告: 取得件数が0件です。HTML構造が変わったか、パースに失敗している可能性があります。")

            return True, "取得成功", data
        except Exception as e:
            self.logger.error(f"データ取得エラー: {e}", exc_info=True)
            return False, f"データ取得エラー: {e}", []

    def update_schedule(self, ui_data_list: List[Dict[str, Any]]) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """勤務データを一括更新します。

        バリデーションを行い、現在のフォーム情報を取得後にPOST送信し、
        最新の状態を再取得して返します。

        Args:
            ui_data_list (List[Dict[str, Any]]): 更新対象のデータリスト。

        Returns:
            Tuple[bool, str, List[Dict[str, Any]]]: (成功フラグ, メッセージ, 更新後の最新データリスト)。
        """
        if not self.ORIGIN:
            return False, "環境設定エラー: ORIGIN設定がありません。", []

        self.logger.info("update_schedule: 登録処理を開始します。")

        errors = self._validate_input(ui_data_list)
        if errors:
            error_msg = "入力内容に不備があります。修正してください。\n\n" + "\n".join(errors)
            self.logger.warning(f"バリデーションエラー: {error_msg}")
            return False, error_msg, []

        try:
            # POST先とトークン等の収集のためGET
            resp = self.session.get(self.current_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            register_btn = soup.find("input", {"name": "register"})
            if not register_btn:
                self.logger.warning("registerボタンが見つかりません。")
                form = soup
                post_url = self.current_url
            else:
                form = register_btn.find_parent("form")
                action = form.get("action")
                post_url = urljoin(self.current_url, action) if action else self.current_url
            
            self.logger.info(f"POST先URL: {post_url}")

            payload = self._build_payload(form, ui_data_list)
            
            headers = {
                "Referer": self.current_url, 
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.ORIGIN
            }
            resp_post = self.session.post(post_url, data=payload, headers=headers)
            self.log_response("Update Schedule POST", resp_post)
            resp_post.raise_for_status()
            
            if "System Error" in resp_post.text or "システムエラー" in resp_post.text:
                 self.logger.error("サーバー側でシステムエラーが発生しました。")
                 return False, "システムエラーが発生しました。", []
                 
            if "入力エラー" in resp_post.text or 'class="error"' in resp_post.text:
                error_detail = self._extract_error_message(resp_post.text)
                self.logger.error(f"サーバーから入力エラー: {error_detail}")
                return False, f"入力エラー: {error_detail}", []

            logger_msg = "登録が完了しました。"
            
            success_get, _, latest_data = self.get_current_data()
            if success_get:
                return True, logger_msg, latest_data
            else:
                return True, logger_msg + "\n(ただし最新データの再取得に失敗しました)", []

        except Exception as e:
            self.logger.error(f"登録処理中に予期せぬ例外: {e}", exc_info=True)
            return False, f"更新エラー: {e}", []

    # --- Private Helpers ---

    def _parse_schedule_rows(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """HTMLから勤務表の行データを抽出します。

        Args:
            soup (BeautifulSoup): パース対象のBeautifulSoupオブジェクト。

        Returns:
            List[Dict[str, Any]]: 抽出された勤務データのリスト。
        """
        data_list = []
        
        target_area = soup
        register_btn = soup.find("input", {"name": "register"})
        if register_btn:
            form = register_btn.find_parent("form")
            if form:
                target_area = form

        found_count = 0
        for i in range(32):
            id_input = target_area.find("input", {"name": f"workDataDetailList[{i}].id"})
            if not id_input:
                continue 
            
            found_count += 1
            row_data = {}
            row_data["index"] = i
            row_data["id"] = id_input.get("value", "")
            
            for key in ["workDate", "youbi", "youbiCode", "shukujitsu", "nenkyu", 
                        "approvalName", "slideStatus", "kakuteiShime", "kakuteiShonin", "isAvailableCopy"]:
                inp = target_area.find("input", {"name": f"workDataDetailList[{i}].{key}"})
                row_data[key] = inp.get("value", "") if inp else ""

            ui_key_map = {
                "workStartTimeHour": "start_h", "workStartTimeMinute": "start_m",
                "workEndTimeHour": "end_h", "workEndTimeMinute": "end_m",
                "restTimeHour": "rest_h", "restTimeMinute": "rest_m",
                "midnightTimeHour": "mid_h", "midnightTimeMinute": "mid_m"
            }
            for key, val_name in ui_key_map.items():
                inp = target_area.find("input", {"name": f"workDataDetailList[{i}].{key}"})
                row_data[val_name] = inp.get("value", "") if inp else ""

            work_type_select = target_area.find("select", {"name": f"workDataDetailList[{i}].workType"})
            selected_type = "99" 
            if work_type_select:
                selected_option = work_type_select.find("option", selected=True)
                if selected_option:
                    selected_type = selected_option.get("value")
            row_data["workType"] = selected_type

            comment_input = target_area.find("input", {"name": f"workDataDetailList[{i}].comment"})
            row_data["comment"] = comment_input.get("value", "") if comment_input else ""

            kakutei_input = target_area.find("input", {"name": f"workDataDetailList[{i}].kakutei"})
            row_data["is_kakutei"] = True if kakutei_input and kakutei_input.has_attr("checked") else False
            
            row_data["shukujitsu_bool"] = (row_data.get("shukujitsu") == "true")
            data_list.append(row_data)
        
        self.logger.debug(f"Parse loop finished. Found {found_count} rows.")
        return data_list

    def _validate_input(self, data_list: List[Dict[str, Any]]) -> List[str]:
        """入力データの整合性を検証します。

        Args:
            data_list (List[Dict[str, Any]]): 検証対象のデータリスト。

        Returns:
            List[str]: エラーメッセージのリスト。
        """
        error_messages = []
        def _safe_str(val: Optional[Any]) -> str:
            return str(val) if val is not None else ""

        for row in data_list:
            date_label = row.get("workDate", f"{row.get('index')}行目")
            
            s_h = _safe_str(row.get("start_h")).strip()
            s_m = _safe_str(row.get("start_m")).strip()
            e_h = _safe_str(row.get("end_h")).strip()
            e_m = _safe_str(row.get("end_m")).strip()
            r_h = _safe_str(row.get("rest_h")).strip()
            r_m = _safe_str(row.get("rest_m")).strip()
            m_h = _safe_str(row.get("mid_h")).strip()
            m_m = _safe_str(row.get("mid_m")).strip()

            if bool(s_h) != bool(s_m): error_messages.append(f"【{date_label}】開始時間の時・分不揃い")
            if bool(e_h) != bool(e_m): error_messages.append(f"【{date_label}】終了時間の時・分不揃い")
            if bool(r_h) != bool(r_m): error_messages.append(f"【{date_label}】休憩時間の時・分不揃い")
            if bool(m_h) != bool(m_m): error_messages.append(f"【{date_label}】深夜時間の時・分不揃い")

            has_start = bool(s_h) and bool(s_m)
            has_end = bool(e_h) and bool(e_m)
            if has_start != has_end:
                error_messages.append(f"【{date_label}】開始・終了時間はセットで入力してください")

            if (bool(r_h) or bool(m_h)) and not has_start:
                error_messages.append(f"【{date_label}】休憩・深夜のみの入力はできません")

        return error_messages

    def _build_payload(self, form: Tag, ui_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """POST用のペイロードデータを構築します。

        YYYY/MM/DD形式およびMM/DD形式の日付補完に対応し、
        休日の空入力時に「稼働なし」を自動設定するロジックを含みます。

        Args:
            form (Tag): フォーム要素のBeautifulSoup Tagオブジェクト。
            ui_data (List[Dict[str, Any]]): UIからの入力データ。

        Returns:
            Dict[str, str]: 送信用のPOSTデータ。
        """
        payload = {}
        def _safe_str(val: Optional[Any]) -> str:
            return str(val) if val is not None else ""

        # 1. フォーム上の全値を収集 (Hidden含む)
        for tag in form.find_all(['input', 'select', 'textarea']):
            name = tag.get('name')
            if not name: continue
            
            if tag.name == 'input' and tag.get('type') in ['checkbox', 'radio']:
                if tag.has_attr('checked'):
                    payload[name] = tag.get('value', 'on')
                continue
            
            val = tag.get('value', '')
            if tag.name == 'textarea': val = tag.get_text()
            if tag.name == 'select':
                opt = tag.find('option', selected=True)
                val = opt.get('value') if opt else (tag.find('option').get('value') if tag.find('option') else "")
                
            payload[name] = _safe_str(val)
        
        keys_to_remove = [k for k in payload.keys() if k.endswith(".kakutei")]
        for k in keys_to_remove: del payload[k]

        # 2. UIデータで上書き
        today = date.today()

        for row in ui_data:
            i = row['index']
            base = f"workDataDetailList[{i}]"
            
            try:
                w_date_str = row.get("workDate", "")
                w_date = None
                
                if w_date_str:
                    ymd = w_date_str.split("/")
                    if len(ymd) == 3:
                        w_date = date(int(ymd[0]), int(ymd[1]), int(ymd[2]))
                    elif len(ymd) == 2:
                        w_date = date(today.year, int(ymd[0]), int(ymd[1]))
                
                if w_date:
                    s_h_chk = _safe_str(row.get("start_h")).strip()
                    w_type_chk = _safe_str(row.get("workType", "99"))
                    cmt_chk = _safe_str(row.get("comment")).strip()
                    
                    is_empty_input = (not s_h_chk) and (w_type_chk == "99") and (not cmt_chk)
                    
                    is_weekend = (w_date.weekday() >= 5) 
                    is_shukujitsu = (row.get("shukujitsu") == "true")
                    is_holiday = is_weekend or is_shukujitsu

                    if (w_date < today) and is_holiday and is_empty_input:
                        row["comment"] = "稼働なし"
                        self.logger.info(f"自動補完: {w_date} に「稼働なし」をセットしました。")

            except ValueError as e:
                self.logger.warning(f"自動補完処理中に日付変換エラー (Row {i}): {e}")

            if row.get("id"): payload[f"{base}.id"] = _safe_str(row.get("id"))
            
            s_h = _safe_str(row.get("start_h"))
            s_m = _safe_str(row.get("start_m"))
            m_h = _safe_str(row.get("mid_h"))
            m_m = _safe_str(row.get("mid_m"))
            if m_h == "00": m_h = ""
            if m_m == "00": m_m = ""

            mapping = {
                "workStartTimeHour": s_h, "workStartTimeMinute": s_m,
                "workEndTimeHour": _safe_str(row.get("end_h")), "workEndTimeMinute": _safe_str(row.get("end_m")),
                "restTimeHour": _safe_str(row.get("rest_h")), "restTimeMinute": _safe_str(row.get("rest_m")),
                "midnightTimeHour": m_h, "midnightTimeMinute": m_m,
                "workType": _safe_str(row.get("workType", "99")),
                "comment": _safe_str(row.get("comment"))
            }
            
            for k, v in mapping.items():
                payload[f"{base}.{k}"] = v
            
            has_time = bool(s_h and s_h.strip())
            has_cmt = bool(row.get("comment"))
            has_type = bool(mapping["workType"] and mapping["workType"] != "99")
            
            if has_time or has_cmt or has_type:
                payload[f"{base}.kakutei"] = "true"

        for k in list(payload.keys()):
            if payload[k] is None: payload[k] = ""
        payload["register"] = "登録"
        
        return payload

    def _extract_error_message(self, html_text: str) -> str:
        """HTMLからエラーメッセージを抽出します。

        Args:
            html_text (str): エラーを含むHTMLテキスト。

        Returns:
            str: 抽出されたエラーメッセージ。
        """
        soup = BeautifulSoup(html_text, 'html.parser')
        err_msgs = []
        for err in soup.find_all(class_="error"):
            t = err.get_text(strip=True)
            if t: err_msgs.append(t)
        
        if not err_msgs:
            try:
                err_ul = soup.find("ul", style=re.compile(r"color:\s*red", re.I))
                if err_ul:
                    for li in err_ul.find_all("li"):
                        err_msgs.append(li.get_text(strip=True))
            except Exception: pass
            
        return " / ".join(err_msgs) if err_msgs else "（詳細不明）"