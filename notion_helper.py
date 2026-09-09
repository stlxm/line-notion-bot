import os
import requests
from google import genai

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")
NOTION_MEMO_DATABASE_ID = os.environ.get("NOTION_MEMO_DATABASE_ID", "")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")

# Google GenAI クライアントの初期化
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


def get_database_title(database_id):
    """Notionデータベースのタイトルを取得する"""
    if not database_id:
        return "無題のデータベース"
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
        print(f"DBタイトル取得エラー: {e}")
    return "データベース"


def get_database_properties(database_id):
    """データベースのプロパティ構造を取得する（手動データ追加用）"""
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
                if p_type in ["title", "rich_text", "number", "select", "multi_select", "date", "url"]:
                    valid_props.append((name, p_type))
            return valid_props
    except Exception as e:
        print(f"DBプロパティ取得エラー: {e}")
    return []


def create_notion_page(database_id, collected_data, prop_types):
    """対話型データ追加で収集した内容をNotionページとして作成する"""
    if not database_id:
        return False

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties = {}
    for prop_name, val in collected_data.items():
        p_type = prop_types.get(prop_name)
        if p_type == "title":
            properties[prop_name] = {"title": [{"text": {"content": val}}]}
        elif p_type == "rich_text":
            properties[prop_name] = {"rich_text": [{"text": {"content": val}}]}
        elif p_type == "number":
            try:
                properties[prop_name] = {"number": float(val)}
            except ValueError:
                properties[prop_name] = {"number": 0}
        elif p_type == "select":
            properties[prop_name] = {"select": {"name": val}}
        elif p_type == "date":
            properties[prop_name] = {"date": {"start": val}}
        elif p_type == "url":
            properties[prop_name] = {"url": val}

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
    """送信されたURLを後で見るURLデータベースに保存する"""
    if not NOTION_URL_DATABASE_ID:
        return "URL保存用のデータベースIDが設定されていません。"

    notion_url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": NOTION_URL_DATABASE_ID},
        "properties": {
            "URL": {"title": [{"text": {"content": url_text}}]}
        }
    }

    try:
        res = requests.post(notion_url, headers=headers, json=payload)
        if res.status_code == 200:
            return "後で見るURLデータベースに保存しました！"
        else:
            print(f"URL保存エラー ({res.status_code}): {res.text}")
            return f"URLの保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        print(f"URL保存通信エラー: {e}")
        return f"エラーが発生しました: {str(e)}"


def fetch_notion_context():
    """環境変数に登録されている複数のNotionデータベースからテキスト情報を抽出し、文字数制限付きでまとめる"""
    if not NOTION_DATABASE_IDS:
        return "参照可能なデータベースが設定されていません。"

    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    context_lines = []
    total_chars = 0
    MAX_CHARS = 10000

    for db_id in db_id_list:
        db_title = get_database_title(db_id)
        query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
        try:
            res = requests.post(query_url, headers=headers, json={"page_size": 30})
            if res.status_code == 200:
                results = res.json().get("results", [])
                context_lines.append(f"\n--- データベース: {db_title} ---")
                
                for page in results:
                    props = page.get("properties", {})
                    row_parts = []
                    for prop_name, prop_val in props.items():
                        v_type = prop_val.get("type")
                        val_str = ""
                        if v_type == "title":
                            t_list = prop_val.get("title", [])
                            if t_list:
                                val_str = t_list[0].get("plain_text", "")
                        elif v_type == "rich_text":
                            r_list = prop_val.get("rich_text", [])
                            if r_list:
                                val_str = r_list[0].get("plain_text", "")
                        elif v_type == "number":
                            val_str = str(prop_val.get("number", ""))
                        elif v_type == "select":
                            sel = prop_val.get("select")
                            if sel:
                                val_str = sel.get("name", "")
                        elif v_type == "date":
                            date_obj = prop_val.get("date")
                            if date_obj:
                                val_str = date_obj.get("start", "")

                        if val_str:
                            row_parts.append(f"{prop_name}: {val_str}")

                    if row_parts:
                        line = " | ".join(row_parts)
                        if total_chars + len(line) > MAX_CHARS:
                            context_lines.append("...(文字数制限のため省略)...")
                            break
                        context_lines.append(line)
                        total_chars += len(line)
        except Exception as e:
            print(f"DBデータ取得エラー ({db_id}): {e}")

    return "\n".join(context_lines)


def generate_gemini_response(user_message, notion_context):
    """Google GenAI SDK を使用してNotionデータを元に応答を生成（gemini-3.6-flash使用）"""
    try:
        prompt = (
            "あなたはユーザーのNotionデータを管理・参照する優秀なパーソナルアシスタントです。"
            "以下のNotionから取得したコンテキスト情報を参考にして、ユーザーからの質問に日本語で簡潔かつ正確に答えてください。\n\n"
            f"【Notionコンテキスト情報】\n{notion_context}\n\n"
            f"【ユーザーからの質問】\n{user_message}"
        )

        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Gemini APIエラー: {e}")
        return f"AIの応答生成中にエラーが発生しました: {str(e)}"
