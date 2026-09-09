import os
import json
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
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            title_list = res.json().get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "無題のデータベース")
    except Exception as e:
        print(f"DBタイトル取得エラー: {e}")
    return "データベース"


def get_database_properties(database_id):
    """データベースのプロパティ構造を取得する"""
    if not database_id:
        return []
    url = f"https://api.notion.com/v1/databases/{database_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
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
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        return res.status_code == 200
    except Exception as e:
        print(f"Notionページ作成エラー: {e}")
        return False


def add_url_to_notion(url_text):
    """送信されたURLを後で見るURLデータベースに保存する"""
    if NOTION_URL_DATABASE_ID:
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
            res = requests.post(notion_url, headers=headers, json=payload, timeout=5)
            if res.status_code == 200:
                return "後で見るURLデータベースに保存しました！"
        except Exception as e:
            print(f"URL保存エラー: {e}")
    return "URLの保存に失敗しました。"


def fetch_notion_context():
    """互換性維持のためのダミー"""
    return ""


def dynamic_search_and_fetch(user_message):
    """
    gemini-3.6-flash を使用して動的にNotionクエリを生成・実行する
    """
    if not NOTION_DATABASE_IDS:
        return "参照可能なデータベースが設定されていません。"

    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    db_schemas = {}
    for db_id in db_id_list:
        title = get_database_title(db_id)
        props = get_database_properties(db_id)
        db_schemas[title] = {
            "database_id": db_id,
            "properties": {name: p_type for name, p_type in props}
        }

    prompt = (
        "あなたはNotionのデータベース検索・クエリ生成エキスパートです。"
        "以下の『利用可能なDB構造』と『ユーザーの質問』を分析し、Notion APIのクエリ用JSONを一つだけ出力してください。\n"
        "出力は必ずコードブロック（```json ... ```）形式で行い、余計な文字は一切含めないでください。\n\n"
        "【JSONフォーマット例】\n"
        "{\n"
        '  "database_id": "対象DBの32桁ID",\n'
        '  "page_size": 5\n'
        "}\n\n"
        f"【利用可能なDB構造】\n{json.dumps(db_schemas, ensure_ascii=False)}\n\n"
        f"【ユーザーの質問】\n{user_message}"
    )

    try:
        res = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        
        text_resp = res.text
        if "```json" in text_resp:
            json_str = text_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in text_resp:
            json_str = text_resp.split("```")[1].split("```")[0].strip()
        else:
            json_str = text_resp.strip()

        query_data = json.loads(json_str)
        target_db_id = query_data.pop("database_id", None)

        if not target_db_id:
            return "対象のデータベースを特定できませんでした。"

        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        query_url = f"https://api.notion.com/v1/databases/{target_db_id}/query"
        response = requests.post(query_url, headers=headers, json=query_data, timeout=5)

        if response.status_code == 200:
            results = response.json().get("results", [])
            db_title = get_database_title(target_db_id)
            
            context_lines = [f"\n--- データベース: {db_title} (検索結果) ---"]
            for page in results:
                props = page.get("properties", {})
                row_parts = []
                for prop_name, prop_val in props.items():
                    v_type = prop_val.get("type")
                    val_str = ""
                    if v_type == "title":
                        t_list = prop_val.get("title", [])
                        if t_list: val_str = t_list[0].get("plain_text", "")
                    elif v_type == "rich_text":
                        r_list = prop_val.get("rich_text", [])
                        if r_list: val_str = r_list[0].get("plain_text", "")
                    elif v_type == "number":
                        val_str = str(prop_val.get("number", ""))
                    elif v_type == "select":
                        sel = prop_val.get("select")
                        if sel: val_str = sel.get("name", "")
                    elif v_type == "date":
                        date_obj = prop_val.get("date")
                        if date_obj: val_str = date_obj.get("start", "")

                    if val_str:
                        row_parts.append(f"{prop_name}: {val_str}")
                if row_parts:
                    context_lines.append(" | ".join(row_parts))
            
            return "\n".join(context_lines)
        else:
            return f"Notion検索エラー: {response.text}"

    except Exception as e:
        print(f"動的検索処理エラー: {e}")
        return f"検索処理中にエラーが発生しました: {str(e)}"


def generate_gemini_response(user_message, notion_context):
    """gemini-3.6-flash を使用して応答を生成"""
    try:
        dynamic_context = dynamic_search_and_fetch(user_message)

        prompt = (
            "あなたはユーザーのNotionデータを管理・参照するパーソナルアシスタントです。"
            "以下のNotion検索結果を参考にして、ユーザーの質問に日本語で簡潔に答えてください。\n\n"
            f"【Notion検索結果】\n{dynamic_context}\n\n"
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
