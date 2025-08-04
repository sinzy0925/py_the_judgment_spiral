# gemini_search_parallel.py (全機能統合・バグ修正・最終版)

import os
import sys
import time
import argparse
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import re
from google.api_core import exceptions
from api_key_manager1 import api_key_manager

#load_dotenv()

if 'GOOGLE_API_KEY' in os.environ:
    del os.environ['GOOGLE_API_KEY']

# --- 1件ごとの追記処理のための、ファイル書き込みロック ---
file_write_lock = asyncio.Lock()

MODEL_NAME = 'gemini-2.5-flash'

LOG_DIR = "log1"

LINES_PER_QUERY = 3
# --- ▼▼▼ この変数を追加 ▼▼▼ ---
# 1クエリあたりにまとめる行数をここで指定
# 1 => 1行で1件
# 2 => 2行で1件
# --- ▲▲▲ この変数を追加 ▲▲▲ ---

def split_json_by_status(input_file=f'{LOG_DIR}/output.json'):
    """
    指定されたJSONファイルを読み込み、'status'キーの値に応じて、
    'success.json' と 'terminated.json' に分割して出力する。
    
    Args:
        input_file (str): 読み込むJSONファイルのパス。
    """
    try:
        # --- 1. 入力ファイルを読み込む ---
        print(f"'{input_file}' を読み込んでいます...")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"エラー: ファイル '{input_file}' の内容はJSON配列（リスト）ではありません。", file=sys.stderr)
            sys.exit(1)
            
        # --- 2. データを振り分けるための空のリストを用意 ---
        success_items = []
        terminated_items = []
        other_items_count = 0

        # --- 3. 全データをループして、statusに応じてリストに追加 ---
        for item in data:
            # itemが辞書型で、かつ'status'キーを持っているか確認
            if isinstance(item, dict) and 'status' in item:
                if item['status'] == 'success':
                    success_items.append(item)
                elif item['status'] == 'terminated':
                    terminated_items.append(item)
                else:
                    other_items_count += 1
            else:
                other_items_count += 1
        
        # --- 4. 'success.json' に書き込む ---
        success_filename = f'{LOG_DIR}/success.json'
        print(f"'{success_filename}' に {len(success_items)} 件のデータを書き込んでいます...")
        with open(success_filename, 'w', encoding='utf-8') as f:
            # indent=2 で見やすい形式に整形し、ensure_ascii=Falseで日本語の文字化けを防ぐ
            json.dump(success_items, f, indent=2, ensure_ascii=False)
            
        # --- 5. 'terminated.json' に書き込む ---
        terminated_filename = f'{LOG_DIR}/terminated.json'
        print(f"'{terminated_filename}' に {len(terminated_items)} 件のデータを書き込んでいます...")
        with open(terminated_filename, 'w', encoding='utf-8') as f:
            json.dump(terminated_items, f, indent=2, ensure_ascii=False)
            
        # --- ▼▼▼ ここから修正箇所 ▼▼▼ ---

        # --- 6. 処理結果のサマリーをJSONオブジェクトとして作成 ---
        summary_data = {
            "total_read_count": len(data),
            "success": {
                "count": len(success_items),
                "filename": success_filename
            },
            "terminated": {
                "count": len(terminated_items),
                "filename": terminated_filename
            },
            "other": {
                "count": other_items_count,
                "description": "statusが'success'でも'terminated'でもない、またはstatusキーが存在しないアイテム"
            }
        }
        
        # --- 7. サマリーを 'summary.json' に書き込む ---
        summary_filename = f'{LOG_DIR}/summary.json'
        print(f"処理結果のサマリーを '{summary_filename}' に書き込んでいます...")
        with open(summary_filename, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
        # --- 8. 処理結果のサマリーをコンソールにも表示（従来通り） ---
        print("\n--- 処理完了 ---")
        print(f"読み込み総件数: {summary_data['total_read_count']}件")
        print(f" -> '{summary_data['success']['filename']}': {summary_data['success']['count']}件")
        print(f" -> '{summary_data['terminated']['filename']}': {summary_data['terminated']['count']}件")
        if summary_data['other']['count'] > 0:
            print(f" -> 対象外の件数: {summary_data['other']['count']}件")
        print(f" -> サマリーファイル: '{summary_filename}' が作成されました。")
        print("------------------")
        
        # --- ▲▲▲ ここまで修正箇所 ▲▲▲ ---

    except FileNotFoundError:
        print(f"エラー: ファイル '{input_file}' が見つかりません。", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"エラー: ファイル '{input_file}' は有効なJSON形式ではありません。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)

#def _blocking_call_to_gemini(api_key: str, full_contents: str, query_for_log_base: str, parallel_count: int, task_id: int):
def test_blocking_call_to_gemini(
    loop: asyncio.AbstractEventLoop,
    api_key_manager, # ApiKeyManagerのインスタンス
    api_key: str, 
    full_contents: str, 
    query_for_log_base: str, 
    parallel_count: int, 
    task_id: int
):    # Geminiを呼び出すメイン関数　リトライ機能付き
    # 単独処理の場合は、AI思考ログを出力する。
    # 並列処理の場合は、AI思考ログを出力しない。
    query_for_log = query_for_log_base[6:26] + '...' if len(query_for_log_base) > 50 else query_for_log_base
    log_prefix = f"Task{task_id} API {api_key[-6:]} {query_for_log}"
    MAX_RETRIES = 3    # リトライ回数
    INITIAL_DELAY = 10 # リトライまでの待ち時間

    for attempt in range(MAX_RETRIES):
        try:
            if not api_key:
                print(f"\nエラー ({log_prefix}): 有効なAPIキーがありません。", file=sys.stderr)
                return None, None

            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=-1, include_thoughts=True)
            )
            if attempt == 0:
                print(f"({log_prefix}) AIが思考を開始します...", file=sys.stderr)
            api_call_start_time = time.time()
            stream = client.models.generate_content_stream(
                model=MODEL_NAME, 
                contents=full_contents, 
                config=config
            )
            
            thinking_text, answer_text = "", ""
            
            
            is_first_thought = True # 思考ログの初回かどうかを判定するフラグ
            
            for chunk in stream:
                if not chunk.candidates: continue

                # SDKのバージョンやレスポンス形式の差異に対応
                if hasattr(chunk.candidates[0].content, 'parts'):
                    parts = chunk.candidates[0].content.parts
                else:
                    parts = []
                
                for part in parts:
                    if not hasattr(part, 'text') or not part.text: continue
                    
                    # 'thought' 属性の有無で思考ログかどうかを判定
                    is_thought = hasattr(part, 'thought') and part.thought
                    
                    if is_thought and parallel_count <= 1:
                        if is_first_thought :
                            # 最初の思考ログの前に、見出しと改行を表示する
                            print(f"\n--- AIの思考プロセス ({log_prefix}) ---", file=sys.stderr)
                            is_first_thought = False
                        # 思考ログを画面にリアルタイムで出力
                        print(part.text, end="", flush=True, file=sys.stderr)
                        thinking_text += part.text
                    else:
                        answer_text += part.text

            if not is_first_thought and parallel_count <= 1:
                # 思考ログが表示された場合、見やすくするために最後に改行を入れる
                print("", file=sys.stderr)


            elapsed = time.time() - api_call_start_time
            #print(f"({log_prefix}) 全ストリーム受信完了 ({elapsed:.2f}s)。", file=sys.stderr)
            return thinking_text, answer_text
            
        # --- ▼▼▼ 例外処理を修正 ▼▼▼ ---
        except Exception as e:
            error_message = str(e).lower()
            # 429 レートリミットエラーかどうかを文字列で判定
            if "429" in error_message and "resource_exhausted" in error_message:
                if attempt < MAX_RETRIES - 1:
                    # 待機時間を指数関数的に増やす (10秒, 20秒, 40秒...)
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(f"\n警告 ({log_prefix}): APIレートリミットです。{delay}秒待機して再試行します... (試行 {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(delay)
                    # 次のループでリトライを試みる
                    continue
                else:
                    print(f"\nエラー ({log_prefix}): APIレートリミットによる最大リトライ回数({MAX_RETRIES}回)を超えました。", file=sys.stderr)
                    # ループを抜けて失敗を返す
                    return None, None
            else:
                # 429以外の予期せぬエラー
                print(answer_text)
                print('answer_text')
                print(f"\nストリームの処理中に予期せぬエラーが発生しました ({log_prefix}): {e}", file=sys.stderr)
                # リトライせずに失敗を返す
                if attempt < MAX_RETRIES - 1:
                    # 待機時間を指数関数的に増やす (10秒, 20秒, 40秒...)
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(f"\n警告 ({log_prefix}): 予期せぬエラー対応。{delay}秒待機して再試行します... (試行 {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(delay)
                    # 次のループでリトライを試みる
                    continue
                else:
                    print(f"\nエラー ({log_prefix}): 予期せぬエラー対応よる最大リトライ回数({MAX_RETRIES}回)を超えました。", file=sys.stderr)
                    # ループを抜けて失敗を返す
                    return None, None
                # --- ▲▲▲ 例外処理を修正 ▲▲▲ ---
            
    # forループがすべて失敗した場合
    return None, None

# ★★★ 引数に loop と api_key_manager を追加 ★★★
def _blocking_call_to_gemini(
    loop: asyncio.AbstractEventLoop,
    api_key_manager, # ApiKeyManagerのインスタンス
    api_key: str, 
    full_contents: str, 
    query_for_log_base: str, 
    parallel_count: int, 
    task_id: int
):
    # Geminiを呼び出すメイン関数　リトライ機能付き
    query_for_log = query_for_log_base[6:26] + '...' if len(query_for_log_base) > 50 else query_for_log_base
    MAX_RETRIES = 3
    INITIAL_DELAY = 10

    # ★★★ ループ内で変化する可能性があるため、ループの外で初期化 ★★★
    current_api_key = api_key

    for attempt in range(MAX_RETRIES):
        # ★★★ 常に最新のキー情報でログを出力するため、log_prefixはループ内で定義 ★★★
        log_prefix = f"Task{task_id} API {current_api_key[-6:]} {query_for_log}"

        try:
            if not current_api_key:
                print(f"\nエラー ({log_prefix}): 有効なAPIキーがありません。", file=sys.stderr)
                return None, None

            # ★★★ 現在のキー(current_api_key)でクライアントを初期化 ★★★
            client = genai.Client(api_key=current_api_key)
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=-1, include_thoughts=True)
            )
            if attempt == 0:
                print(f"({log_prefix}) AIが思考を開始します...", file=sys.stderr)
            
            # (...既存のストリーム処理部分は変更なし...)
            api_call_start_time = time.time()
            stream = client.models.generate_content_stream(model=MODEL_NAME, contents=full_contents, config=config)
            thinking_text, answer_text = "", ""
            is_first_thought = True
            for chunk in stream:
                if not chunk.candidates: continue
                if hasattr(chunk.candidates[0].content, 'parts'): parts = chunk.candidates[0].content.parts
                else: parts = []
                for part in parts:
                    if not hasattr(part, 'text') or not part.text: continue
                    is_thought = hasattr(part, 'thought') and part.thought
                    if is_thought and parallel_count <= 1:
                        if is_first_thought :
                            print(f"\n--- AIの思考プロセス ({log_prefix}) ---", file=sys.stderr)
                            is_first_thought = False
                        print(part.text, end="", flush=True, file=sys.stderr)
                        thinking_text += part.text
                    else:
                        answer_text += part.text
            if not is_first_thought and parallel_count <= 1:
                print("", file=sys.stderr)

            # ★★★ 成功した場合は、結果を返してループを抜ける ★★★
            return thinking_text, answer_text
            
        except Exception as e:
            error_message = str(e).lower()
            if "429" in error_message and "resource_exhausted" in error_message:
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(f"\n警告 ({log_prefix}): API Limit! {delay}秒待機+再試行({attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    
                    # --- ▼▼▼ リトライ用の新しいキーを取得する処理 ▼▼▼ ---
                    try:
                        # 非同期の get_next_key を別スレッドから安全に呼び出す
                        future = asyncio.run_coroutine_threadsafe(api_key_manager.get_next_key(), loop)
                        # 結果を同期的に待つ (タイムアウトを5秒に設定)
                        new_key = future.result(timeout=5)
                        
                        if new_key and new_key != current_api_key:
                            current_api_key = new_key  # ★キーを更新
                            #print(f"情報 ({log_prefix}): APIキーを新しいものに変更して再試行します。")
                        else:
                            print(f"警告 ({log_prefix}): 新しいキーを取得できませんでした。同じキーで再試行します。")
                    except Exception as key_e:
                        print(f"警告 ({log_prefix}): リトライ用のキー取得中にエラー: {key_e}。同じキーで再試行します。")
                    # --- ▲▲▲ ここまで ▲▲▲ ---

                    time.sleep(delay)
                    continue # ループの先頭に戻り、新しいキーでリトライ
                else:
                    print(f"\nエラー ({log_prefix}): APIレートリミットによる最大リトライ回数({MAX_RETRIES}回)を超えました。", file=sys.stderr)
                    return None, None
            else:
                # 429以外の予期せぬエラー
                print(answer_text)
                print('answer_text')
                print(f"\nストリームの処理中に予期せぬエラーが発生しました ({log_prefix}): {e}", file=sys.stderr)
                # リトライせずに失敗を返す
                if attempt < MAX_RETRIES - 1:
                    # 待機時間を指数関数的に増やす (10秒, 20秒, 40秒...)
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(f"\n警告 ({log_prefix}): 予期せぬエラー対応。{delay}秒待機して再試行します... (試行 {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(delay)
                    # 次のループでリトライを試みる
                    continue
                else:
                    print(f"\nエラー ({log_prefix}): 予期せぬエラー対応よる最大リトライ回数({MAX_RETRIES}回)を超えました。", file=sys.stderr)
                    # ループを抜けて失敗を返す
                    return None, None
                # --- ▲▲▲ 例外処理を修正 ▲▲▲ ---
            
            
    # forループがすべて失敗した場合 (リトライ上限に達した場合)
    return None, None

def _blocking_count_tokens(api_key: str, model: str, contents: str) -> types.CountTokensResponse | None:
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        return client.models.count_tokens(model=model, contents=contents)
    except Exception as e:
        print(f"\nトークン計算中にエラーが発生しました ({contents[:30]}...): {e}", file=sys.stderr)
        return None

async def process_query_task(query: str, semaphore: asyncio.Semaphore, output_filename: str, parallel_count: int, task_id: int):
    # プロンプト、ファイル出力など
    # 単独処理の場合は、トークン数を計算する。
    # 並列処理の場合は、トークン数を計算しない。（APIコールを減らして、並列度を高める為）

    query_for_log = query[6:26] + '...' if len(query) > 50 else query
    log_prefix = f"Task {task_id}: {query_for_log}"

    MAX_RETRIES = 3
    INITIAL_DELAY = 10

    async with semaphore:
        start_time = time.time()
        
        prompt_template="""
# 調査対象企業
- {company_name}
# 上記の企業について、ルールに従い、以下のJSON形式で出力してください。
# 厳守すべきルール
0. 入力される企業情報は複数あります。企業情報１件につき、１件のJSONオブジェクトで出力してください。
   **もし入力に対して複数の企業情報が見つかった場合は、それぞれのJSONオブジェクトを個別の ```json ... ``` ブロックで囲って出力してください。**
1. 欠損情報の扱い:調査しても情報が見つからない場合は、項目の値を `不明` としてください。
2. 以下の３つの主要調査項目の全項目が見つからなければ、即座に調査を中止し、下記の「調査中断レポート」を出力してください。
   主要調査項目（３項目）：`officialUrl`, `email`, `tel`
3. 上記2.に抵触しなかった場合のみ、収集した情報を下記の「通常調査レポート」の形式で出力してください。
4. # **「通常調査レポート」または「調査中断レポート」のJSONを、必ず1つ以上出力してください。それ以外のテキストは出力しないでください。**

# 出力形式 (JSON)
# 調査中断レポート
```json
{{
  "status": "terminated",
  "error": "Required information could not be found.",
  "message": "主要調査３項目全てが不明だったため、調査を中断しました。",
  "targetCompany": "{company_name}"
}}```
# 通常調査レポート
```json
{{
  "status": "success",
  "data": {{
    "companyName": "企業の正式名称（string）",
    "companyStatus": "企業の現在の状況（例：活動中, 閉鎖, 不明）（string）",
    "address": "本社の所在地（string）",
    "officialUrl": "公式サイトのURL（string）",
    "industry": "主要な業種（string）",
    "email": "メールアドレス（string）# 探し方:HTMLの<a>タグ mailto:を探すこと。",
    "tel": "代表電話番号（string）",
    "fax": "代表FAX番号（string）",
    "capital": "資本金（string）",
    "founded": "設立年月（string）",
    "businessSummary": "事業内容の簡潔な要約（string）",
    "strengths": "企業の強みや特徴の簡潔な要約（string）"
  }}
}}```
"""
        for attempt in range(MAX_RETRIES):

            full_contents = prompt_template.format(company_name=query)

            # トークン数の初期化
            input_tokens, thinking_tokens, answer_tokens = 0, 0, 0


            # メインのAPIコール　絶対に必要な処理
            main_call_key = await api_key_manager.get_next_key()
            if not main_call_key:
                return None
            
            loop = asyncio.get_running_loop()

            start = time.time()
            thinking_text, answer_text = await asyncio.to_thread(
                #_blocking_call_to_gemini, main_call_key, full_contents, query, parallel_count, task_id
                _blocking_call_to_gemini, loop, api_key_manager, main_call_key, full_contents, query, parallel_count, task_id
            )

            if thinking_text is None and answer_text is None:
                return None
            elapsed = time.time() - start

            # input_tokensの計算　並列実行時は不要
            if parallel_count <= 1:
                input_key = await api_key_manager.get_next_key()
                if input_key:
                    input_token_response = await asyncio.to_thread(
                        _blocking_count_tokens, input_key, MODEL_NAME, full_contents
                    )
                    if input_token_response: 
                        input_tokens = input_token_response.total_tokens

            # thinking_tokensの計算　並列実行時は不要
            if parallel_count <= 1:
                thinking_key = await api_key_manager.get_next_key()
                if thinking_text:
                    if thinking_key:
                        thinking_token_response = await asyncio.to_thread(
                            _blocking_count_tokens, thinking_key, MODEL_NAME, thinking_text
                        )
                        if thinking_token_response: 
                            thinking_tokens = thinking_token_response.total_tokens

            # answer_tokensの計算　並列実行時は不要
            if parallel_count <= 1:
                answer_key = await api_key_manager.get_next_key()
                if answer_text:
                    if answer_key:
                        answer_token_response = await asyncio.to_thread(
                            _blocking_count_tokens, answer_key, MODEL_NAME, answer_text
                        )
                        if answer_token_response: 
                            answer_tokens = answer_token_response.total_tokens

            end_time = time.time()
            time_tokens_info = {
                "time": round(end_time - start_time, 2),
                "input_tokens": input_tokens,
                "thinking_tokens": thinking_tokens,
                "answer_tokens": answer_tokens,
                "total_tokens": input_tokens + thinking_tokens + answer_tokens
            }

            # 複数のJSONオブジェクトを格納するためのリスト
            final_outputs = []
            # AIの応答から、マークダウンのJSONブロックを全て抽出する
            json_matches = re.findall(r"```json(.*?)```", answer_text, re.DOTALL)

            if not json_matches:
                # 1件もJSONブロックが見つからなかった場合
                #print(f"エラー ({log_prefix}): API応答から有効なJSONブロックを抽出できませんでした。", file=sys.stderr)
                #print(f"--- 生の応答 ---\n{answer_text}\n----------------", file=sys.stderr)
                #return None # タスク失敗

                if attempt < MAX_RETRIES - 1:
                    # 待機時間を指数関数的に増やす (10秒, 20秒, 40秒...)
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(f"\n警告 ({log_prefix}): JSON抽出全部失敗。{delay}秒待機=>再試行... (試行 {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(delay)
                    # 次のループでリトライを試みる
                    continue
                else:
                    print(f"\nエラー ({log_prefix}): JSON抽出全部失敗。最大リトライ回数({MAX_RETRIES}回)を超えました。", file=sys.stderr)
                    # ループを抜けて失敗を返す
                    return None# タスク失敗


            # 抽出した各JSON文字列を個別にパースする
            for json_str in json_matches:
                try:
                    # 文字列をJSONオブジェクトにパース
                    parsed_json = json.loads(json_str.strip())
                    # 処理時間などの共通情報を付与
                    parsed_json["time_tokens"] = time_tokens_info
                    # 結果リストに追加
                    final_outputs.append(parsed_json)
                except json.JSONDecodeError as e:
                    # パースに失敗したJSONブロックは警告を出してスキップ
                    print(f"警告 ({log_prefix}): JSONパース一部失敗。スキップします。エラー: {e}", file=sys.stderr)
                    #print(f"--- パース失敗文字列 ---\n{json_str.strip()}\n--------------------", file=sys.stderr)



            # JSONパースが入力件数未満ならリトライ
            if len(final_outputs) < LINES_PER_QUERY:
                #print(f"エラー ({log_prefix}): 抽出されたJSONブロックはありましたが、全てパースに失敗しました。", file=sys.stderr)
                #return None
                if attempt < MAX_RETRIES - 1:
                    # 待機時間を指数関数的に増やす (10秒, 20秒, 40秒...)
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(f"\n警告 ({log_prefix}): JSON件数不足。{len(final_outputs)}/{LINES_PER_QUERY} {delay}秒待機=>再試行... (試行 {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(delay)
                    # 次のループでリトライを試みる
                    continue
                else:
                    print(f"\nエラー ({log_prefix}): JSON件数不足。最大リトライ回数({MAX_RETRIES}回)を超えました。", file=sys.stderr)
                    # ループを抜けて失敗を返す
                    return None# タスク失敗


            # --- 1件ごとのファイル追記処理 ---
            async with file_write_lock:
                all_data = []
                try:
                    if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                        with open(output_filename, 'r', encoding='utf-8') as f:
                            all_data = json.load(f)
                            if not isinstance(all_data, list): all_data = []
                except (json.JSONDecodeError, FileNotFoundError): pass
                
                # ★★★ 複数の結果をリストに一括で追加する ★★★
                all_data.extend(final_outputs)
                
                try:
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        json.dump(all_data, f, indent=2, ensure_ascii=False)
                    # ログメッセージを、処理したJSONの件数を表示するように変更
                    print(f"({log_prefix}) 処理完了({elapsed:.2f}s) {len(final_outputs)}件のJSONを {output_filename} に追記済 ", file=sys.stderr)
                except IOError as e:
                    print(f"エラー ({log_prefix}): ファイル書き込みに失敗: {e}", file=sys.stderr)

            return final_outputs

def make_log_dir():
    # フォルダが存在しないかチェック
    if not os.path.exists(LOG_DIR):
        # 存在しない場合のみ、フォルダを作成
        os.makedirs(LOG_DIR)
        print(f"フォルダ '{LOG_DIR}' を作成しました。")
    else:
        # 既に存在する場合
        print(f"フォルダ '{LOG_DIR}' は既に存在します。")

async def main():
    parser = argparse.ArgumentParser(description="企業情報を検索し、結果をJSONで出力するアプリ")
    parser.add_argument("query", nargs='?', default=None, help="検索対象の企業名と住所（単一実行モード時）")
    parser.add_argument("--prompt-file", help="複数クエリが記述されたテキストファイルのパス（並列実行モード時）")
    parser.add_argument("--parallel", type=int, default=5, help="最大並列実行数（デフォルト: 5）")
    args = parser.parse_args()
    
    make_log_dir()

    output_filename = f"{LOG_DIR}/output.json"

    
    #try:
    #    if os.path.exists(output_filename):
    #        os.remove(output_filename)
    #        print(f"INFO: 既存の '{output_filename}' をクリアしました。", file=sys.stderr)
    #except OSError as e:
    #    print(f"警告: '{output_filename}' のクリアに失敗しました: {e}", file=sys.stderr)
    
    is_parallel_mode = bool(args.prompt_file)
    
    if is_parallel_mode:
        print(f"INFO: 並列実行モードで起動します (最大{args.parallel}並列)。", file=sys.stderr)
        try:
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                # --- ▼▼▼ ここから修正 ▼▼▼ ---
                
                # スクリプト冒頭で定義した設定値を参照する
                if LINES_PER_QUERY < 1:
                    print(f"エラー: 設定変数 LINES_PER_QUERY ({LINES_PER_QUERY}) は1以上の整数である必要があります。", file=sys.stderr)
                    sys.exit(1)

                # まず全ての行を読み込み、空行は除外する
                lines = [line.strip() for line in f if line.strip()]
                
                # 行数が LINES_PER_QUERY の倍数でない場合は警告
                if len(lines) % LINES_PER_QUERY != 0:
                    extra_lines = len(lines) % LINES_PER_QUERY
                    print(f"警告: 入力ファイルの行数が {LINES_PER_QUERY} の倍数ではありません。最後の {extra_lines} 行は無視されます。", file=sys.stderr)

                # LINES_PER_QUERY で指定された行数ずつグループ化する
                queries = []
                # 作成できるクエリの総数を計算
                num_queries = len(lines) // LINES_PER_QUERY
                for i in range(num_queries):
                    start_index = i * LINES_PER_QUERY
                    end_index = start_index + LINES_PER_QUERY
                    # スライスした行のリストを改行で連結
                    query_block = "\n".join(lines[start_index:end_index])
                    queries.append(query_block)

                # --- ▲▲▲ ここまで修正 ▲▲▲ ---
                
            if not queries:
                print(f"エラー: プロンプトファイル '{args.prompt_file}' が空です。", file=sys.stderr)
                sys.exit(1)
            print(f"INFO: {len(queries)}件のクエリをファイルから読み込みました。", file=sys.stderr)
        except FileNotFoundError:
            print(f"エラー: プロンプトファイルが見つかりません: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
        
        semaphore = asyncio.Semaphore(args.parallel)
        # --- `args.parallel` の値をタスク関数に渡す ---        
        tasks = [process_query_task(q, semaphore, output_filename, args.parallel, i + 1) for i, q in enumerate(queries)]
        results = await asyncio.gather(*tasks)
        
        successful_results = [res for res in results if res is not None]
        print(f"\n--- 全タスク完了: {len(successful_results)} / {len(queries)} 件の処理に成功 ---", file=sys.stderr)
        #print(json.dumps(successful_results, indent=2, ensure_ascii=False))
        split_json_by_status(output_filename)
        
    else: # 単一実行モード
        if not args.query:
            parser.error("単一実行モードでは 'query' 引数が必要です。")
        print("INFO: 単一実行モードで起動します。", file=sys.stderr)
        semaphore = asyncio.Semaphore(1)
        # --- 単一実行なので並列数は 1 を渡す ---
        result = await process_query_task(args.query, semaphore, output_filename, 1, 1)
        if result:
            print(json.dumps([result], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    exit_code = 0
    start_time1 = time.time()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nプログラムが中断されました。", file=sys.stderr)
        exit_code = 130
    except Exception as e:
        print(f"予期せぬ致命的なエラーが発生しました: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        end_time1 = time.time()
        print(f"time: {round(end_time1 - start_time1, 2)} s")
        api_key_manager.save_session()
        print("[INFO] アプリケーション終了に伴いセッションを保存しました。", file=sys.stderr)
        sys.exit(0)