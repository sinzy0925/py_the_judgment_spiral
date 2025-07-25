import sys
import json
import re
import os
import tempfile
from dotenv import load_dotenv
import asyncio
import subprocess

# google.genaiのインポートは非同期化後も必要
try:
    from google import genai
except ImportError:
    print("エラー: 'google-genai'ライブラリがインストールされていません。")
    print("pip install google-genai を実行してください。")
    sys.exit(1)


# .envファイルから環境変数を読み込む
load_dotenv()

# --- PROMPT DEFINITIONS ---

def create_initial_evaluation_prompt(log_output: str) -> str:
    """初回評価と、改善版プロンプトの生成をAIに依頼するプロンプト"""
    return f"""
あなたは、AIのパフォーマンスを多角的に分析し、改善策を提案する専門のプロンプトエンジニアです。
以下の実行ログを慎重に分析し、提供されたJSONスキーマに従って「評価レポート」と「改善版プロンプト」を作成してください。

評価のポイント：
1.  **品質評価**: 情報の正確性、推論の妥当性、指示への忠実性を評価します。
2.  **性能評価**: 実行時間とトークン数から、コストパフォーマンスを評価します。
3.  **プロンプト改善提案**: ログの内容に基づき、元のプロンプトをさらに改善するための**具体的な改善版プロンプトを生成してください。**改善の必要性が低い場合でも、より良くするための提案を盛り込んでください。

--- 評価対象の実行ログ ---
{log_output}
--- ここまで ---

--- 出力必須のJSONスキーマ ---
```json
{{
  "evaluationResult": {{
    "targetCompany": "ログから抽出した調査対象企業名",
    "overallScore": "100点満点での総合評価",
    "overallSummary": "評価全体の総括コメント",
    "detailedCriteria": [
      {{"criterion": "プロンプト指示への忠実性", "score": "25/25", "analysis": "..."}},
      {{"criterion": "情報の正確性（ファクトチェック）", "score": "25/25", "analysis": "..."}},
      {{"criterion": "高度な推論・分析能力", "score": "25/25", "analysis": "..."}},
      {{"criterion": "網羅性と例外処理", "score": "25/25", "analysis": "..."}}
    ]
  }},
  "performanceMetrics": {{
    "executionTimeSeconds": "ログから抽出した総実行時間（float）",
    "tokens": {{"input": "int", "output": "int", "total": "int"}},
    "analysis": "速度とコストの観点からのパフォーマンス分析"
  }},
  "suggestedPrompt": "（ここに、あなたが生成した改善版の完全なプロンプト文字列を記述してください。company_nameプレースホルダーを含めてください。）"
}}
```
"""

def create_comparison_prompt(eval1_json: str, eval2_json: str) -> str:
    """2つの評価結果を比較し、最終判定を下すためのプロンプト"""
    return f"""
あなたは、A/Bテストの結果を分析する専門のアナリストです。
以下の2つのAI実行評価レポート（初回実行と、プロンプト改善後の実行）を比較し、プロンプトの改善が有効だったかどうかを最終判定してください。

--- レポート1: 初回実行の評価 ---
{eval1_json}
--- ここまで ---

--- レポート2: プロンプト改善後の実行評価 ---
{eval2_json}
--- ここまで ---

--- 出力必須のJSONスキーマ ---
```json
{{
  "comparisonSummary": {{
    "initialScore": "レポート1の総合スコア",
    "improvedScore": "レポート2の総合スコア",
    "performanceChange": {{
      "executionTime": "実行時間の変化（例: -2.5s）",
      "totalTokens": "総トークン数の変化（例: +50 tokens）"
    }},
    "qualityChange": "回答の品質（正確性、推論など）がどのように変化したかの具体的な分析",
    "finalVerdict": "プロンプトの改善は有効だったか、その理由は何か、という最終結論"
  }}
}}
```
"""

# --- HELPER FUNCTIONS (Async) ---

async def run_search_app(company_name: str, prompt_file: str = None) -> str:
    """gemini_search_app_new_sdk.py を非同期で実行してログを返す"""
    target_script = "gemini_search_app_new_sdk.py"
    command = [sys.executable, target_script, company_name]
    if prompt_file:
        command.extend(["--prompt-file", prompt_file])

    process_env = os.environ.copy()
    process_env["PYTHONIOENCODING"] = "utf-8"

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=process_env
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, command,
            stdout.decode('utf-8', 'replace'),
            stderr.decode('utf-8', 'replace')
        )

    return stdout.decode('utf-8', 'replace')

