import asyncio
import json
import sys
import os
import re
import subprocess
from typing import List, Dict, Any

# --- 設定項目 ---
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

TARGET_SCRIPT = os.path.join(BASE_DIR, "gemini_search_app_new_sdk_thoughts.py")
INPUT_FILE = os.path.join(BASE_DIR, "input_data_sumple.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "results.json")

BATCH_SIZE = 5 #１プロセスで並列処理可能な会社数
MAX_CONCURRENT_TASKS = 5 # 同時に実行する最大プロセス数


def sync_run_gemini_batch(batch_id: int, batch_data: List[str]) -> List[Dict[str, Any]] | None:
    print(f"[SYNC-RUNNER {batch_id}] 同期処理関数を開始します。")
    
    try:
        query_content = "\n".join(batch_data)
        command = [sys.executable, TARGET_SCRIPT]
        
        print(f"[SYNC-RUNNER {batch_id}] サブプロセスを呼び出します...")

        # <<< 文字化け対策の最重要変更点 >>>
        # サブプロセスに渡す環境変数をコピーし、PYTHONIOENCODINGをutf-8に設定
        process_env = os.environ.copy()
        process_env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(
            command,
            input=query_content,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            env=process_env  # <<< 変更点: 環境変数を渡す
        )

        print(f"[SYNC-RUNNER {batch_id}] サブプロセス完了。リターンコード: {result.returncode}")

        if result.returncode != 0:
            print(f"[SYNC-RUNNER {batch_id}] エラー終了を検出。", file=sys.stderr)
            if result.stderr:
                print(f"--- [SYNC-RUNNER {batch_id}] のエラー出力 ---\n{result.stderr}\n---------------------------------", file=sys.stderr)
            return None

        output_str = result.stdout
        print(f"[SYNC-RUNNER {batch_id}] 正常終了。出力解析開始。")
        
        try:
            match = re.search(r"```json\s*([\s\S]*?)\s*```", output_str, re.DOTALL)
            if not match:
                raise ValueError("出力から '```json' で囲まれたブロックが見つかりません。")

            json_str = match.group(1)
            
            # <<< JSON解析の堅牢化 >>>
            result_json = json.loads(json_str, strict=False)
            
            if result_json.get("status") == "success" and "data" in result_json:
                data_list = result_json["data"]
                if isinstance(data_list, list):
                    print(f"[SYNC-RUNNER {batch_id}] 正常なデータ {len(data_list)}件 を取得しました。")
                    return data_list
                else:
                    raise TypeError("レスポンスの'data'フィールドがリストではありません。")
            else:
                error_msg = result_json.get("message", "不明なレスポンスエラー")
                raise ValueError(f"レスポンスにエラーが含まれます: {error_msg}")

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"[SYNC-RUNNER {batch_id}] エラー: 出力解析に失敗。詳細: {e}", file=sys.stderr)
            print(f"--- [SYNC-RUNNER {batch_id}] の標準出力（先頭1000文字） ---\n{output_str[:1000]}\n---------------------------------", file=sys.stderr)
            return None
    
    except Exception as e:
        print(f"[SYNC-RUNNER {batch_id}] 予期せぬ致命的エラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

async def run_batch_in_executor(semaphore: asyncio.Semaphore, loop: asyncio.AbstractEventLoop, batch_id: int, batch_data: List[str]):
    async with semaphore:
        print(f"[ASYNC-WRAPPER {batch_id}] セマフォ取得。スレッドプールで同期関数を実行...")
        result = await loop.run_in_executor(
            None, sync_run_gemini_batch, batch_id, batch_data
        )
        print(f"[ASYNC-WRAPPER {batch_id}] スレッドプール処理完了。")
        return result

async def main_orchestrator():
    print("--- 企業情報一括調査アプリケーション開始 ---")
    
    if not os.path.exists(TARGET_SCRIPT) or not os.path.exists(INPUT_FILE):
        print("致命的エラー: 必須ファイルが見つかりません。", file=sys.stderr)
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if not lines:
        print("入力ファイルが空です。")
        return

    total_lines = len(lines)
    num_batches = (total_lines + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"合計 {total_lines} 件のデータを読み込み、{BATCH_SIZE}件ずつの {num_batches} バッチを作成。")

    batches = [lines[i:i + BATCH_SIZE] for i in range(0, total_lines, BATCH_SIZE)]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    loop = asyncio.get_running_loop()
    tasks = [asyncio.create_task(run_batch_in_executor(semaphore, loop, i + 1, batch)) for i, batch in enumerate(batches)]
    
    print(f"\n最大{MAX_CONCURRENT_TASKS}件の並列処理を開始します...")
    batch_results = await asyncio.gather(*tasks)

    print("\n--- 全バッチ処理完了。結果を統合しています... ---")
    final_data = [item for result in batch_results if result for item in result]
    success_count = sum(1 for r in batch_results if r is not None)
    failed_count = len(batches) - success_count

    print(f"処理結果: 成功 {success_count}バッチ / 失敗 {failed_count}バッチ")
    print(f"合計 {len(final_data)} 件の企業データを正常に取得。")
    
    if final_data:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        print(f"結果を '{OUTPUT_FILE}' に保存しました。")
    else:
        print("正常に取得できたデータがなかったため、出力ファイルは作成されませんでした。")
    
    print("\n--- アプリケーション終了 ---")

if __name__ == "__main__":
    try:
        asyncio.run(main_orchestrator())
    except KeyboardInterrupt:
        print("\nプログラムが中断されました。")
    except Exception as e:
        print(f"予期せぬ致命的なエラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()