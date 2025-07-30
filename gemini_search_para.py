# gemini_search_parallel.py (1件ごとのリアルタイム追記版)

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

# --- ▼▼▼ リトライ機能のために、特定のエラーを捕捉するライブラリをインポート ▼▼▼ ---
from google.api_core import exceptions

from api_key_manager import api_key_manager

load_dotenv()

if 'GOOGLE_API_KEY' in os.environ:
    del os.environ['GOOGLE_API_KEY']
    
# --- ▼▼▼ 複数タスクからのファイル書き込みを保護するためのロックを作成 ▼▼▼ ---
file_write_lock = asyncio.Lock()


# (この関数は変更なし)
def _blocking_call_to_gemini(api_key: str, full_contents: str, query_for_log: str):
    MAX_RETRIES = 3
    INITIAL_DELAY = 2
    for attempt in range(MAX_RETRIES):
        try:
            if not api_key:
                print(f"\nエラー ({query_for_log}): 有効なAPIキーがありません。", file=sys.stderr)
                return None, None
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=-1, include_thoughts=True)
            )
            if attempt == 0:
                print(f"({query_for_log}) AIが思考を開始します...", file=sys.stderr)
            api_call_start_time = time.time() 
            stream = client.models.generate_content_stream(model='gemini-2.5-flash', contents=full_contents, config=config)
            thinking_text, answer_text = "", ""
            for chunk in stream:
                if not chunk.candidates: continue
                # --- SDKのバージョン差異に対応 ---
                if hasattr(chunk.candidates[0].content, 'parts'):
                    parts = chunk.candidates[0].content.parts
                else:
                    parts = [] # Fallback for older versions or different structures
                for part in parts:
                    if not hasattr(part, 'text') or not part.text: continue
                    if hasattr(part, 'thought') and part.thought:
                        thinking_text += part.text
                    else:
                        answer_text += part.text
            elapsed = time.time() - api_call_start_time
            print(f"({query_for_log}) 全ストリーム受信完了 ({elapsed:.2f}s)。", file=sys.stderr)
            return thinking_text, answer_text
        except exceptions.ResourceExhausted as e:
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_DELAY ** (attempt + 1)
                print(f"警告 ({query_for_log}): APIレートリミットです。{delay}秒待機して再試行します... (試行 {attempt + 2}/{MAX_RETRIES})", file=sys.stderr)
                time.sleep(delay)
            else:
                print(f"エラー ({query_for_log}): 最大リトライ回数({MAX_RETRIES}回)を超えました。メインAPIコール失敗。", file=sys.stderr)
                return None, None
        except Exception as e:
            print(f"\nストリームの処理中に予期せぬエラーが発生しました ({query_for_log}): {e}", file=sys.stderr)
            return None, None
    return None, None

# (この関数は変更なし)
def _blocking_count_tokens(api_key: str, model: str, contents: str) -> types.CountTokensResponse | None:
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        return client.models.count_tokens(model=model, contents=contents)
    except Exception as e:
        print(f"\nトークン計算中にエラーが発生しました ({contents[:30]}...): {e}", file=sys.stderr)
        return None

