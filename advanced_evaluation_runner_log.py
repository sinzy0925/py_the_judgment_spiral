# advanced_evaluation_runner_log.py (ロギング機能追加版)

import sys
import json
import re
import os
import tempfile
from dotenv import load_dotenv
import asyncio
import subprocess
import logging # <<< 変更点: loggingモジュールをインポート
from datetime import datetime # <<< 変更点: datetimeモジュールをインポート
import time

# google.genaiのインポート
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("エラー: 'google-genai'ライブラリがインストールされていません。")
    print("pip install google-genai を実行してください。")
    sys.exit(1)

# ApiKeyManagerのシングルトンインスタンスをインポート
from api_key_manager import api_key_manager

# .envファイルから環境変数を読み込む
load_dotenv()

# --- Logger Setup ---
# <<< 変更点: ロガー設定のセクションを丸ごと追加 >>>
def setup_logger(company_name: str):
    """
    コンソールとファイルの両方に出力するロガーを設定する。
    """
    # 1. ログファイル名の生成
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    
    # ファイル名に使えない文字を置換
    safe_company_name = re.sub(r'[\\|/|:|*|?|"|<|>|\|]', '_', company_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_name = f"{timestamp}_{safe_company_name[:50]}.log"
    log_file_path = os.path.join(log_dir, log_file_name)

    # 2. ロガーの取得とレベル設定
    #    logging.getLogger() に名前を渡さないことで、ルートロガーを取得
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 3. 既存のハンドラをクリア (重複設定を防ぐため)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 4. フォーマッターの作成
    #    ログメッセージのみを出力するシンプルなフォーマット
    formatter = logging.Formatter('%(message)s')

    # 5. コンソールハンドラの作成と設定
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 6. ファイルハンドラの作成と設定
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 7. print関数をロガーのinfoメソッドで上書き（モンキーパッチ）
    #    これにより、既存のprint文はすべてロガー経由で出力されるようになる
    #builtins = __import__('builtins')
    #builtins.print = logger.info
    
    #print(f"--- ログ出力開始: {log_file_path} ---")
    # ログに出力したい場合は、明示的に logger.info を使う
    logging.info(f"--- ログ出力開始: {log_file_path} ---")

# --- PROMPT DEFINITIONS ---
def create_initial_evaluation_prompt(log_output: str, company_name: str) -> str:
    """初回評価と、改善版プロンプトの生成をAIに依頼するプロンプト"""
    
    # ドキュメントの要点をプロンプト内に埋め込む
    prompt_design_principles = """
### 最高のプロンプトを設計するための原理原則（Google AIドキュメントより抜粋）

0.  **早期打ち切りルール:**
    *   ユーザーが必要としている内容は複数です。なので、１件の情報に対して、どれくらいの時間をかけるかを決めてください。
    *   早期打ち切りにする場合は、理由がわかるように提示してください。
    *   一度調べて、分からなければその時点で、「不明」と答えて良い。

1.  **簡素なプロンプトを設計する:**
    *   文字数が多ければ、良いプロンプトになるとは限りません。
    *   逆に簡素なプロンプトが良い結果を出す場合が多い。
    *   この前提を踏まえて、プロンプト全体を設計すること。
    *   AIに自由を残してあげてください。厳格すぎる指示では、AIの自由が奪われます。
    *   **以下にたくさんの指示事項があるが、参考程度に確認せよ。**

2.  **推測の絶対的禁止:**
    *   具体的な検索結果に基づく情報のみ提供すること。
    *   ファクトチェックして、推測がないか調査すること。

3.  **明確性と具体性:**
    *   曖昧な指示を避け、AIに何をすべきか、どのような形式で出力してほしいかを具体的に指示する。
    *   制約（例：文字数、使用すべきでない言葉）を明確に指定する。

4.  **少数ショットプロンプト（Few-shot Prompting）:**
    *   可能であれば、望ましい入出力の「例」を1〜数個示す。モデルは例からパターンを学習し、より正確な結果を生成する。
    *   例の形式（XMLタグ、空白、改行など）は一貫させる。

5.  **コンテキストの追加:**
    *   AIが必要な情報を持っていると仮定せず、回答を生成するために必要な背景情報やデータをプロンプトに含める。

6.  **役割（ペルソナ）の付与:**
    *   「あなたは専門の〇〇です」のように、AIに特定の役割を与えることで、その役割にふさわしい、より高品質な応答を引き出す。

7.  **構造化と分割:**
    *   複雑なタスクは、役割設定、ルール、入力データ、出力形式、最終命令などのコンポーネントに分割してプロンプトを構造化する。
    *   ステップ・バイ・ステップでの実行を指示することで、複雑な推論を安定させる。

8.  **出力形式の制御:**
    *   JSONやマークダウンなど、望ましい出力形式を明確に指定する。
    *   `Output:` のような出力接頭辞を使って、モデルに応答の開始点を教える（完了戦略）。

9.  **メールアドレスの調査方法:**
    *   メールアドレスは以下の手順で調査する。
    *   公式サイトがあれば、会社情報、お問合せ、companyinfoなどのページから、<a>タグ、mailto:に含まれていないか調べること。
"""
    
    return f"""
以下の評価対象の実行ログを元に、改善が見込めると確信があれば、プロンプトを修正してください。確信がなければ、前回と全く同じプロンプトを出力してください。

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
  "suggestedPrompt": "（ここに、あなたが生成した改善版の完全なプロンプト文字列を記述してください。プレースホルダーは含めないでください。）"
}}```
"""



    return1= f"""
あなたは、AIのパフォーマンスを多角的に分析し、改善策を提案する、世界トップクラスのプロンプトエンジニアです。
あなたは、以下の【最高のプロンプトを設計するための原理原則】を深く理解しています。

{prompt_design_principles}

---
### あなたの任務
以下の【評価対象の実行ログ】を慎重に分析し、【出力必須のJSONスキーマ】に従って「評価レポート」と「改善版プロンプト」を作成してください。

### 改善版プロンプト作成時の最重要ルール
- 上記の【原理原則】を最大限に活用し、ログで明らかになった課題を解決するための、より洗練されたプロンプトを生成してください。
- 生成するプロンプトは、それ自体が**単独で実行可能な命令セット**でなければなりません。
- 調査対象の企業名として、必ず「{company_name}」という具体的な文字列をプロンプト内に直接埋め込んでください。プレースホルダーは絶対に使用しないでください。
- プロンプトの最後には、AIが実行すべき具体的な命令文を必ず含めてください。

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
  "suggestedPrompt": "（ここに、あなたが生成した改善版の完全なプロンプト文字列を記述してください。プレースホルダーは含めないでください。）"
}}```
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
json```{{
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
}}```
"""

async def run_search_app(company_name: str, prompt_file: str = None) -> str:
    target_script = "gemini_search_paralell.py"
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

    # サブプロセスの標準エラー出力もログに記録する
    if stderr:
        print("\n--- サブプロセスのエラー出力 ---")
        print(stderr.decode('utf-8', 'replace').strip())
        print("------------------------------\n")
        
    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, command,
            stdout.decode('utf-8', 'replace'),
            stderr.decode('utf-8', 'replace')
        )

    return stdout.decode('utf-8', 'replace')

