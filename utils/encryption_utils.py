# --- encryption_utils.py ---
# 役割: .env に保存するID/パスワードの暗号化・復号
# マシンのMACアドレスをベースにしたキーを使用して、Fernetによる共通鍵暗号化を行う。

import base64
import logging
import os
import uuid # MACアドレス取得のためインポート
from typing import Optional

# --- 外部ライブラリ (cryptography) ---
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logging.critical("="*50)
    logging.critical("必須ライブラリ (cryptography) が見つかりません。")
    logging.critical("pip install cryptography を実行してください。")
    logging.critical("="*50)

logger = logging.getLogger(__name__)

# --- 設定 (ハードコード) ---

# キー導出用のソルト (固定値で問題ない)
SALT = b'q\x8a\x0e\x9b\xf6\x0c\x94\xa8\x8d\x1b\xd3\x99\xe3\x8f\x0b\x1d'

# --- グローバル変数 ---

# Fernet インスタンスは一度初期化したらキャッシュする
_fernet_instance: Optional[Fernet] = None

def _get_machine_key() -> str:
    """
    PC固有のMACアドレスを取得し、暗号化キーの元として使用する。
    
    Notes:
        MACアドレスは `uuid.getnode()` を使用して取得する。
        これは 48ビットの整数値を返す。

    Returns:
        str: MACアドレスの16進数文字列 (例: '001a2b3c4d5e')。
             取得失敗時はフォールバック用の固定文字列。
    """
    try:
        # getnode() はMACアドレスを 48ビットの整数として返す
        mac_num = uuid.getnode()
        
        if (mac_num >> 40) % 2:
            # MACアドレスのU/Lビット (ユニバーサル/ローカル) が 1 の場合
            # (ランダムMACアドレスなど) は、PC再起動などで値が変わる可能性がある
            logger.warning("MACアドレスがローカル管理アドレス（ランダムMACなど）の可能性があります。")
            logger.warning("PC再起動やWi-FiのON/OFFで .env が読めなくなる場合があります。")

        # 整数を 12桁の16進数文字列 (例: '001a2b3c4d5e') に変換
        mac_str = format(mac_num, 'x').zfill(12)
        
        if mac_str == '000000000000':
            raise ValueError("有効なMACアドレスを取得できませんでした (00:00:...)。")
            
        logger.info(f"マシン固有キー (MAC) の取得成功: ...{mac_str[-6:]}")
        return mac_str
        
    except Exception as e:
        logger.error(f"マシン固有キー (MAC) の取得に失敗しました: {e}", exc_info=True)
        # 究極のフォールバック (固定文字列)
        # これを使用すると、このマシンで暗号化したデータは他のマシンでも復号可能になる
        return "fallback-static-key-if-mac-fails"


def _get_fernet_instance() -> Optional[Fernet]:
    """
    暗号化・復号に使用するFernetインスタンスを初期化または取得する（シングルトン）。
    
    MACアドレスからPBKDF2HMACを用いてキーを導出し、
    それを基にFernetインスタンスを生成する。

    Returns:
        Optional[Fernet]:
            初期化に成功したFernetインスタンス。
            cryptography がない場合や初期化失敗時は None。
    """
    global _fernet_instance
    if not CRYPTOGRAPHY_AVAILABLE:
        return None
        
    if _fernet_instance:
        return _fernet_instance

    try:
        # MACアドレスをキーの元として取得
        machine_key_str = _get_machine_key()
        
        # PBKDF2 (Password-Based Key Derivation Function 2) を使用
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32, # Fernet が要求する 32バイトキー
            salt=SALT,
            iterations=100000, # ブルートフォース耐性のための反復回数
        )
        # MACアドレス (文字列) から 32バイトのキーを導出
        key_bytes = kdf.derive(machine_key_str.encode('utf-8'))
        # Fernet が要求する base64 エンコードキーに変換
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        
        _fernet_instance = Fernet(fernet_key)
        logger.info("Fernet (暗号化) インスタンスの初期化に成功しました。")
        return _fernet_instance
    except Exception as e:
        logger.error(f"Fernet インスタンスの初期化に失敗: {e}", exc_info=True)
        return None

def encrypt(plain_text: str) -> str:
    """
    指定された平文文字列を暗号化する。

    Args:
        plain_text (str): 暗号化する文字列。

    Returns:
        str:
            暗号化された文字列 (base64)。
            ライブラリがない場合や暗号化失敗時は、平文のまま返す。
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        logger.error("cryptography ライブラリがないため暗号化できません。平文で返します。")
        return plain_text 
    
    fernet = _get_fernet_instance()
    if not fernet:
        logger.error("Fernet インスタンスの取得に失敗。平文で返します。")
        return plain_text 

    try:
        encrypted_bytes = fernet.encrypt(plain_text.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"暗号化に失敗: {e}", exc_info=True)
        return plain_text # 暗号化失敗時も平文を返す

def decrypt(encrypted_text: str) -> str:
    """
    指定された暗号化文字列を復号する。

    Args:
        encrypted_text (str): 復号する文字列 (base64)。

    Returns:
        str:
            復号された平文文字列。
            復号に失敗した場合 (MACアドレス変更、平文が渡された等) は、
            入力された文字列 (encrypted_text) をそのまま返す。
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        logger.error("cryptography ライブラリがないため復号できません。")
        return encrypted_text 
        
    fernet = _get_fernet_instance()
    if not fernet:
        logger.error("Fernet インスタンスの取得に失敗。")
        return encrypted_text 

    try:
        # Fernet 暗号は 'gAAAAA...' で始まる
        if not encrypted_text.startswith('gAAAAA'):
            logger.warning("暗号化された文字列ではありません (平文のようです)。そのまま返します。")
            return encrypted_text
            
        decrypted_bytes = fernet.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        # 復号失敗 (InvalidToken) は、キー (MACアドレス) が変わった場合に発生しうる
        logger.warning(f"復号に失敗しました: {e} (PCを移行したか、MACアドレスが変更された可能性があります)")
        return encrypted_text # 復号失敗時はそのまま返す