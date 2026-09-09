import os
import json
import requests
from datetime import datetime, timezone, timedelta
from linebot.v3.messaging import FlexMessage, FlexContainer

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_MEMO_DATABASE_ID = os.environ.get("NOTION_MEMO_DATABASE_ID", "")


def add_memo_to_notion(memo_text):
    """NotionのメモDBへ新しいメモを追加します"""
    if not NOTION_MEMO_DATABASE_ID:
        return "メモDB IDが設定されていません。Renderの環境変数 NOTION_MEMO_DATABASE_ID を設定してください。"

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    jst = timezone(timedelta(hours=+9), "JST")
    today_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    payload = {
        "parent": {"database_id": NOTION_MEMO_DATABASE_ID},
        "properties": {
            "メモ": {"title": [{"text": {"content": memo_text}}]},
            "日付": {"date": {"start": today_str}}
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return f"メモを保存しました！\n\n【内容】{memo_text}\n【日時】{today_str}"
        else:
            return f"メモの保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        return f"通信エラーが発生しました: {str(e)}"


def get_memos_from_notion():
    """NotionのメモDBから現在残っているメモ一覧（ページIDとタイトル）を取得します"""
    if not NOTION_MEMO_DATABASE_ID:
        return []

    url = f"https://api.notion.com/v1/databases/{NOTION_MEMO_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(url, headers=headers, json={})
        memos = []
        if res.status_code == 200:
            results = res.json().get("results", [])
            for page in results:
                page_id = page.get("id")
                props = page.get("properties", {})
                title_list = props.get("メモ", {}).get("title", [])
                text_content = title_list[0]["text"]["content"] if title_list else "無題"
                memos.append({"id": page_id, "title": text_content})
        return memos
    except Exception as e:
        print(f"メモ取得エラー: {e}")
        return []


def delete_memo_from_notion(page_id):
    """指定したメモページをNotion上で削除（アーカイブ）します"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {"archived": True}

    try:
        res = requests.patch(url, headers=headers, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"メモ削除エラー: {e}")
        return False


def create_memo_delete_flex():
    """削除対象のメモをボタンで並べたFlex Messageを生成します"""
    memos = get_memos_from_notion()
    if not memos:
        return None

    buttons = []
    for m in memos:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": m["title"][:20],
                "data": f"action=delete_memo&id={m['id']}&title={m['title'][:10]}"
            }
        })

    # キャンセルボタンの追加
    buttons.append({
        "type": "button",
        "style": "secondary",
        "height": "sm",
        "action": {
            "type": "postback",
            "label": "キャンセル",
            "data": "action=cancel_registration"
        }
    })

    rows = []
    for i in range(0, len(buttons), 2):
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": buttons[i:i+2]
        })

    flex_json = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "削除するメモを選択してください", "weight": "bold", "size": "md", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "lg"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": rows
        }
    }
    return FlexMessage(alt_text="メモ削除選択", contents=FlexContainer.from_json(json.dumps(flex_json)))
