import os
import sys
import time
import argparse
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
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

    print(f"'{full_contents.splitlines()[0]}' について、AIが思考を開始します...", file=sys.stderr)
    
    api_call_start_time = time.time() 
    try:
        stream = client.models.generate_content_stream(
            model='gemini-2.5-flash', # モデル名を必要に応じて変更してください
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
    
    print("\n--- AIの思考プロセスと回答 ---", file=sys.stderr)
    try:
        for chunk in stream:
            if not first_chunk_received:
                first_chunk_received = True
                print(f"[{time.time() - api_call_start_time:.2f}s] API呼び出し成功、最初のチャンクを受信しました。", file=sys.stderr)

            if not chunk.candidates:
                continue

            for part in chunk.candidates[0].content.parts:
                if not hasattr(part, 'text') or not part.text:
                    continue
                
                if hasattr(part, 'thought') and part.thought:
                    thinking_text += part.text
                    if is_first_thought:
                        print("\n[思考プロセス]:", file=sys.stderr)
                        is_first_thought = False
                    print(part.text, end="", flush=True, file=sys.stderr)
                else:
                    answer_text += part.text
                    if is_first_answer:
                        #print("\n\n[最終的な回答プレビュー]:", file=sys.stderr)
                        is_first_answer = False
                    #print(part.text, end="", flush=True, file=sys.stderr)
        print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。", file=sys.stderr)
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
    #parser.add_argument("--output-file", "-o", help="結果を追記するJSONファイルのパス")
    args = parser.parse_args()

    start_time = time.time()
    
    full_contents = ""

    if args.prompt_file:
        try:
            print(f"INFO: プロンプトファイル '{args.prompt_file}' を読み込みます。", file=sys.stderr)
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                full_contents = f.read()
        except FileNotFoundError:
            print(f"エラー: プロンプトファイルが見つかりません: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
    else:
        print("INFO: デフォルトのプロンプトテンプレートを使用します。", file=sys.stderr)
        prompt_template="""
# 調査対象企業
- {company_name}

# 上記の企業について、ルールに従い、以下のJSON形式で出力してください。

# 厳守すべきルール
1. 入力された、会社名　住所の情報から、出力内容を特定してください。
2. ファクトチェックの徹底:名称と住所を基に、正しい業種を再検証してください。
3. 欠損情報の扱い:調査しても情報が見つからない場合は、項目の値を `不明` としてください。
4. 以下の４つの主要調査項目のうち、２項目が見つからなければ、即座に調査を中止し、下記の「調査中断レポート」を出力してください。
   主要調査項目（４項目）：`officialUrl`, `industry`, `email`, `tel`
5. 上記4.に抵触しなかった場合のみ、収集した情報を下記の「通常調査レポート」の形式で出力してください。

# 出力形式 (JSON)
# 調査中断レポート
```json
{{
  "status": "terminated",
  "error": "Required information could not be found.",
  "message": "主要調査項目のうち2項目以上が不明だったため、調査を中断しました。",
  "targetCompany": "{company_name}"
}}```

# 通常調査レポート
```json
{{
  "status": "success",
  "data": {{
    "companyName": "企業の正式名称（string）",
    "companyStatus": "企業の現在の状況（例：活動中, 閉鎖, 不明）（string）",
    "address": "本社の所在地（string）",
    "officialUrl": "公式サイトのURL（string）",
    "industry": "主要な業種（string）",
    "email": "メールアドレス（string）",
    "tel": "代表電話番号（string）",
    "fax": "代表FAX番号（string）",
    "capital": "資本金（string）",
    "founded": "設立年月（string）",
    "businessSummary": "事業内容の簡潔な要約（string）",
    "strengths": "企業の強みや特徴（string）"
  }}
}}```
"""
        full_contents = prompt_template.format(company_name=args.query)

    if not full_contents:
        print("エラー: 実行するプロンプトが空です。", file=sys.stderr)
        sys.exit(1)

    input_tokens, thinking_tokens, answer_tokens = 0, 0, 0

    input_key = await api_key_manager.get_next_key()
    if input_key:
        key_info = api_key_manager.last_used_key_info 
        print(f"[INFO] 入力トークン計算用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。", file=sys.stderr)
        input_token_response = await asyncio.to_thread(
            _blocking_count_tokens, input_key, 'gemini-2.5-flash', full_contents
        )
        if input_token_response:
            input_tokens = input_token_response.total_tokens

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

    if thinking_text:
        thinking_key = await api_key_manager.get_next_key()
        if thinking_key:
            key_info = api_key_manager.last_used_key_info 
            print(f"[INFO] 思考トークン計算用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。", file=sys.stderr)
            thinking_token_response = await asyncio.to_thread(
                _blocking_count_tokens, thinking_key, 'gemini-2.5-flash', thinking_text
            )
            if thinking_token_response:
                thinking_tokens = thinking_token_response.total_tokens

    # <--- ▼▼▼ ここからが出力形式を修正した箇所です ▼▼▼ --->

    if answer_text:
        answer_key = await api_key_manager.get_next_key()
        if answer_key:
            key_info = api_key_manager.last_used_key_info 
            print(f"[INFO] 回答トークン計算用にキー (index: {key_info['index']}, ...{key_info['key_snippet']}) を取得。", file=sys.stderr)
            answer_token_response = await asyncio.to_thread(
                _blocking_count_tokens, answer_key, 'gemini-2.5-flash', answer_text
            )
            if answer_token_response:
                answer_tokens = answer_token_response.total_tokens

    end_time = time.time()

    # time_tokens オブジェクトを作成
    time_tokens_info = {
        "time": round(end_time - start_time, 2),
        "input_tokens": input_tokens,
        "thinking_tokens": thinking_tokens,
        "answer_tokens": answer_tokens,
        "total_tokens": input_tokens + thinking_tokens + answer_tokens
    }

    final_output = {}
    try:
        # answer_textからJSON部分を抽出
        json_str = answer_text.replace("```json", "").replace("```", "").strip()
        if not json_str:
            raise json.JSONDecodeError("APIからの応答が空です", json_str, 0)
            
        # JSON文字列をPython辞書に変換
        final_output = json.loads(json_str)

    except json.JSONDecodeError as e:
        print(f"エラー: API応答のJSON解析に失敗しました: {e}", file=sys.stderr)
        final_output = {
            "status": "error",
            "error": "Failed to parse API response",
            "message": "APIからの応答をJSONとして解析できませんでした。",
            "raw_response": answer_text
        }

    # 最終的な辞書にtime_tokens情報を追加
    final_output["time_tokens"] = time_tokens_info

    print(json.dumps(final_output, indent=2, ensure_ascii=False))
    # --- ▼▼▼ ここからがファイル出力と追記のロジックです ▼▼▼ ---

    # --output-file 引数が指定されている場合、ファイルに追記する
    output_file='output.json'
    results_list = []
    try:
        # 既存のファイルがあれば読み込む
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                # ファイルが空でなければJSONとして読み込む
                content = f.read()
                if content.strip():
                    results_list = json.loads(content)
                # 読み込んだデータがリストでなければ、警告して新しいリストで上書きする
                if not isinstance(results_list, list):
                    print(f"警告: 出力ファイル {args.output_file} はJSON配列形式ではありません。新しいリストで上書きします。", file=sys.stderr)
                    results_list = []
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"警告: 出力ファイル {args.output_file} の読み込みに失敗しました。新しいファイルを作成します。", file=sys.stderr)
        results_list = []

    # 今回の結果をリストに追加
    results_list.append(final_output)

    # リスト全体をファイルに書き込む（上書き）
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_list, f, indent=2, ensure_ascii=False)
        print(f"\n結果を {output_file} に追記しました。", file=sys.stderr)
    except IOError as e:
        print(f"\nエラー: ファイル '{output_file}' への書き込みに失敗しました: {e}", file=sys.stderr)

    # 常に今回の結果を標準出力にも表示する
    #print(json.dumps(results_list, f, indent=2, ensure_ascii=False))

    # --- ▲▲▲ ここまでがファイル出力と追記のロジックです ▲▲▲ ---

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
