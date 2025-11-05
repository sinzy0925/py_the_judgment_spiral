import os
import sys
import time
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import re

from api_key_manager import api_key_manager

load_dotenv()

def _blocking_call_to_gemini(api_key: str, full_contents: str):
    if not api_key:
        print("\nエラー: _blocking_call_to_gemini に有効なAPIキーが渡されませんでした。", file=sys.stderr)
        return None, None
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"\nエラー: APIクライアントの初期化に失敗しました: {e}", file=sys.stderr)
        return None, None
        
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )

    print(f"'{full_contents.splitlines()[0]}' で始まるプロンプトについて、AIが処理を開始します...", file=sys.stderr)
    
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
    
    answer_text = ""
    print("\n--- AIの回答ストリーム受信中 ---", file=sys.stderr)
    try:
        for chunk in stream:
            if not chunk.candidates: continue
            for part in chunk.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    answer_text += part.text
        
        print(answer_text, end="")
        print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。", file=sys.stderr)
        return "Thinking process is currently disabled.", answer_text
    
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
    input_count = len(companies)

    # <<< プロンプトの改善 >>>
    prompt_template="""
# 指示
あなたは、入力された複数の会社名と住所の情報から、それぞれの業種を特定するプロフェッショナルです。
入力された全ての企業について、Google検索ツールを駆使して調査し、結果を**必ず指定されたJSON形式で厳密に出力**してください。

# 調査対象企業リスト
{company_list}

# 出力に関する厳格なルール
1.  **出力は必ず ` ```json ` で始まり、 ` ``` ` で終わるマークダウンのJSONコードブロックの中に記述してください。**
2.  JSONの文字列値にバックスラッシュ(`\`)やその他のエスケープが必要な文字を含めないでください。
3.  不明な項目は、無理に情報を探さず、正直に「不明」と記載してください。

# 出力形式 (JSON)
```json
{{
  "status": "success",
  "count": {input_count},
  "data": [
    {{
      "url": "公式サイトのURL（string）",
      "companyName": "企業の正式名称（string）",
      "email": "メールアドレス（string）",
      "mail_form": "メールフォームのURL（string）"
    }}
  ]
}}```
"""
    full_contents = prompt_template.format(
        company_list=query_from_stdin,
        input_count=input_count
    )

    print(f"プロンプトを生成しました。文字数: {len(full_contents)}", file=sys.stderr)

    main_call_key = await api_key_manager.get_next_key()
    if not main_call_key:
        print("エラー: メイン処理用のAPIキーを取得できませんでした。", file=sys.stderr)
        sys.exit(1)
        
    key_info = api_key_manager.last_used_key_info 
    print(f"[INFO] メイン処理用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。", file=sys.stderr)

    thinking_text, answer_text = await asyncio.to_thread(
        _blocking_call_to_gemini, main_call_key, full_contents
    )

    if thinking_text is None and answer_text is None:
        print("エラー: Geminiからの応答取得に失敗しました。処理を中断します。", file=sys.stderr)
        sys.exit(1)

    print("\n------------------------------", file=sys.stderr)
    end_time = time.time()
    print(f"総実行時間: {end_time - start_time:.2f}秒", file=sys.stderr)

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