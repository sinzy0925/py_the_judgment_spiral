import json
import sys

def split_json_by_status(input_file='output.json'):
    """
    指定されたJSONファイルを読み込み、'status'キーの値に応じて、
    'success.json' と 'terminated.json' に分割して出力する。
    
    Args:
        input_file (str): 読み込むJSONファイルのパス。
    """
    try:
        # --- 1. 入力ファイルを読み込む ---
        print(f"'{input_file}' を読み込んでいます...")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"エラー: ファイル '{input_file}' の内容はJSON配列（リスト）ではありません。", file=sys.stderr)
            sys.exit(1)
            
        # --- 2. データを振り分けるための空のリストを用意 ---
        success_items = []
        terminated_items = []
        other_items_count = 0

        # --- 3. 全データをループして、statusに応じてリストに追加 ---
        for item in data:
            # itemが辞書型で、かつ'status'キーを持っているか確認
            if isinstance(item, dict) and 'status' in item:
                if item['status'] == 'success':
                    success_items.append(item)
                elif item['status'] == 'terminated':
                    terminated_items.append(item)
                else:
                    other_items_count += 1
            else:
                other_items_count += 1
        
        # --- 4. 'success.json' に書き込む ---
        success_filename = 'success.json'
        print(f"'{success_filename}' に {len(success_items)} 件のデータを書き込んでいます...")
        with open(success_filename, 'w', encoding='utf-8') as f:
            # indent=2 で見やすい形式に整形し、ensure_ascii=Falseで日本語の文字化けを防ぐ
            json.dump(success_items, f, indent=2, ensure_ascii=False)
            
        # --- 5. 'terminated.json' に書き込む ---
        terminated_filename = 'terminated.json'
        print(f"'{terminated_filename}' に {len(terminated_items)} 件のデータを書き込んでいます...")
        with open(terminated_filename, 'w', encoding='utf-8') as f:
            json.dump(terminated_items, f, indent=2, ensure_ascii=False)
            
        # --- 6. 処理結果のサマリーを表示 ---
        print("\n--- 処理完了 ---")
        print(f"読み込み総件数: {len(data)}件")
        print(f" -> '{success_filename}': {len(success_items)}件")
        print(f" -> '{terminated_filename}': {len(terminated_items)}件")
        if other_items_count > 0:
            print(f" -> 対象外（statusが'success'でも'terminated'でもないもの）: {other_items_count}件")
        print("------------------")

    except FileNotFoundError:
        print(f"エラー: ファイル '{input_file}' が見つかりません。", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"エラー: ファイル '{input_file}' は有効なJSON形式ではありません。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        file_to_split = sys.argv[1]
        split_json_by_status(file_to_split)
    else:
        split_json_by_status() # デフォルトは 'output.json'