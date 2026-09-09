import os
import requests
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def add_url_to_notion(url_string):
    if not NOTION_URL_DATABASE_ID:
        return "URL保存用のデータベースIDが設定されていません。"

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    jst = timezone(timedelta(hours=+9), "JST")
    now_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    payload = {
        "parent": {"database_id": NOTION_URL_DATABASE_ID},
        "properties": {
            "URL": {"title": [{"text": {"content": url_string}}]},
            "時間": {"rich_text": [{"text": {"content": now_str}}]}
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return f"後で見るURLに追加しました！\n\nURL: {url_string}\n時間: {now_str}"
        else:
            return f"URLの保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"


def get_database_title(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            title_list = res.json().get("title", [])
            title_text = "".join([t.get("plain_text", "") for t in title_list])
            if title_text:
                return title_text
    except Exception as e:
        print(f"DBタイトル取得エラー: {e}")
    return f"データベース ({db_id[:6]}...)"


def get_database_properties(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            props = res.json().get("properties", {})
            prop_list = []
            title_prop = None
            for p_name, p_info in props.items():
                p_type = p_info.get("type")
                if p_type == "title":
                    title_prop = (p_name, p_type)
                else:
                    prop_list.append((p_name, p_type))
            if title_prop:
                prop_list.insert(0, title_prop)
            return prop_list
    except Exception as e:
        print(f"プロパティ取得エラー: {e}")
    return []


def create_notion_page(db_id, collected_data, prop_types):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties_payload = {}
    for p_name, val in collected_data.items():
        p_type = prop_types.get(p_name, "rich_text")
        if p_type == "title":
            properties_payload[p_name] = {"title": [{"text": {"content": val}}]}
        elif p_type == "rich_text":
            properties_payload[p_name] = {"rich_text": [{"text": {"content": val}}]}
        elif p_type == "number":
            try:
                num_val = float(val) if "." in val else int(val)
                properties_payload[p_name] = {"number": num_val}
            except ValueError:
                properties_payload[p_name] = {"number": None}
        elif p_type == "select":
            properties_payload[p_name] = {"select": {"name": val}}
        elif p_type == "multi_select":
            items = [item.strip() for item in val.split(",")]
            properties_payload[p_name] = {"multi_select": [{"name": item} for item in items]}
        elif p_type == "url":
            properties_payload[p_name] = {"url": val}
        else:
            properties_payload[p_name] = {"rich_text": [{"text": {"content": val}}]}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties_payload
    }
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200


def fetch_notion_context():
    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    formatted_data = []

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    for db_id in db_id_list:
        try:
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            res = requests.post(url, headers=headers)
            if res.status_code != 200:
                continue

            pages = res.json().get("results", [])
            for page in pages:
                props = page.get("properties", {})
                item_info = []
                for prop_name, prop_val in props.items():
                    p_type = prop_val.get("type")
                    val_str = ""
                    if p_type == "title":
                        val_str = "".join([t.get("plain_text", "") for t in prop_val.get("title", [])])
                    elif p_type == "rich_text":
                        val_str = "".join([t.get("plain_text", "") for t in prop_val.get("rich_text", [])])
                    elif p_type == "number":
                        num = prop_val.get("number")
                        val_str = str(num) if num is not None else ""
                    elif p_type == "select":
                        select_obj = prop_val.get("select")
                        if select_obj:
                            val_str = select_obj.get("name", "")
                    elif p_type == "multi_select":
                        val_str = ", ".join([m.get("name", "") for m in prop_val.get("multi_select", [])])
                    elif p_type == "url":
                        val_str = prop_val.get("url", "")

                    if val_str:
                        item_info.append(f"{prop_name}: {val_str}")
                if item_info:
                    formatted_data.append("- " + " | ".join(item_info))
        except Exception as e:
            print(f"データベース取得エラー (ID: {db_id}): {e}")

    return "\n".join(formatted_data)


def generate_gemini_response(user_query, notion_context):
    system_instruction = (
        "あなたはユーザーのプライベート生活情報を把握している優秀なパーソナルアシスタントです。\n"
        "提供されたNotionデータベースの最新情報を参考に、ユーザーからの質問に正確かつ丁寧に回答してください。\n\n"
        "【回答ルール】\n"
        "1. 提供されたNotionデータの中に該当する情報がある場合は、分かりやすく要約して回答してください。\n"
        "2. 計算を求められた場合は数値をもとに正確に計算してください。\n"
        "3. 情報がない場合はNotionに該当する情報が登録されていませんと伝えてください。"
    )
    prompt = f"【Notionの最新データ】\n{notion_context}\n\n【ユーザーの質問】\n{user_query}"
    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )
    return response.text
