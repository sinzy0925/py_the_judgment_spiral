# gemini_search_app_new_sdk.py (修正後)

import os
import sys
import time
import argparse
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import sys

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
        print("\nエラー: _blocking_call_to_gemini に有効なAPIキーが渡されませんでした。")
        return None, None
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"\nエラー: APIクライアントの初期化に失敗しました: {e}", file=sys.stderr)
        # エラー発生時はNoneを返して異常を伝える
        return None, None
        
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=True
        )
    )

    print(f"'{full_contents.splitlines()[0]}' について、AIが思考を開始します...")
    
    api_call_start_time = time.time() 
    try:
        stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
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
                    res = part.text.replace("```json", "").replace("```", "")
                    print(res, end="", flush=True)
        
        print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。")
        return thinking_text, answer_text
    
    except Exception as e:
        # ストリーム処理中のエラーも標準エラー出力へ
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
    args = parser.parse_args()

    start_time = time.time()
    
    # <<< ここからロジックを修正 >>>
    full_contents = ""

    if args.prompt_file:
        # --- --prompt-fileが指定された場合（改善後実行）のルート ---
        try:
            print(f"INFO: プロンプトファイル '{args.prompt_file}' を読み込みます。")
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                # ファイルの内容をそのまま最終的なプロンプトとして使用
                full_contents = f.read()
        except FileNotFoundError:
            print(f"エラー: プロンプトファイルが見つかりません: {args.prompt_file}", file=sys.stderr)
            sys.exit(1) # エラーが見つかったら異常終了
    else:
        # --- --prompt-fileが指定されていない場合（初回実行）のルート ---
        print("INFO: デフォルトのプロンプトテンプレートを使用します。")
        prompt_template="""
# 調査対象企業
- {company_name}

# 上記の企業を以下のJSON形式で出力してください。

# 出力形式 (JSON)
```json
{{
  "companyName": "企業の正式名称",
  "companyStatus": "活動中、休眠中、清算中など、企業の現在の活動状況",
  "officialUrl": "公式ウェブサイトの完全なURL",
  "address": "登記上の本社の所在地",
  "industry": "主要な事業領域・業界（例: ソフトウェア開発、飲食業など）",
  "email": "公開されている代表問い合わせ用のメールアドレス",
  "tel": "代表電話番号",
  "fax": "代表FAX番号",
  "capital": "資本金の額（単位も明記）",
  "founded": "会社設立年月日（例: 2006年3月17日）",
  "businessSummary": "どのような顧客に、どのような製品やサービスを提供しているか、具体的な事業内容の要約",
  "strengths": "企業の技術的優位性、市場でのポジション、主要な株主構成、特許など、企業の強みや特徴を具体的に記述"
}}
```"""

        before="""
# 実行命令
上記の指示に厳密に従い、調査を実行し、結果をJSON形式で出力してください。

////


以下の企業について、公開情報から徹底的に調査し、結果を下記のJSON形式で厳密に出力してください。

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
```"""
        # デフォルトテンプレートに企業名を埋め込む
        full_contents = prompt_template.format(company_name=args.query)

    if not full_contents:
        print("エラー: 実行するプロンプトが空です。", file=sys.stderr)
        sys.exit(1)
    # <<< ここまでロジックを修正 >>>

    print(f"プロンプト: \n{full_contents[:200]}...")

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
    # メイン処理でキーが取得できない場合は致命的エラーとして終了
    if not main_call_key:
        print("エラー: メイン処理用のAPIキーを取得できませんでした。", file=sys.stderr)
        sys.exit(1)
        
    key_info = api_key_manager.last_used_key_info 
    print(f"[INFO] メイン処理用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。")
    thinking_text, answer_text = await asyncio.to_thread(
        _blocking_call_to_gemini, main_call_key, full_contents
    )

    # thinking_text と answer_text がNoneの場合、API呼び出しでエラーが起きている
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
    print(f"\n総実行時間: {end_time - start_time:.2f}秒")
    print(f"[ログ] 入力トークン数: {input_tokens}")
    print(f"[ログ] 思考トークン数: {thinking_tokens}")
    print(f"[ログ] 回答トークン数: {answer_tokens}")
    total_output_tokens = thinking_tokens + answer_tokens
    print(f"[ログ] 合計出力トークン数: {total_output_tokens}")
    print(f"[ログ] 総計トークン数: {input_tokens + total_output_tokens}")

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