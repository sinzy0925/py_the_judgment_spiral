import os
import sys
import time
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import re
from datetime import datetime  # ★ ログのタイムスタンプ用にインポート

# api_key_manager.pyからシングルトンインスタンスをインポート
from api_key_manager import api_key_manager

# .envファイルから環境変数を読み込む
load_dotenv()

def _blocking_call_to_gemini(api_key: str, full_contents: str):
    """
    GeminiへのAPI呼び出しとストリーム処理（思考プロセスを含む）を
    同期的に実行する関数。
    """
    if not api_key:
        print("\nエラー: _blocking_call_to_gemini に有効なAPIキーが渡されませんでした。", file=sys.stderr)
        return None, None
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"\nエラー: APIクライアントの初期化に失敗しました: {e}", file=sys.stderr)
        return None, None

    # 思考機能を有効にする設定
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,  # 思考の要約を有効にする
            thinking_budget=-1      # 動的思考を有効にする（モデルが思考量を自動調整）
        )
    )

    print(f"'{full_contents.strip().splitlines()[0]}' で始まるプロンプトについて、AIが思考を開始します...", file=sys.stderr)
    
    api_call_start_time = time.time()
    try:
        # モデルを gemini-2.5-pro に指定して思考能力を最大限に活用
        stream = client.models.generate_content_stream(
            model='gemini-2.5-pro',
            contents=full_contents,
            config=config,
        )
    except Exception as e:
        print(f"\nAPI呼び出し中にエラーが発生しました: {e}", file=sys.stderr)
        return None, None
    
    thinking_text = ""
    answer_text = ""
    is_first_thought = True
    
    print("\n--- AIの思考プロセスと回答 ---", file=sys.stderr)
    try:
        for chunk in stream:
            if not chunk.candidates:
                continue
            for part in chunk.candidates[0].content.parts:
                if not hasattr(part, 'text') or not part.text:
                    continue
                
                # part.thought 属性の有無で、思考か回答かを判定
                if hasattr(part, 'thought') and part.thought:
                    thinking_text += part.text
                    if is_first_thought:
                        # 思考内容のヘッダーを標準エラー出力に表示
                        print("\n[思考プロセス開始]:", file=sys.stderr)
                        is_first_thought = False
                    # 思考内容を標準エラー出力にリアルタイムで表示
                    print(part.text, end="", flush=True, file=sys.stderr)
                else:
                    # 最終的な回答を変数に蓄積
                    answer_text += part.text
        
        # --- 全てのストリーム受信完了後の処理 ---
        
        # 最終的な回答（JSON）を標準出力に一括で出力
        print(answer_text, end="")
        
        if not is_first_thought:
            print("\n[思考プロセス終了]", file=sys.stderr)

        print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。", file=sys.stderr)
        
        # 思考内容と回答の両方を返す
        return thinking_text, answer_text
    
    except Exception as e:
        print(f"\nストリームの処理中に予期せぬエラーが発生しました: {e}", file=sys.stderr)
        return None, None