async def call_gemini(prompt: str) -> dict:
    """Geminiを非同期で呼び出し、レスポンスのJSONをパースして返す"""
    def generate():
        # 同期SDKはスレッド内で呼び出す
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt
        )
        json_text = response.text.strip()
        # 正規表現でJSON部分を抽出
        match = re.search(r'```json\s*(.*)\s*```', json_text, re.DOTALL)
        if match:
            json_text = match.group(1)
        
        # JSONとしてパース
        return json.loads(json_text)

    # 同期的な処理を別スレッドで実行し、イベントループをブロックしないようにする
    return await asyncio.to_thread(generate)

# --- MAIN LOGIC (Async) ---

async def main():
    if len(sys.argv) < 2:
        print("使い方: python advanced_evaluation_runner.py <評価したい企業名>")
        sys.exit(1)
    company_name = " ".join(sys.argv[1:])

    temp_prompt_file = None
    try:
        # 1. 初回実行
        print("--- [ステップ1/6] 初回実行中... ---")
        initial_log = await run_search_app(company_name)
        print(f"log: \n{initial_log}")
        print("初回実行完了。")

        # 2. 初回評価＆改善案プロンプト生成
        print("\n--- [ステップ2/6] 初回ログを評価し、改善版プロンプトを生成中... ---")
        initial_eval_prompt = create_initial_evaluation_prompt(initial_log)
        initial_eval_result = await call_gemini(initial_eval_prompt)
        suggested_prompt = initial_eval_result.get("suggestedPrompt")
        print(f"log: \n{suggested_prompt}")
        
        if not suggested_prompt:
            print("エラー: 改善版プロンプトの生成に失敗しました。処理を中断します。")
            print("AIからのレスポンス:", json.dumps(initial_eval_result, indent=2, ensure_ascii=False))
            return

        print("改善版プロンプトの生成完了。")

        # 3. 改善版プロンプトを一時ファイルに保存
        print(f"\n--- [ステップ3/6] 改善版プロンプトを一時ファイルに保存します ---")
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix=".txt") as tf:
            temp_prompt_file = tf.name
            tf.write(suggested_prompt)
        
        print(f"改善版プロンプトを '{os.path.basename(temp_prompt_file)}' に保存しました。")

        # 4. 改善後プロンプトで再実行
        print("\n--- [ステップ4/6] 改善版プロンプトで再実行中... ---")
        improved_log = await run_search_app(company_name, prompt_file=temp_prompt_file)
        print(f"log: \n{improved_log}")
        print("再実行完了。")

        # 5. 2回目の評価
        print("\n--- [ステップ5/6] 2回目のログを評価中... ---")
        improved_eval_prompt = create_initial_evaluation_prompt(improved_log)
        improved_eval_result = await call_gemini(improved_eval_prompt)
        print(f"log: \n{improved_eval_result}")
        print("2回目の評価完了。")

        # 6. 最終比較
        print("\n--- [ステップ6/6] 最終比較レポートを生成中... ---")
        comparison_prompt = create_comparison_prompt(
            json.dumps(initial_eval_result),
            json.dumps(improved_eval_result)
        )
        final_report = await call_gemini(comparison_prompt)
        
        print("\n\n" + "="*20 + " 最終比較分析レポート " + "="*20)
        print(json.dumps(final_report, indent=2, ensure_ascii=False))
        print("="*64)

    except subprocess.CalledProcessError as e:
        print(f"\nエラー: スクリプト '{e.cmd[1]}' の実行に失敗しました。")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
    except Exception as e:
        import traceback
        print(f"\nエラー: 予期せぬエラーが発生しました。: {e}")
        traceback.print_exc()
    finally:
        # 一時ファイルをクリーンアップ
        if temp_prompt_file and os.path.exists(temp_prompt_file):
            os.remove(temp_prompt_file)
            print(f"\n一時ファイル '{os.path.basename(temp_prompt_file)}' を削除しました。")


if __name__ == "__main__":
    # 非同期のmain関数を実行
    asyncio.run(main())