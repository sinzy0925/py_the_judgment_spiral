# gemini_search_app_new_sdk.py (最終ログ出力修正版)

import os
import sys
import time
import argparse
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import sys
import json
import re

# 作成したAPIキーマネージャーをインポート
from api_key_manager import api_key_manager

# .envファイルから環境変数を読み込む
load_dotenv()

def _blocking_call_to_gemini(api_key: str, full_contents: str):
    """
    GeminiへのAPI呼び出しとストリーム処理という、すべての同期的（ブロッキング）
    な処理をまとめて実行する関数。この関数全体が別スレッドで実行される。
    
    Args:
        api_key (str): このAPI呼び出しで使用するAPIキー。
        full_contents (str): モデルに渡す完全なプロンプト。
    """
    
    if not api_key:
        print("\nエラー: _blocking_call_to_gemini に有効なAPIキーが渡されませんでした。", file=sys.stderr)
        return None, None
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"\nエラー: APIクライアントの初期化に失敗しました: {e}", file=sys.stderr)
        return None, None
        
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=True
        )
    )

    print(f"'{full_contents.strip().splitlines()[0]}' について、AIが思考を開始します...")
    
    api_call_start_time = time.time() 
    try:
        stream = client.models.generate_content_stream(
            model='gemini-2.5-pro',
            contents=full_contents,
            config=config,
        )
    except Exception as e:
        print(f"\nAPI呼び出し中にエラーが発生しました: {e}", file=sys.stderr)
        return None, None
    
    is_first_thought = True
    is_first_answer = True
    first_chunk_received = False
    thinking_text = ""
    answer_text = ""
    
    print("\n--- AIの思考プロセスと回答 ---")
    try:
        for chunk in stream:
            if not first_chunk_received:
                first_chunk_received = True
                print(f"[{time.time() - api_call_start_time:.2f}s] API呼び出し成功、最初のチャンクを受信しました。")

            if not chunk.candidates:
                continue

            for part in chunk.candidates[0].content.parts:
                if not hasattr(part, 'text') or not part.text:
                    continue
                
                if hasattr(part, 'thought') and part.thought:
                    thinking_text += part.text
                    if is_first_thought:
                        print("\n[思考プロセス]:")
                        is_first_thought = False
                    print(part.text, end="", flush=True)
                else:
                    answer_text += part.text
                    if is_first_answer:
                        print("\n\n[最終的な回答]:")
                        is_first_answer = False
                    res = re.sub(r'```json|```', '', part.text)
                    print(res, end="", flush=True)#
        
        print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。")
        return thinking_text, answer_text
    
    except Exception as e:
        print(f"\nストリームの処理中に予期せぬエラーが発生しました: {e}", file=sys.stderr)
        return None, None

def _blocking_count_tokens(api_key: str, model: str, contents: str) -> types.CountTokensResponse | None:
    """
    APIキーを使ってクライアントを初期化し、トークン数を計算する同期関数。
    """
    if not api_key:
        print("\nエラー: _blocking_count_tokens に有効なAPIキーが渡されませんでした。", file=sys.stderr)
        return None
    try:
        client = genai.Client(api_key=api_key)
        return client.models.count_tokens(model=model, contents=contents)
    except Exception as e:
        print(f"\nトークン計算中にエラーが発生しました: {e}", file=sys.stderr)
        return None