async def call_gemini(prompt: str) -> dict:
    api_key = await api_key_manager.get_next_key()
    if not api_key:
        raise ValueError("APIキーを取得できませんでした。ApiKeyManagerの設定を確認してください。")

    key_info = api_key_manager.last_used_key_info
    print(f"  [Gemini Call] API Key (index: {key_info['index']}/{key_info['total']-1}, ends with: ...{key_info['key_snippet']}) を使用します。")
    
    def generate(key_to_use: str):
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,
                include_thoughts=True
            )
        )
    
        client = genai.Client(api_key=key_to_use)
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=config
        )
        raw_text = response.text.strip()
        
        json_string = None
        match = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
        if match:
            json_string = match.group(1)
        else:
            start_index = raw_text.find('{')
            end_index = raw_text.rfind('}')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_string = raw_text[start_index : end_index + 1]

        if json_string:
            try:
                # <<< 修正点：JSONをパースする前に、文字列内の不正な改行を置換する >>>
                # re.subを使って、キー: "値" の値部分に含まれる改行文字(\n)を、
                # JSONとして有効なエスケープシーケンス(\\n)に置換する。
                # (?<!\\) は「直前にバックスラッシュがない」ことを確認するネガティブ後読みアサーション。
                # これにより、既に正しくエスケープされている \\n を \\\\n に変えてしまうのを防ぐ。
                json_string = json_string.strip()
                corrected_json_string = re.sub(r'(?<!\\)\n', r'\\n', json_string)

                return json.loads(corrected_json_string) # <<< 修正した文字列をパースする
                
            except json.JSONDecodeError as e:
                print("\n--- JSONパースエラー ---")
                print(f"エラー詳細: {e}")
                # <<< デバッグ用に修正前の文字列と修正後の文字列の両方を出力 >>>
                print("パースに失敗した抽出済み文字列（修正前）:", json_string)
                if 'corrected_json_string' in locals():
                    print("パースに失敗した抽出済み文字列（修正後）:", corrected_json_string)
                print("--- AIからの生のレスポンス全体 ---")
                print(raw_text)
                print("------------------------------\n")
                raise

    return await asyncio.to_thread(generate, api_key)


