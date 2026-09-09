import os
import requests
import google.generativeai as genai

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


# Gemini APIの初期化
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def get_database_title(database_id):
    if not database_id:
        return "不明なデータベース"
    url = f"https://api.notion.com/v1/databases/{database_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            title_list = res.json().get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "無題のデータベース")
    except Exception as e:
        print(f"データベースタイトル取得エラー ({database_id}): {e}")
    return "データベース"


def get_database_properties(database_id):
    if not database_id:
        return []
    url = f"https://api.notion.com/v1/databases/{database_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            props = res.json().get("properties", {})
            valid_props = []
            for name, details in props.items():
                p_type = details.get("type")
                if p_type not in ["formula", "rollup", "created_time", "last_edited_time", "relation"]:
                    valid_props.append((name, p_type))
            return valid_props
    except Exception as e:
        print(f"プロパティ取得エラー ({database_id}): {e}")
    return []


def create_notion_page(database_id, collected_data, prop_types):
    if not database_id:
        return False

    url = "https://api.line.me/v2/bot/message/push" # プレースホルダー（実際は下のNotion APIエンドポイント）
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties = {}
    for prop_name, val_str in collected_data.items():
        p_type = prop_types.get(prop_name, "rich_text")
        if p_type == "title":
            properties[prop_name] = {"title": [{"text": {"content": val_str}}]}
        elif p_type == "rich_text":
            properties[prop_name] = {"rich_text": [{"text": {"content": val_str}}]}
        elif p_type == "number":
            try:
                num_val = float(val_str)
                properties[prop_name] = {"number": num_val}
            except ValueError:
                properties[prop_name] = {"number": 0}
        elif p_type == "select":
            properties[prop_name] = {"select": {"name": val_str}}
        elif p_type == "multi_select":
            tags = [t.strip() for t in val_str.replace("、", ",").split(",") if t.strip()]
            properties[prop_name] = {"multi_select": [{"name": tag} for tag in tags]}
        elif p_type == "date":
            properties[prop_name] = {"date": {"start": val_str}}
        elif p_type == "checkbox":
            is_true = val_str.lower() in ["true", "はい", "yes", "1", "on"]
            properties[prop_name] = {"checkbox": is_true}
        elif p_type == "url":
            properties[prop_name] = {"url": val_str}

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"Notionページ作成エラー: {e}")
        return False


def add_url_to_notion(url_text):
    if not NOTION_URL_DATABASE_ID:
        return "URL保存用のデータベースIDが設定されていません。"

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": NOTION_URL_DATABASE_ID},
        "properties": {
            "タイトル": {"title": [{"text": {"content": url_text}}]},
            "URL": {"url": url_text}
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return "URLをNotionのデータベースに保存しました！"
        else:
            print(f"URL保存エラー ({res.status_code}): {res.text}")
            return f"URLの保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        print(f"URL保存通信エラー: {e}")
        return f"エラーが発生しました: {str(e)}"


def fetch_notion_context():
    """連携されているすべてのNotionデータベースからデータを取得してテキスト化する"""
    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    if not db_id_list:
        return "データベースが連携されていません。"

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    all_context_lines = []

    for db_id in db_id_list:
        db_title = get_database_title(db_id)
        query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
        try:
            res = requests.post(query_url, headers=headers, json={})
            if res.status_code == 200:
                results = res.json().get("results", [])
                all_context_lines.append(f"\n--- データベース: {db_title} ---")
                for page in results:
                    props = page.get("properties", {})
                    row_details = []
                    for prop_name, prop_val in props.items():
                        p_type = prop_val.get("type")
                        val_str = ""
                        if p_type == "title":
                            t_list = prop_val.get("title", [])
                            val_str = "".join([t.get("plain_text", "") for t in t_list])
                        elif p_type == "rich_text":
                            r_list = prop_val.get("rich_text", [])
                            val_str = "".join([r.get("plain_text", "") for r in r_list])
                        elif p_type == "number":
                            val_str = str(prop_val.get("number", ""))
                        elif p_type == "select":
                            sel = prop_val.get("select")
                            val_str = sel.get("name", "") if sel else ""
                        elif p_type == "date":
                            d = prop_val.get("date")
                            val_str = d.get("start", "") if d else ""
                        elif p_type == "checkbox":
                            val_str = str(prop_val.get("checkbox", ""))
                        
                        if val_str:
                            row_details.append(f"{prop_name}: {val_str}")
                    if row_details:
                        all_context_lines.append(" | ".join(row_details))
        except Exception as e:
            print(f"コンテキスト取得中のエラー ({db_id}): {e}")

    context_text = "\n".join(all_context_lines)

    # 🔍 デバッグ用ログ出力（RenderのLogsタブで確認できます）
    print(f"DEBUG - 取得したNotionコンテキスト:\n{context_text}")

    return context_text


def generate_gemini_response(user_message, context):
    """取得したNotionデータをコンテキストとしてGeminiに回答を生成させる"""
    if not GEMINI_API_KEY:
        return "Gemini APIキーが設定されていません。"

    try:
        model = genai.GenerativeModel("gemini-3.6-flash")
        prompt = (
            "あなたは優秀な家計簿・パーソナルアシスタントです。\n"
            "以下のNotionデータベースの内容（コンテキスト）を基にして、ユーザーの質問に日本語で親切に答えてください。\n"
            "情報が見つからない場合は「該当する情報が登録されていません」と答えてください。\n\n"
            f"【Notionデータ】\n{context}\n\n"
            f"【ユーザーの質問】\n{user_message}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini生成エラー: {e}")
        return f"AIの応答生成中にエラーが発生しました: {str(e)}"
