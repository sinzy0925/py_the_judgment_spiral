import sys
import os
import time
import urllib.request
from urllib.error import URLError, HTTPError
from google import genai
from google.genai import types
import argparse
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

def fetch_url_content(url: str) -> str:
    """
    指定されたURLからHTMLコンテンツを取得し、文字列として返す。

    Args:
        url (str): 情報を取得したいウェブページの完全なURL。

    Returns:
        str: 取得したHTMLコンテンツ。取得に失敗した場合はエラーメッセージを返す。
    """
    print(f"\n--- ツール実行: fetch_url_content(url='{url}') ---")
    try:
        # タイムアウトを設定し、偽装ヘッダーを追加してブロックを回避
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            encoding = response.headers.get_content_charset('utf-8')
            html_content = response.read().decode(encoding, errors='replace')
            # 非常に長いコンテンツはAIを混乱させるため、要点を返す
            # ここでは簡単のため、先頭の2000文字に制限
            summary = f"成功: {url} の内容の先頭2000文字を取得しました。"
            print(summary)
            return html_content[:2000]
    except (HTTPError, URLError) as e:
        error_message = f"失敗: URL '{url}' の取得中にエラー。理由: {e}"
        print(error_message)
        return error_message
    except Exception as e:
        error_message = f"失敗: URL '{url}' の取得中に予期せぬエラー。詳細: {e}"
        print(error_message)
        return error_message
        
def ask_gemini_with_thinking_stream(client: genai.Client, contents: str):
    """
    思考プロセスとGoogle検索を有効にしたGeminiモデルで、
    回答生成のストリームを返す関数
    """
    print(f"'{contents.splitlines()[0]}' について、AIが思考を開始します...")
    
    try:
        # モデルの設定
        config = types.GenerateContentConfig(
            # 外部ツールとしてGoogle検索を有効化
            tools=[
                types.Tool(
                    google_search=types.GoogleSearch(),
                    url_context=types.UrlContext()
                )            
            ],
            # 思考プロセスの設定
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,    # 動的思考をON
                include_thoughts=True  # レスポンスに思考ログを含める
            )
        )
        
        # ストリーミングでコンテンツ生成をリクエスト
        time.sleep(1)
        stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=contents,
            config=config,
        )
        return stream

    except Exception as e:
        if 'api_key' in str(e).lower() or 'credential' in str(e).lower():
             print("\nエラー: APIキーが見つからないか、無効です。")
             print("環境変数 'GEMINI_API_KEY' が正しく設定されているか確認してください。")
        else:
            print(f"\nエラーが発生しました: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企業情報を検索するGeminiアプリ")
    parser.add_argument("query", help="検索対象の企業名と住所")
    parser.add_argument("--prompt-file", help="プロンプトが記述されたテキストファイルのパス")
    args = parser.parse_args()

    start_time = time.time()
    
    # 質問文を作成
    question = args.query

    # プロンプトの決定
    if args.prompt_file:
        with open(args.prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        # ===== ここからが修正箇所 =====
        # AIが生成したプロンプトは '{' や '}' をそのまま含んでいる可能性が高いため、
        # 安全な .replace() を使ってプレースホルダーを置換する
        full_contents = prompt_template.replace("{company_name}", question)
        # ===== ここまでが修正箇所 =====
    else:
        # デフォルトのプロンプト（人間が管理しているので安全）
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
        # こちらは波括弧 {{ }} が正しくエスケープされているので .format() で安全
        full_contents = prompt_template.format(company_name=question)

    print(f"プロンプト: \n{full_contents[:200]}...") # 長すぎるので冒頭だけ表示
    
    input_tokens = 0
    thinking_tokens = 0
    answer_tokens = 0
    client = None

    try:
        client = genai.Client()
        # 入力トークン数を計算して保存
        time.sleep(1)
        input_token_response = client.models.count_tokens(model='gemini-2.5-flash', contents=full_contents)
        input_tokens = input_token_response.total_tokens
    except Exception as e:
        print(f"[ログ] クライアントの初期化または入力トークン数の計算に失敗しました: {e}")

    # AIからストリームを取得
    api_call_start_time = time.time()
    stream = ask_gemini_with_thinking_stream(client, full_contents) if client else None

    # ストリームを処理して思考ログと回答を表示
    if stream:
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
                    
                    # 思考パートの場合
                    if hasattr(part, 'thought') and part.thought:
                        thinking_text += part.text
                        if is_first_thought:
                            print("\n[思考プロセス]:")
                            is_first_thought = False
                        print(part.text, end="", flush=True)
                    
                    # 回答パートの場合
                    else:
                        answer_text += part.text
                        if is_first_answer:
                            # 思考ログと回答の間にスペースを確保
                            print("\n\n[最終的な回答]:")
                            is_first_answer = False
                        res = part.text.replace("```json", "").replace("```", "")
                        print(res, end="", flush=True)
            
            print(f"\n[{time.time() - api_call_start_time:.2f}s] 全ストリーム受信完了。")
            
            if client:
                try:
                    # 思考トークン数を計算
                    if thinking_text:
                        time.sleep(1)
                        thinking_token_response = client.models.count_tokens(model='gemini-2.5-flash', contents=thinking_text)
                        thinking_tokens = thinking_token_response.total_tokens
                    # 回答トークン数を計算
                    if answer_text:
                        time.sleep(1)
                        answer_token_response = client.models.count_tokens(model='gemini-2.5-flash', contents=answer_text)
                        answer_tokens = answer_token_response.total_tokens
                except Exception as e:
                    print(f"[ログ] 出力トークン数の計算に失敗しました: {e}")

            print("\n------------------------------") # 最後に改行
        
        except Exception as e:
            print(f"\nストリームの処理中にエラーが発生しました: {e}")

    end_time = time.time()
    print(f"\n総実行時間: {end_time - start_time:.2f}秒")
    print(f"[ログ] 入力トークン数: {input_tokens}")
    print(f"[ログ] 思考トークン数: {thinking_tokens}")
    print(f"[ログ] 回答トークン数: {answer_tokens}")
    total_output_tokens = thinking_tokens + answer_tokens
    print(f"[ログ] 合計出力トークン数: {total_output_tokens}")
    print(f"[ログ] 総計トークン数: {input_tokens + total_output_tokens}")