# --- ▼▼▼ この関数が、ファイルへの書き込みまで担当するように修正 ▼▼▼ ---
async def process_query_and_write_to_file(query: str, semaphore: asyncio.Semaphore, output_filename: str):
    """
    単一クエリを処理し、完了後、即座に結果をJSONファイルに追記する。
    """
    async with semaphore:
        start_time = time.time()
        query_for_log = query[25:50] + '...' if len(query) > 40 else query

        prompt_template="""
# 調査対象企業
- {company_name}
# 上記の企業について、ルールに従い、以下のJSON形式で出力してください。
# 厳守すべきルール
1. 入力された、会社名　住所の情報から、出力内容を特定してください。
2. ファクトチェックの徹底:名称と住所を基に、正しい業種を再検証してください。
3. 欠損情報の扱い:調査しても情報が見つからない場合は、項目の値を `不明` としてください。
4. 以下の４つの主要調査項目のうち、２項目が見つからなければ、即座に調査を中止し、下記の「調査中断レポート」を出力してください。
   主要調査項目（４項目）：`officialUrl`, `industry`, `email`, `tel`
5. 上記4.に抵触しなかった場合のみ、収集した情報を下記の「通常調査レポート」の形式で出力してください。
# 出力形式 (JSON)
# 調査中断レポート
```json
{{
  "status": "terminated",
  "error": "Required information could not be found.",
  "message": "主要調査項目のうち2項目以上が不明だったため、調査を中断しました。",
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
    "email": "メールアドレス（string）",
    "tel": "代表電話番号（string）",
    "fax": "代表FAX番号（string）",
    "capital": "資本金（string）",
    "founded": "設立年月（string）",
    "businessSummary": "事業内容の簡潔な要約（string）",
    "strengths": "企業の強みや特徴（string）"
  }}
}}```
"""

        full_contents = prompt_template.format(company_name=query)

        input_tokens, thinking_tokens, answer_tokens = 0, 0, 0

        input_key = await api_key_manager.get_next_key()
        if input_key:
            input_token_response = await asyncio.to_thread(
                _blocking_count_tokens, input_key, 'gemini-2.5-flash', full_contents
            )
            if input_token_response: input_tokens = input_token_response.total_tokens

        main_call_key = await api_key_manager.get_next_key()
        if not main_call_key:
            print(f"エラー ({query_for_log}): メイン処理用のAPIキーを取得できませんでした。", file=sys.stderr)
            return None
            
        thinking_text, answer_text = await asyncio.to_thread(
            _blocking_call_to_gemini, main_call_key, full_contents, query_for_log
        )

        if thinking_text is None and answer_text is None:
            print(f"エラー ({query_for_log}): Geminiからの応答取得に失敗しました。", file=sys.stderr)
            return None

        if thinking_text:
            thinking_key = await api_key_manager.get_next_key()
            if thinking_key:
                thinking_token_response = await asyncio.to_thread(
                    _blocking_count_tokens, thinking_key, 'gemini-2.5-flash', thinking_text
                )
                if thinking_token_response: thinking_tokens = thinking_token_response.total_tokens

        if answer_text:
            answer_key = await api_key_manager.get_next_key()
            if answer_key:
                answer_token_response = await asyncio.to_thread(
                    _blocking_count_tokens, answer_key, 'gemini-2.5-flash', answer_text
                )
                if answer_token_response: answer_tokens = answer_token_response.total_tokens

        end_time = time.time()
        time_tokens_info = {
            "time": round(end_time - start_time, 2),
            "input_tokens": input_tokens,
            "thinking_tokens": thinking_tokens,
            "answer_tokens": answer_tokens,
            "total_tokens": input_tokens + thinking_tokens + answer_tokens
        }

        final_output = {}
        try:
            # --- ▼▼▼ ここが唯一の修正箇所です ▼▼▼ ---
            
            json_str = None
            # 1. ```json ... ``` というブロックを、説明文ごと全文の中から探す (re.DOTALLで改行も対象に)
            match = re.search(r"```json(.*)```", answer_text, re.DOTALL)
            
            if match:
                # 2. ブロックが見つかった場合、その中身だけを抽出する (group(1))
                json_str = match.group(1).strip()
            else:
                # 3. ブロックが見つからない場合（正常系）、応答全体がJSONだと仮定する
                json_str = answer_text.strip()
            
            if not json_str:
                raise json.JSONDecodeError("抽出後のJSON文字列が空です", "", 0)

            final_output = json.loads(json_str)

        except json.JSONDecodeError as e:
            print(json_str)
            print(f"NG_json_str") # デバッグ用
            print(f"エラー ({query_for_log}): API応答のJSON解析に失敗しました: {e}", file=sys.stderr)
            final_output = {
                "status": "error",
                "error": "Failed to parse API response",
                "message": f"APIからの応答をJSONとして解析できませんでした。 raw_response: {answer_text}",
                "raw_response": answer_text
            }
        
        # --- ▲▲▲ ここまでが唯一の修正箇所です ▲▲▲ ---        
        final_output["time_tokens"] = time_tokens_info
        # --- ▼▼▼ ここからがファイル追記処理 ▼▼▼ ---

        async with file_write_lock: # ロックを取得して、ファイルアクセスを排他制御
            all_data = []
            try:
                # 既存のファイルを読み込む
                if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                    with open(output_filename, 'r', encoding='utf-8') as f:
                        all_data = json.load(f)
                        if not isinstance(all_data, list):
                            all_data = []
            except (json.JSONDecodeError, FileNotFoundError):
                pass
            
            # 今回の結果を追加
            all_data.append(final_output)
            
            # ファイルに書き戻す
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, indent=2, ensure_ascii=False)
                print(f"({query_for_log}) 結果を {output_filename} に追記しました。", file=sys.stderr)
            except IOError as e:
                print(f"エラー ({query_for_log}): ファイル書き込みに失敗: {e}", file=sys.stderr)
        
        # 標準出力用に結果を返す
        return final_output

