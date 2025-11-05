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

# ワーカーを単一企業処理用のスクリプトに変更
TARGET_SCRIPT = os.path.join(BASE_DIR, "gemini_search_app_new_sdk.py")
INPUT_FILE = os.path.join(BASE_DIR, "input_data_sumple.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "results.json")

# BATCH_SIZEは使わなくなるが、並列実行数の上限としてMAX_CONCURRENT_TASKSは残す
MAX_CONCURRENT_TASKS = 10 # 同時に実行する最大プロセス数

def sync_run_gemini_for_company(company_id: int, company_name: str) -> Dict[str, Any] | None:
    """ 1社だけを処理するワーカー関数 """
    print(f"[SYNC-RUNNER {company_id}] 会社名: '{company_name[:30]}...' の処理を開始...")
    
    try:
        # 会社名をコマンドライン引数として渡す
        command = [sys.executable, TARGET_SCRIPT, company_name]
        
        process_env = os.environ.copy()
        process_env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            env=process_env
        )

        if result.returncode != 0:
            print(f"[SYNC-RUNNER {company_id}] エラー終了を検出。", file=sys.stderr)
            if result.stderr:
                print(f"--- [SYNC-RUNNER {company_id}] のエラー出力 ---\n{result.stderr}\n---------------------------------", file=sys.stderr)
            return None

        output_str = result.stdout
        
        try:
            match = re.search(r"```json\s*([\s\S]*?)\s*```", output_str, re.DOTALL)
            if not match:
                # JSONが見つからない場合、ターミネーションレポートかもしれないのでチェック
                if '"status": "terminated"' in output_str:
                     print(f"[SYNC-RUNNER {company_id}] 調査中断レポートを検出しました。")
                     # 中断レポート自体をJSONとしてパース試行
                     match_term = re.search(r"{\s*\"status\":\s*\"terminated\"[\s\S]*}", output_str, re.DOTALL)
                     if match_term:
                         json_str = match_term.group(0)
                     else:
                        raise ValueError("調査中断レポートのJSON形式が不正です。")
                else:
                    raise ValueError("出力から '```json' で囲まれたブロックが見つかりません。")
            else:
                 json_str = match.group(1)

            result_json = json.loads(json_str, strict=False)
            
            # 成功時も中断時も、dataフィールドを返すように統一する
            if result_json.get("status") == "success" and "data" in result_json:
                print(f"[SYNC-RUNNER {company_id}] 正常なデータを取得しました。")
                return result_json["data"]
            elif result_json.get("status") == "terminated":
                 # 中断した場合でも、どの会社か分かるように情報を付加して返す
                 return {
                     "companyName": result_json.get("targetCompany", company_name),
                     "companyStatus": "調査中断",
                     "error": result_json.get("message", "N/A")
                 }
            else:
                error_msg = result_json.get("message", "不明なレスポンスエラー")
                raise ValueError(f"レスポンスにエラーが含まれます: {error_msg}")

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"[SYNC-RUNNER {company_id}] エラー: 出力解析に失敗。詳細: {e}", file=sys.stderr)
            print(f"--- [SYNC-RUNNER {company_id}] の標準出力（先頭1000文字） ---\n{output_str[:1000]}\n---------------------------------", file=sys.stderr)
            return None
    
    except Exception as e:
        print(f"[SYNC-RUNNER {company_id}] 予期せぬ致命的エラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

async def run_company_in_executor(semaphore: asyncio.Semaphore, loop: asyncio.AbstractEventLoop, company_id: int, company_name: str):
    async with semaphore:
        print(f"[ASYNC-WRAPPER {company_id}] セマフォ取得。'{company_name[:30]}...' を処理します。")
        result = await loop.run_in_executor(
            None, sync_run_gemini_for_company, company_id, company_name
        )
        print(f"[ASYNC-WRAPPER {company_id}] 処理完了。")
        return result

async def main_orchestrator():
    print("--- 企業情報【並列】調査アプリケーション開始 ---")
    
    if not os.path.exists(TARGET_SCRIPT) or not os.path.exists(INPUT_FILE):
        print("致命的エラー: 必須ファイルが見つかりません。", file=sys.stderr)
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if not lines:
        print("入力ファイルが空です。")
        return

    total_lines = len(lines)
    print(f"合計 {total_lines} 件の企業データを読み込みました。")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    loop = asyncio.get_running_loop()
    
    # 1行（1社）ごとにタスクを作成する
    tasks = [asyncio.create_task(run_company_in_executor(semaphore, loop, i + 1, line)) for i, line in enumerate(lines)]
    
    print(f"\n最大{MAX_CONCURRENT_TASKS}件の並列処理を開始します...")
    results = await asyncio.gather(*tasks)

    print("\n--- 全社処理完了。結果を統合しています... ---")
    final_data = [item for item in results if item]
    success_count = len(final_data)
    failed_count = total_lines - success_count

    print(f"処理結果: 成功 {success_count}件 / 失敗 {failed_count}件")
    
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