# --- MAIN LOGIC (Async) ---
async def main():
    if len(sys.argv) < 2:
        # ロガー設定前なので、オリジナルのprintで出力
        original_print = __import__('builtins').print
        original_print("使い方: python advanced_evaluation_runner.py <評価したい企業名>")
        sys.exit(1)
        
    company_name = " ".join(sys.argv[1:])
    
    # <<< 変更点: main関数の最初にロガーを設定
    setup_logger(company_name)

    temp_prompt_file = None
    try:
        # (以降のtryブロック内は変更なし)
        # 1. 初回実行
        print("--- [ステップ1/6] 初回実行中... ---")
        initial_log = await run_search_app(company_name)
        print(f"log: \n{initial_log}")
        print("初回実行完了。")
        await asyncio.sleep(2) # <<< 変更点: time.sleep(2) 

        # 2. 初回評価＆改善案プロンプト生成
        print("\n--- [ステップ2/6] 初回ログを評価し、改善版プロンプトを生成中... ---")
        initial_eval_prompt = create_initial_evaluation_prompt(initial_log, company_name)
        initial_eval_result = await call_gemini(initial_eval_prompt)
        suggested_prompt = initial_eval_result.get("suggestedPrompt")
        print(f"log: \n{initial_eval_prompt}")
        print(f"log: \n{initial_eval_result}")
        print(f"log: \n{suggested_prompt}")
        
        if not suggested_prompt:
            print("エラー: 改善版プロンプトの生成に失敗しました。処理を中断します。")
            print("AIからのレスポンス:", json.dumps(initial_eval_result, indent=2, ensure_ascii=False))
            return

        print("改善版プロンプトの生成完了。")
        await asyncio.sleep(2)

        # 3. 改善版プロンプトを一時ファイルに保存
        print(f"\n--- [ステップ3/6] 改善版プロンプトを一時ファイルに保存します ---")
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix=".txt") as tf:
            temp_prompt_file = tf.name
            tf.write(suggested_prompt)
        
        print(f"改善版プロンプトを '{os.path.basename(temp_prompt_file)}' に保存しました。")
        await asyncio.sleep(2)
        
        # 4. 改善後プロンプトで再実行
        print("\n--- [ステップ4/6] 改善版プロンプトで再実行中... ---")
        improved_log = await run_search_app(company_name, prompt_file=temp_prompt_file)
        print(f"log: \n{improved_log}")
        print("再実行完了。")
        await asyncio.sleep(2)

        # 5. 2回目の評価
        print("\n--- [ステップ5/6] 2回目のログを評価中... ---")
        improved_eval_prompt = create_initial_evaluation_prompt(improved_log, company_name)
        improved_eval_result = await call_gemini(improved_eval_prompt)
        print(f"log: \n{improved_eval_prompt}")
        print(f"log: \n{improved_eval_result}")
        print("2回目の評価完了。")
        await asyncio.sleep(2)
        
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
        # CalledProcessErrorにはstdout, stderrが属性として含まれているので、それらを出力
        if e.stdout:
            print("--- STDOUT ---")
            print(e.stdout)
        if e.stderr:
            print("--- STDERR ---")
            print(e.stderr)
            
    except Exception as e:
        import traceback
        print(f"\nエラー: 予期せぬエラーが発生しました。: {e}")
        # traceback.print_exc() はファイルにも出力される
        traceback.print_exc()
        
    finally:
        # (finallyブロックは変更なし)
        print("\n[ApiKeyManager] セッション情報を保存しています...")
        api_key_manager.save_session()
        print("[ApiKeyManager] セッション情報を保存しました。")
        
        if temp_prompt_file and os.path.exists(temp_prompt_file):
            os.remove(temp_prompt_file)
            print(f"\n一時ファイル '{os.path.basename(temp_prompt_file)}' を削除しました。")


if __name__ == "__main__":
    asyncio.run(main())