async def main():
    parser = argparse.ArgumentParser(description="企業情報を検索し、結果をJSONで出力するアプリ")
    parser.add_argument("query", nargs='?', default=None, help="検索対象の企業名と住所（単一実行モード時）")
    parser.add_argument("--prompt-file", help="複数クエリが記述されたテキストファイルのパス（並列実行モード時）")
    parser.add_argument("--parallel", type=int, default=5, help="最大並列実行数（デフォルト: 5）")
    args = parser.parse_args()

    output_filename = "output.json"
    is_parallel_mode = bool(args.prompt_file)

    if is_parallel_mode:
        print(f"INFO: 並列実行モードで起動します (最大{args.parallel}並列)。", file=sys.stderr)
        try:
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip()]
            if not queries:
                print(f"エラー: プロンプトファイル '{args.prompt_file}' が空です。", file=sys.stderr)
                sys.exit(1)
            print(f"INFO: {len(queries)}件のクエリをファイルから読み込みました。", file=sys.stderr)
        except FileNotFoundError:
            print(f"エラー: プロンプトファイルが見つかりません: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
        
        semaphore = asyncio.Semaphore(args.parallel)
        # 新しいタスク関数を呼び出す
        tasks = [process_query_and_write_to_file(q, semaphore, output_filename) for q in queries]
        # 全てのタスクの完了を待つ
        results = await asyncio.gather(*tasks)
        
        successful_results = [res for res in results if res is not None]
        print(f"\n--- 全タスク完了: {len(successful_results)} / {len(queries)} 件の処理に成功 ---", file=sys.stderr)
        
        # 最後に、標準出力にだけ全結果をまとめて表示する
        print(json.dumps(successful_results, indent=2, ensure_ascii=False))
        
    else: # (単一実行モードも同様に修正)
        if not args.query:
            parser.error("単一実行モードでは 'query' 引数が必要です。")
        print("INFO: 単一実行モードで起動します。", file=sys.stderr)
        semaphore = asyncio.Semaphore(1)
        # 新しいタスク関数を呼び出す
        result = await process_query_and_write_to_file(args.query, semaphore, output_filename)
        if result:
            # 標準出力に結果を表示
            print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    exit_code = 0
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nプログラムが中断されました。", file=sys.stderr)
        exit_code = 130
    except Exception as e:
        print(f"予期せぬ致命的なエラーが発生しました: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        api_key_manager.save_session()
        print("[INFO] アプリケーション終了に伴いセッションを保存しました。", file=sys.stderr)
        sys.exit(exit_code)