import sys
import subprocess
import json
from google import genai
import re
import os

# Gemini APIキーを環境変数から設定
# genai.configure(api_key="YOUR_GEMINI_API_KEY")

def create_evaluation_prompt(log_output: str) -> str:
    """
    キャプチャしたログを元に、AI評価用のプロンプトを生成する関数。
    """
    # (この関数の内容は変更ありません)
    return f"""
あなたは、AIのパフォーマンスを多角的に分析する専門の評価者です。
以下の実行ログを慎重に分析し、提供されたJSONスキーマに従って評価レポートを作成してください。

評価のポイント：
1.  **品質評価**: 情報の正確性、推論の妥当性、指示への忠実性を評価します。
2.  **性能評価**: 実行時間とトークン数から、コストパフォーマンスを評価します。
3.  **プロンプト改善提案**: ログの内容に基づき、元のプロンプトをさらに改善するための具体的で建設的な提案をしてください。もし改善の必要がなければ、その理由を述べてください。

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
      {{
        "criterion": "プロンプト指示への忠実性",
        "score": "25/25",
        "analysis": "JSON形式の遵守、全項目の網羅性などに関する分析"
      }},
      {{
        "criterion": "情報の正確性（ファクトチェック）",
        "score": "25/25",
        "analysis": "抽出された情報の事実との整合性に関する分析"
      }},
      {{
        "criterion": "高度な推論・分析能力",
        "score": "25/25",
        "analysis": "情報の矛盾の発見、状況の推論など、表面的な検索を超えた能力の分析"
      }},
      {{
        "criterion": "網羅性と例外処理",
        "score": "25/25",
        "analysis": "要求された全項目への回答と、情報がない場合の処理に関する分析"
      }}
    ]
  }},
  "performanceMetrics": {{
    "executionTimeSeconds": "ログから抽出した総実行時間（float）",
    "tokens": {{
      "input": "ログから抽出した入力トークン数（int）",
      "output": "ログから抽出した合計出力トークン数（int）",
      "total": "ログから抽出した総計トークン数（int）"
    }},
    "analysis": "速度とコストの観点からのパフォーマンス分析"
  }},
  "promptImprovementSuggestions": "ログの分析に基づいた、元のプロンプトに対する具体的で建設的な改善提案。改善不要の場合はその旨を記述。"
}}
```
"""

def main():
    if len(sys.argv) < 2:
        print("使い方: python evaluation_runner.py <評価したい企業名>")
        sys.exit(1)
    company_name = " ".join(sys.argv[1:])

    target_script = "gemini_search_app_new_sdk.py"

    print(f"--- '{target_script}' を実行してログを収集中... ---")
    try:
        # ===== ここからが修正箇所 =====
        # 実行する子プロセスの環境変数を設定
        process_env = os.environ.copy()
        # Pythonの標準入出力のエンコーディングをUTF-8に強制する
        process_env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, target_script, company_name],
            capture_output=True,
            text=True,
            check=True,
            # 子プロセスがUTF-8で出力するので、こちらもUTF-8で受け取る
            encoding='utf-8',
            # 万が一、それでもデコードできない文字があった場合にエラーを回避する
            errors='replace',
            env=process_env
        )
        # ===== ここまでが修正箇所 =====

        log_output = result.stdout
        print(f"--- ログ収集完了 ---")

    except subprocess.CalledProcessError as e:
        print(f"エラー: '{target_script}' の実行に失敗しました。")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"エラー: '{target_script}' が見つかりません。同じディレクトリにありますか？")
        sys.exit(1)

    print("\n--- Geminiにログの評価を依頼中... ---")
    try:
        client = genai.Client()
        evaluation_prompt = create_evaluation_prompt(log_output)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=evaluation_prompt
        )

        print("\n--- 評価結果 ---")
        json_text = response.text.strip()
        match = re.search(r'```json\s*(\{.*?\})\s*```', json_text, re.DOTALL)
        if match:
            json_text = match.group(1)
        
        parsed_json = json.loads(json_text)
        print(json.dumps(parsed_json, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\nエラー: Geminiへの評価依頼中にエラーが発生しました。: {e}")
        print("AIからの生のレスポンス:", response.text if 'response' in locals() else "N/A")

if __name__ == "__main__":
    main()