async def main():
    """
    メインの非同期実行関数
    """
    parser = argparse.ArgumentParser(description="企業情報を検索するGeminiアプリ")
    parser.add_argument("query", help="検索対象の企業名と住所")
    parser.add_argument("--prompt-file", help="プロンプトが記述されたテキストファイルのパス")
    parser.add_argument("--param", help="パラメータの値を指定するオプション")
    args = parser.parse_args()

    start_time = time.time()
    
    full_contents = ""
    input_count = 0 # <<< 変更点: 入力件数を保持する変数を追加

    if args.prompt_file:
        try:
            print(f"INFO: プロンプトファイル '{args.prompt_file}' を読み込みます。")
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                full_contents = f.read()
            # プロンプトファイルの場合は暫定的に1件としてカウント
            input_count = 1
        except FileNotFoundError:
            print(f"エラー: プロンプトファイルが見つかりません: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
    else:
        print("INFO: デフォルトのプロンプトテンプレートを使用します。")
        
        # <<< 変更点: 入力文字列から件数を計算 >>>
        companies = [c.strip() for c in re.split(r'\s*###\s*|\s*\n\s*', args.query) if c.strip()]
        input_count = len(companies)

        prompt_template="""
# 調査対象リスト
- {company_name}

# あなたの役割
あなたは、与えられたリストの各項目について、Web上の信頼できる情報源を基に、
正確な情報をファクトチェックする専門のリサーチャーです。

# 任務
以下の【調査対象リスト】に含まれる条件に基づいて、**必ずGoogle検索ツールを使って**、
それぞれの**「最新の正確な名称」と「最新の正確な住所」**を調査してください。


# 厳守すべきルール
1.  **情報の源泉:** あなたの回答は、**必ずGoogle検索で得られた信頼できる情報源（公式サイトのスニペット、地図情報のスニペット）
    **に基づいていなければなりません。プロンプト内の情報は参考程度とし、鵜呑みにしないでください。
2.  **ファクトチェックの徹底:** 名称と住所を基に、正しい住所を再検証してください。
3.  **欠損情報の扱い:** 調査してもがどうしても見つからない場合は、住所の値を `不正確` としてください。

# 出力形式
```markdown
- 名称１,住所
- 名称２,住所
- ...  

```
"""

        prompt_template2="""
# 調査対象リスト
- {company_name}

# あなたの役割
あなたは、与えられたリストの各項目について、Web上の信頼できる情報源を基に、
正確な情報をファクトチェックする専門のリサーチャーです。

# 任務
以下の【調査対象リスト】に含まれる条件に基づいて、**必ずGoogle検索ツールを使って**、
それぞれの**「最新の正確な名称」と「最新の正確な住所」**を調査してください。
調査対象リストには、間違いが多数含まれています。間違いを見つけたら、住所にnullを入力してください。


# 厳守すべきルール
1.  **情報の源泉:** あなたの回答は、**必ずGoogle検索で得られた信頼できる情報源（公式サイト、地図情報、信頼できるサイトなど）
    **に基づいていなければなりません。プロンプト内の情報は参考程度とし、鵜呑みにしないでください。
2.  **ファクトチェックの徹底:** 名称と住所を基に、正しい住所を再検証してください。
3.  **欠損情報の扱い:** 調査してもがどうしても見つからない場合は、住所の値を `不正確` としてください。

# 出力形式
```markdown
- 名称１,住所
- 名称２,住所
- ...  

```
"""


        prompt_template3="""

# 調査対象リスト
- {company_name}

# あなたの役割
あなたは、与えられたリストの各項目について、Web上の信頼できる情報源を基に、
正確な情報をファクトチェックする専門のリサーチャーです。

# 任務
以下の【調査対象リスト】に含まれる名称について、**必ずGoogle検索ツールを使って**、
それぞれの**「最新の正確な住所」と「公式な電話番号」**を調査してください。


# 厳守すべきルール
1.  **情報の源泉:** あなたの回答は、**必ずGoogle検索で得られた信頼できる情報源（公式サイト、地図情報、信頼できるサイトなど）
    **に基づいていなければなりません。プロンプト内の情報は参考程度とし、鵜呑みにしないでください。
2.  **ファクトチェックの徹底:** 名称と「大阪市天王寺区」という情報を基に、正しい住所と電話番号を再検証してください。
3.  **欠損情報の扱い:** 調査しても電話番号がどうしても見つからない場合は、電話番号の値を `null` としてください。
4.  **出力形式:** 思考プロセスは不要です。最終的な結果のみを、以下の形式のJSON配列として出力してください。

# 出力形式
```json
[
  {{
    "name": "名称",
    "address": "（調査で判明した正確な住所）",
    "tel": "（調査で判明した電話番号、またはnull）"
  }},
  {{
    "name": "名称",
    "address": "（調査で判明した正確な住所）",
    "tel": "（調査で判明した電話番号、またはnull）"
  }}
]
"""
        if args.param:
            if args.param == "1":
                full_contents = prompt_template.format(company_name=args.query)
            elif args.param == "2":
                full_contents = prompt_template2.format(company_name=args.query)
            elif args.param == "3":
                full_contents = prompt_template3.format(company_name=args.query)
            

    if not full_contents:
        print("エラー: 実行するプロンプトが空です。", file=sys.stderr)
        sys.exit(1)

    print(f"プロンプト: \n{full_contents}\n\n")

    input_tokens, thinking_tokens, answer_tokens = 0, 0, 0

    # 1. 入力トークン計算
    input_key = await api_key_manager.get_next_key()
    if input_key:
        key_info = api_key_manager.last_used_key_info 
        print(f"[INFO] 入力トークン計算用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。")
        input_token_response = await asyncio.to_thread(
            _blocking_count_tokens, input_key, 'gemini-2.5-flash', full_contents
        )
        if input_token_response:
            input_tokens = input_token_response.total_tokens

    # 2. Geminiへのメイン処理
    main_call_key = await api_key_manager.get_next_key()
    if not main_call_key:
        print("エラー: メイン処理用のAPIキーを取得できませんでした。", file=sys.stderr)
        sys.exit(1)
        
    key_info = api_key_manager.last_used_key_info 
    print(f"[INFO] メイン処理用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。")
    thinking_text, answer_text = await asyncio.to_thread(
        _blocking_call_to_gemini, main_call_key, full_contents
    )

    if thinking_text is None and answer_text is None:
        print("エラー: Geminiからの応答取得に失敗しました。処理を中断します。", file=sys.stderr)
        sys.exit(1)
        
    # 3. 出力トークン計算
    if thinking_text:
        thinking_key = await api_key_manager.get_next_key()
        if thinking_key:
            key_info = api_key_manager.last_used_key_info 
            print(f"[INFO] 思考トークン計算用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。")
            thinking_token_response = await asyncio.to_thread(
                _blocking_count_tokens, thinking_key, 'gemini-2.5-flash', thinking_text
            )
            if thinking_token_response:
                thinking_tokens = thinking_token_response.total_tokens

    if answer_text:
        answer_key = await api_key_manager.get_next_key()
        if answer_key:
            key_info = api_key_manager.last_used_key_info 
            print(f"[INFO] 回答トークン計算用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。")
            answer_token_response = await asyncio.to_thread(
                _blocking_count_tokens, answer_key, 'gemini-2.5-flash', answer_text
            )
            if answer_token_response:
                answer_tokens = answer_token_response.total_tokens

    print("\n------------------------------")
    end_time = time.time()
    
    # <<< 変更点: 最終ログ出力 >>>
    print(f"\n総実行時間: {end_time - start_time:.2f}秒")
    if input_count > 0:
        print(f"[ログ] 入力件数: {input_count}") # <= 追加
    print(f"[ログ] 入力トークン数: {input_tokens}")
    print(f"[ログ] 思考トークン数: {thinking_tokens}")
    print(f"[ログ] 回答トークン数: {answer_tokens}")
    total_output_tokens = thinking_tokens + answer_tokens
    print(f"[ログ] 合計出力トークン数: {total_output_tokens}")
    print(f"[ログ] 総計トークン数: {input_tokens + total_output_tokens}")

    logdata= f"""\n\n---\n\nプロンプト:{prompt_template}
総実行時間: {end_time - start_time:.2f}秒
[ログ] 入力件数: {input_count}
[ログ] 入力トークン数: {input_tokens}
[ログ] 思考トークン数: {thinking_tokens}
[ログ] 回答トークン数: {answer_tokens}
[ログ] 合計出力トークン数: {total_output_tokens}
[ログ] 総計トークン数: {input_tokens + total_output_tokens}

"""

    log_dir = 'log'
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, 'output.log')
    try:
        # 'a'は追記モード、'utf-8'は文字化けを防ぐために指定します
        with open(file_path, 'a', encoding='utf-8') as f:
            # f.write()で書き込み、末尾に改行を追加します
            f.write(logdata)
        
        print(f"'{file_path}' に内容を追記しました。")

    except IOError as e:
        print(f"ファイルへの書き込み中にエラーが発生しました: {e}")


if __name__ == "__main__":
    exit_code = 0
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nプログラムが中断されました。")
        exit_code = 130
    except Exception as e:
        print(f"予期せぬ致命的なエラーが発生しました: {e}", file=sys.stderr)
        exit_code = 1 
    finally:
        api_key_manager.save_session()
        print("[INFO] アプリケーション終了に伴いセッションを保存しました。")
        sys.exit(exit_code)