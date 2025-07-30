# api_key_manager.py (修正後)
import os
import json
import asyncio
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# セッションファイル（最後に使ったキーのインデックスを保存する場所）
SESSION_FILE = os.path.join(os.getcwd(), '.session_data.json')

class ApiKeyManager:
    """
    複数のAPIキーを管理し、安全なローテーション、セッションの永続化、
    および高負荷な並列処理下でのレースコンディションを回避するシステム。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ApiKeyManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self._api_keys: list[str] = []
        self._current_index: int = -1
        
        # --- ▼▼▼ 修正ポイント2: 不要な変数を削除 ▼▼▼ ---
        # self._last_access_time: float = 0.0
        # self._COOLDOWN_SECONDS = 1.0
        # --- ▲▲▲ 修正ポイント2: 不要な変数を削除 ▲▲▲ ---

        self._key_selection_lock = asyncio.Lock()
        
        self._load_api_keys_from_env()
        self._load_session()
        
        print(f"[{self.__class__.__name__}] 初期化完了。{len(self._api_keys)}個のキーをロードしました。")

    def _load_api_keys_from_env(self):
        keys = set()
        base_key = os.getenv('GOOGLE_API_KEY')
        if base_key:
            keys.add(base_key)
        
        i = 1
        while True:
            key = os.getenv(f'GOOGLE_API_KEY_{i}')
            if key:
                keys.add(key)
                i += 1
            else:
                break
        
        self._api_keys = list(keys)
        if not self._api_keys:
            print("警告: 有効なAPIキーが.envファイルに設定されていません。")

    def _load_session(self):
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, 'r') as f:
                    data = json.load(f)
                    last_index = data.get('lastKeyIndex', -1)
                    if 0 <= last_index < len(self._api_keys):
                        self._current_index = last_index
                        print(f"[{self.__class__.__name__}] セッションをロードしました。次のキーインデックスは { (last_index + 1) % len(self._api_keys) } から開始します。")
                    else:
                        self._current_index = -1
        except (IOError, json.JSONDecodeError) as e:
            print(f"セッションファイルの読み込み中にエラーが発生しました: {e}")
            self._current_index = -1

    def save_session(self):
        if not self._api_keys:
            return
        try:
            with open(SESSION_FILE, 'w') as f:
                json.dump({'lastKeyIndex': self._current_index}, f)
        except IOError as e:
            print(f"セッションファイルの保存に失敗しました: {e}")

    async def get_next_key(self) -> str | None:
        """
        次の利用可能なAPIキーを、安全な排他制御付きで取得する。
        """
        if not self._api_keys:
            print("エラー: 利用可能なAPIキーがありません。")
            return None

        async with self._key_selection_lock:
            # --- ▼▼▼ 修正ポイント1: クールダウン（待機）ロジックを完全に削除 ---
            # 前回の呼び出しからクールダウン時間内に再度呼び出された場合、待機する
            # ループの初回実行時などを考慮し、self._last_access_timeが0より大きい場合のみチェック
            # if self._last_access_time > 0:
            #     now = asyncio.get_event_loop().time()
            #     elapsed_time = now - self._last_access_time
            #     if elapsed_time < self._COOLDOWN_SECONDS:
            #         wait_time = self._COOLDOWN_SECONDS - elapsed_time
            #         await asyncio.sleep(wait_time)
            # --- ▲▲▲ 修正ポイント1: クールダウン（待機）ロジックを完全に削除 ▲▲▲ ---
            
            # ラウンドロビン方式で次のインデックスを計算
            self._current_index = (self._current_index + 1) % len(self._api_keys)
            
            # --- ▼▼▼ 修正ポイント2: 不要な変数の更新を削除 ▼▼▼ ---
            # self._last_access_time = asyncio.get_event_loop().time()
            # --- ▲▲▲ 修正ポイント2: 不要な変数の更新を削除 ▲▲▲ ---
            
            return self._api_keys[self._current_index]

    @property
    def last_used_key_info(self) -> dict:
        if self._current_index == -1 or not self._api_keys:
            return {
                "key_snippet": "N/A",
                "index": -1,
                "total": len(self._api_keys)
            }
        
        key = self._api_keys[self._current_index]
        return {
            "key_snippet": key[-4:],
            "index": self._current_index,
            "total": len(self._api_keys)
        }

api_key_manager = ApiKeyManager()