async def main():
    start_time = time.time()
    
    if sys.stdin.isatty():
        print("エラー: このスクリプトはパイプまたはリダイレクトで入力を受け取る必要があります。", file=sys.stderr)
        sys.exit(1)
    
    query_from_stdin = sys.stdin.read().strip()

    if not query_from_stdin:
        print("エラー: 入力が空です。", file=sys.stderr)
        sys.exit(1)

    companies = [c.strip() for c in re.split(r'\s*###\s*|\s*\n\s*', query_from_stdin) if c.strip()]
    print(companies)
    input_count = len(companies)

    # お客様の目的に最適化されたプロンプト
    prompt_template="""
# INSTRUCTIONS
You are a professional, evidence-focused researcher specializing in identifying the "Official Website URL", "Contact Page URL", and "Email Address" from a list of company information.
For every company provided in the list below, you must conduct a thorough investigation using the Google Search tool and output the results strictly in the specified JSON format.
**Crucially, your final JSON output, including all keys and string values, MUST be in Japanese.**

# LIST OF COMPANIES TO INVESTIGATE
{company_list}

# STRICT RULES TO FOLLOW
1.  **Output Format Compliance:** Your entire response MUST be a single JSON object within a markdown code block starting with ```json and ending with ```. Do not include any text outside of this block (e.g., greetings, apologies).
2.  **IMPORTANT - Input Data Interpretation:** Each line in the company list may contain prefixes like "mail" or numbers. These are NOT part of the official company name. You must ignore them and accurately extract only the company name and address before starting your research.
3.  **IMPORTANT - Investigation Procedure:**
    a. First, identify the company's **official website top page URL** and record it in the `url` field.
    b. Next, explore the official website to find the **URL for the "Contact Us" or equivalent page** and record it in the `contactUrl` field.
    c. Finally, search within the official site (especially the contact and company overview pages) for a **representative email address** and record it in the `email` field.
    d. If you cannot find an email address after completing steps a, b, and c, please retry steps a, b, and c one more time.
4.  **Evidence Recording:** For each company's investigation, you MUST accurately record the **actual Google search queries you used** and the **most critical source URLs** that formed the basis of your answer in the `evidence` field.
5.  **Handling Missing Information:** If you cannot find a piece of information after a thorough search, do not invent it. Honestly use the value `null`.
6.  **Information Accuracy:** The company names or addresses provided in the prompt may be outdated. You must base your final answers on the latest, accurate information discovered through your search results.

# OUTPUT FORMAT (JSON) - MUST BE IN JAPANESE
```json
{{
  "status": "success",
  "count": {input_count},
  "data": [
    {{
      "companyName": "（調査で判明した企業の正式名称）",
      "url": "（公式サイトのトップページのURL、またはnull）",
      "contactUrl": "（「お問い合わせ」ページのURL、またはnull）",
      "email": "（発見したメールアドレス、またはnull）",
      "evidence": {{
        "searchQueries": [
          "（実際に使用した検索クエリ1）",
          "（実際に使用した検索クエリ2）"
        ],
        "sourceUrls": [
          "（回答の根拠となったURL1）",
          "（回答の根拠となったURL2）"
        ]
      }}
    }}
  ]
}}```
"""
    full_contents = prompt_template.format(
        company_list=query_from_stdin,
        input_count=input_count
    )

    print(f"プロンプトを生成しました。文字数: {len(full_contents)}", file=sys.stderr)

    # APIキーマネージャーから次のキーを取得
    main_call_key = await api_key_manager.get_next_key()
    if not main_call_key:
        print("エラー: メイン処理用のAPIキーを取得できませんでした。", file=sys.stderr)
        sys.exit(1)
        
    key_info = api_key_manager.last_used_key_info 
    print(f"[INFO] メイン処理用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。", file=sys.stderr)

    # Geminiへの処理を別スレッドで実行
    thinking_text, answer_text = await asyncio.to_thread(
        _blocking_call_to_gemini, main_call_key, full_contents
    )

    if thinking_text is None and answer_text is None:
        print("エラー: Geminiからの応答取得に失敗しました。処理を中断します。", file=sys.stderr)
        sys.exit(1)

    # === ★ 修正点: ログファイルへの書き込み処理を追加 ===
    end_time = time.time()
    execution_time = end_time - start_time

    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(log_dir, f"batch_run_log_{timestamp}.log")

    # ログに書き込む内容を整形
    log_content = f"""
============================================================
Log Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Total Execution Time: {execution_time:.2f} seconds
Input Companies: {input_count}
============================================================

--- PROMPT SENT TO GEMINI ---
{full_contents}
------------------------------------------------------------

--- THINKING PROCESS (captured from stderr) ---
{thinking_text.strip()}
------------------------------------------------------------

--- FINAL ANSWER (captured from stdout) ---
{answer_text.strip()}
============================================================
"""

    try:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(log_content.strip())
        print(f"\n[INFO] このバッチの実行ログを '{log_file_path}' に保存しました。", file=sys.stderr)
    except IOError as e:
        print(f"\n[ERROR] ログファイルの保存に失敗しました: {e}", file=sys.stderr)
    # --- ログファイル書き込み処理ここまで ---

    print("\n------------------------------", file=sys.stderr)
    print(f"総実行時間: {execution_time:.2f}秒", file=sys.stderr)

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
        # アプリケーション終了時にセッション情報を保存
        api_key_manager.save_session()
        print("[INFO] アプリケーション終了に伴いセッションを保存しました。", file=sys.stderr)
        sys.exit(exit_code)