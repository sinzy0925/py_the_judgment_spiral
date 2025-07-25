import sys
import os
import time
import argparse
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# `fetch_url_content` は非同期を前提としないため、元の同期的な実装に戻します。
# 呼び出し側で to_thread を使って非同期化します。
def fetch_url_content(url: str) -> str:
    """
    指定されたURLからHTMLコンテンツを取得し、文字列として返す。
    """
    # この関数は advanced_evaluation_runner からは使われませんが、
    # 単体で動かす場合に備えて残しておきます。
    # ただし、このファイル自体が非同期アプリになるため、直接の呼び出しは想定しません。
    pass 

def _blocking_call_to_gemini(client, full_contents):
    """
    GeminiへのAPI呼び出しとストリーム処理という、すべての同期的（ブロッキング）
    な処理をまとめて実行する関数。この関数全体が別スレッドで実行される。
    """
    
    # ----------------------------------------------------
    # 1. モデルとツールの設定 (同期的)
    # ----------------------------------------------------
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=True
        )
    )

    # ----------------------------------------------------
    # 2. ストリーム生成 (同期的・ブロッキング)
    # ----------------------------------------------------
    print(f"'{full_contents.splitlines()[0]}' について、AIが思考を開始します...")
    try:
        stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=full_contents,
            config=config,
        )
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        return None, None
    
    # ----------------------------------------------------
    # 3. ストリーム処理 (同期的・ブロッキング)
    # ----------------------------------------------------
    api_call_start_time = time.time()
    print(f"[{time.time() - api_call_start_time:.2f}s] API呼び出し完了、ストリーム受信待機中...")
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

            for part in chunk.candidates[0].content.parts:
                if not part.text:
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
        print(f"\nストリームの処理中にエラーが発生しました: {e}")
        return None, None

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

    if args.prompt_file:
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        full_contents = prompt_template.replace("{company_name}", question)
    else:
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
```
"""
        full_contents = prompt_template.format(company_name=question)

    print(f"プロンプト: \n{full_contents[:200]}...")
    
    input_tokens = 0
    thinking_tokens = 0
    answer_tokens = 0
    
    try:
        # Clientの初期化は同期的で良い
        client = genai.Client()
        
        # ----------------------------------------------------
        # ★【修正箇所１】入力トークン計算を別スレッドで実行
        # ----------------------------------------------------
        await asyncio.sleep(1)
        input_token_response = await asyncio.to_thread(
            client.models.count_tokens,
            model='gemini-2.5-flash', 
            contents=full_contents
        )
        input_tokens = input_token_response.total_tokens

        # ----------------------------------------------------
        # ★【修正箇所２】Geminiへの全処理を別スレッドで実行
        # ----------------------------------------------------
        thinking_text, answer_text = await asyncio.to_thread(
            _blocking_call_to_gemini,
            client,
            full_contents
        )

        # ----------------------------------------------------
        # ★【修正箇所３】出力トークン計算を別スレッドで実行
        # ----------------------------------------------------
        if thinking_text:
            await asyncio.sleep(1)
            thinking_token_response = await asyncio.to_thread(
                client.models.count_tokens,
                model='gemini-2.5-flash',
                contents=thinking_text
            )
            thinking_tokens = thinking_token_response.total_tokens
        if answer_text:
            await asyncio.sleep(1)
            answer_token_response = await asyncio.to_thread(
                client.models.count_tokens,
                model='gemini-2.5-flash',
                contents=answer_text
            )
            answer_tokens = answer_token_response.total_tokens

        print("\n------------------------------")
    
    except Exception as e:
        if 'api_key' in str(e).lower() or 'credential' in str(e).lower():
             print("\nエラー: APIキーが見つからないか、無効です。")
             print("環境変数 'GEMINI_API_KEY' が正しく設定されているか確認してください。")
        else:
            print(f"\nメイン処理で予期せぬエラーが発生しました: {e}")

    end_time = time.time()
    print(f"\n総実行時間: {end_time - start_time:.2f}秒")
    print(f"[ログ] 入力トークン数: {input_tokens}")
    print(f"[ログ] 思考トークン数: {thinking_tokens}")
    print(f"[ログ] 回答トークン数: {answer_tokens}")
    total_output_tokens = thinking_tokens + answer_tokens
    print(f"[ログ] 合計出力トークン数: {total_output_tokens}")
    print(f"[ログ] 総計トークン数: {input_tokens + total_output_tokens}")


if __name__ == "__main__":
    try:
        # メインの非同期関数を実行
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nプログラムが中断されました。")