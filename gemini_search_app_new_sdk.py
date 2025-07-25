# gemini_search_app_new_sdk.py (修正後)

import os
import sys
import time
import argparse
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 作成したAPIキーマネージャーをインポート
from api_key_manager import api_key_manager

# .envファイルから環境変数を読み込む（ApiKeyManagerより先に実行されるのが望ましい）
load_dotenv()

def _blocking_call_to_gemini(api_key: str, full_contents: str):
    """
    GeminiへのAPI呼び出しとストリーム処理という、すべての同期的（ブロッキング）
    な処理をまとめて実行する関数。この関数全体が別スレッドで実行される。
    
    Args:
        api_key (str): このAPI呼び出しで使用するAPIキー。
        full_contents (str): モデルに渡す完全なプロンプト。
    """
    
    # 受け取ったAPIキーでクライアントを初期化
    if not api_key:
        print("\nエラー: _blocking_call_to_gemini に有効なAPIキーが渡されませんでした。")
        return None, None
    try:
        client = genai.Client(api_key=api_key)
        key_info = api_key_manager.last_used_key_info
        print(f"[INFO] メインAPIコール: キー (index: {key_info['index']}, ...{key_info['key_snippet']}) を使用します。")
    except Exception as e:
        print(f"\nエラー: APIクライアントの初期化に失敗しました: {e}")
        return None, None
        
    # モデルとツールの設定
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=True
        )
    )

    # ストリーム生成
    print(f"'{full_contents.splitlines()[0]}' について、AIが思考を開始します...")
    try:
        stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=full_contents,
            config=config,
        )
    except Exception as e:
        print(f"\nAPI呼び出し中にエラーが発生しました: {e}")
        return None, None
    
    # ストリーム処理
    api_call_start_time = time.time()
    print(f"[{time.time() - api_call_start_time:.2f}s] API呼び出し成功、ストリーム受信待機中...")
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
                print(f"[{time.time() - api_call_start_time:.2f}s] 最初のチャンクを受信しました。")

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
                    res = part.text.replace("```json", "").replace("```", "")
                    print(res, end="", flush=True)
        
        print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。")
        return thinking_text, answer_text
    
    except Exception as e:
        print(f"\nストリームの処理中に予期せぬエラーが発生しました: {e}")
        return None, None

def _blocking_count_tokens(api_key: str, model: str, contents: str) -> types.CountTokensResponse | None:
    """
    APIキーを使ってクライアントを初期化し、トークン数を計算する同期関数。
    """
    if not api_key:
        print("\nエラー: _blocking_count_tokens に有効なAPIキーが渡されませんでした。")
        return None
    try:
        client = genai.Client(api_key=api_key)
        key_info = api_key_manager.last_used_key_info
        print(f"[INFO] トークン数計算: キー (index: {key_info['index']}, ...{key_info['key_snippet']}) を使用します。")
        return client.models.count_tokens(model=model, contents=contents)
    except Exception as e:
        print(f"\nトークン計算中にエラーが発生しました: {e}")
        return None

async def main():
    """
    メインの非同期実行関数
    """
    parser = argparse.ArgumentParser(description="企業情報を検索するGeminiアプリ")
    parser.add_argument("query", help="検索対象の企業名と住所")
    parser.add_argument("--prompt-file", help="プロンプトが記述されたテキストファイルのパス")
    args = parser.parse_args()

    start_time = time.time()
    question = args.query

    # プロンプトの準備
    prompt_template="""以下の企業について、公開情報から徹底的に調査し、結果を下記のJSON形式で厳密に出力してください。

調査対象企業： {company_name}

[出力指示]
- 必ず指定されたJSON形式に従ってください。
- 各項目について、可能な限り正確な情報を探してください。
- Webサイト、会社概要、登記情報などを横断的に確認し、情報の裏付けを取るように努めてください。
- **企業が閉鎖・移転・倒産しているなど、特記事項がある場合は、「companyStatus」項目にその状況を記載してください。**
- 調査しても情報が見つからない項目には、「情報なし」と明確に記載してください。

[JSON出力形式]
```json
{{
  "companyName": "企業の正式名称（string）",
  "companyStatus": "企業の現在の状況（例：活動中, 閉鎖, 情報なし）",
  "officialUrl": "公式サイトのURL（string）",
  "address": "本社の所在地（string）",
  "industry": "主要な業界（string）",
  "email": "代表メールアドレス（string）",
  "tel": "代表電話番号（string）",
  "fax": "代表FAX番号（string）",
  "capital": "資本金（string）",
  "founded": "設立年月（string）",
  "businessSummary": "事業内容の簡潔な要約（string）",
  "strengths": "企業の強みや特徴（string）"
}}
"""

    if args.prompt_file:
    try:
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        print(f"エラー: プロンプトファイルが見つかりません: {args.prompt_file}")
    return

full_contents = prompt_template.format(company_name=question)

print(f"プロンプト: \n{full_contents[:200]}...")

input_tokens = 0
thinking_tokens = 0
answer_tokens = 0

try:
    # 1. 入力トークン計算
    input_key = await api_key_manager.get_next_key()
    input_token_response = await asyncio.to_thread(
        _blocking_count_tokens, input_key, 'gemini-2.5-flash', full_contents
    )
    if input_token_response:
        input_tokens = input_token_response.total_tokens

    # 2. Geminiへのメイン処理
    main_call_key = await api_key_manager.get_next_key()
    thinking_text, answer_text = await asyncio.to_thread(
        _blocking_call_to_gemini, main_call_key, full_contents
    )

    # 3. 出力トークン計算
    if thinking_text:
        thinking_key = await api_key_manager.get_next_key()
        thinking_token_response = await asyncio.to_thread(
            _blocking_count_tokens, thinking_key, 'gemini-2.5-flash', thinking_text
        )
        if thinking_token_response:
            thinking_tokens = thinking_token_response.total_tokens
    
    if answer_text:
        answer_key = await api_key_manager.get_next_key()
        answer_token_response = await asyncio.to_thread(
            _blocking_count_tokens, answer_key, 'gemini-2.5-flash', answer_text
        )
        if answer_token_response:
            answer_tokens = answer_token_response.total_tokens

    print("\n------------------------------")

except Exception as e:
    if 'api_key' in str(e).lower() or 'credential' in str(e).lower():
         print("\nエラー: APIキーが見つからないか、無効です。")
         print(".envファイルに 'GOOGLE_API_KEY' または 'GOOGLE_API_KEY_n' が正しく設定されているか確認してください。")
    else:
        print(f"\nメイン処理で予期せぬエラーが発生しました: {e}")

finally:
    # アプリケーション終了時にセッションを保存
    api_key_manager.save_session()
    print("[INFO] セッションを保存しました。")

end_time = time.time()
print(f"\n総実行時間: {end_time - start_time:.2f}秒")
print(f"[ログ] 入力トークン数: {input_tokens}")
print(f"[ログ] 思考トークン数: {thinking_tokens}")
print(f"[ログ] 回答トークン数: {answer_tokens}")
total_output_tokens = thinking_tokens + answer_tokens
print(f"[ログ] 合計出力トークン数: {total_output_tokens}")
print(f"[ログ] 総計トークン数: {input_tokens + total_output_tokens}")

if name == "main":
try:
    # メインの非同期関数を実行
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nプログラムが中断されました。")