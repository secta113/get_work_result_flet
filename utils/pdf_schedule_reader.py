# v1.4 (Fix: Regex update to support "2025帰社会..." pattern)
import pdfplumber
import logging
import re
import datetime
import os
from typing import Optional

# ログ設定
logger = logging.getLogger(__name__)

def normalize_text(text):
    """
    テキストの正規化を行う関数
    """
    if text is None:
        return ""
    
    replacements = {
        '⽉': '月', '⽇': '日', '⽔': '水', '⾦': '金',
        '⼟': '土', '⽊': '木', '⽕': '火',
        ' ': ' ', ' ': ' ',
    }
    
    text = text.strip()
    for radical, standard in replacements.items():
        text = text.replace(radical, standard)

    text = text.replace(" ", "").replace("　", "")
    return text

def extract_year_from_text(text: str) -> Optional[int]:
    """
    テキストから西暦（20xx年/年度/帰社...）を抽出する
    """
    if not text:
        return None
    
    # パターン1: "2025年", "2025年度", "2025帰社" など
    # (?:\s*) は0文字以上の空白を許容
    match = re.search(r'(20[2-3]\d)(?:\s*(?:年|年度|帰社))', text)
    if match:
        return int(match.group(1))
        
    return None

def extract_year_from_filename(path: str) -> Optional[int]:
    """
    ファイルパス（ファイル名）から西暦を抽出する
    """
    if not path:
        return None
    filename = os.path.basename(path)
    # ファイル名なら "2025" などの数字4桁があればそれを年とみなす
    match = re.search(r'(20[2-3]\d)', filename)
    if match:
        return int(match.group(1))
    return None

def get_kishakai_dates(pdf_path: str, target_year: Optional[int] = None) -> set:
    """
    指定されたPDFを読み込み、スケジュール（帰社会）の日付リストを返します。
    """
    if not os.path.exists(pdf_path):
        logger.warning(f"PDFファイルが見つかりません: {pdf_path}")
        return set()

    found_dates = set()
    detected_year = None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # --- 1. 年の自動検出フェーズ ---
            if target_year is None:
                # A. 本文テキストから検索
                for page in pdf.pages:
                    text = page.extract_text()
                    # 最初のページで見つかれば即終了
                    detected_year = extract_year_from_text(text)
                    if detected_year:
                        logger.info(f"PDF本文から年を検出しました: {detected_year}年 (Pattern Match)")
                        break
                
                # B. ファイル名から検索 (本文になかった場合)
                if detected_year is None:
                    detected_year = extract_year_from_filename(pdf_path)
                    if detected_year:
                        logger.info(f"ファイル名から年を検出しました: {detected_year}年")

                # C. 現在の年 (最終手段)
                if detected_year is None:
                    detected_year = datetime.datetime.now().year
                    logger.warning(f"年を検出できなかったため、現在の年({detected_year})を使用します")
            else:
                detected_year = target_year

            logger.info(f"PDF解析開始: {pdf_path} (Base Year: {detected_year})")

            # --- 2. テーブル解析フェーズ ---
            current_month = None 

            for i, page in enumerate(pdf.pages):
                table = page.extract_table()
                if not table:
                    continue

                for row in table:
                    if not row or len(row) < 2:
                        continue

                    # 正規化
                    row_texts = [normalize_text(cell) for cell in row]
                    
                    col_month = row_texts[0] # 月カラム
                    col_date = row_texts[1]  # 日カラム

                    # --- 月の判定 ---
                    month_match = re.search(r'(\d+)', col_month)
                    if month_match:
                        current_month = int(month_match.group(1))
                    elif current_month is None:
                        continue

                    # --- 日の判定 ---
                    day_match = re.search(r'(\d+)', col_date)
                    
                    if current_month and day_match:
                        day = int(day_match.group(1))
                        try:
                            # 簡易的な年生成
                            dt = datetime.date(detected_year, current_month, day)
                            date_str = dt.strftime("%Y/%m/%d")
                            found_dates.add(date_str)
                        except ValueError:
                            continue

        logger.info(f"抽出完了: {len(found_dates)}件の日付が見つかりました")
        return found_dates

    except Exception as e:
        logger.error(f"PDF解析中にエラーが発生しました: {e}")
        return set()

if __name__ == "__main__":
    # テスト用
    # テストファイル名やパスは適宜書き換えてください
    test_pdf = "../../data/Internal_meeting/2025年帰社会スケジュール.pdf" 
    if os.path.exists(test_pdf):
        dates = get_kishakai_dates(test_pdf)
        print(f"Detected Dates: {dates}")