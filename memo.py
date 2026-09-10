import os
import json
import requests
from urllib.parse import quote
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
        return f"メモの保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        return f"通信エラーが発生しました: {str(e)}"


def get_memos_from_notion():
    """NotionのメモDBから現在残っているメモ一覧を取得します"""
    if not NOTION_MEMO_DATABASE_ID:
        return []

    url = f"https://api.notion.com/v1/databases/{NOTION_MEMO_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(
            url,
            headers=headers,
            json={"sorts": [{"property": "日付", "direction": "descending"}]}
        )
        memos = []
        if res.status_code == 200:
            for page in res.json().get("results", []):
                page_id = page.get("id")
                props = page.get("properties", {})
                title_list = props.get("メモ", {}).get("title", [])
                text_content = title_list[0].get("plain_text", "無題") if title_list else "無題"
                date_start = props.get("日付", {}).get("date", {}) or {}
                memos.append({
                    "id": page_id,
                    "title": text_content,
                    "date": date_start.get("start", "")
                })
        return memos
    except Exception as e:
        print(f"メモ取得エラー: {e}")
        return []


def delete_memo_from_notion(page_id):
    """指定したメモページをNotion上で削除（アーカイブ）します"""
    if not page_id:
        return False

    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    try:
        res = requests.patch(url, headers=headers, json={"archived": True})
        return res.status_code == 200
    except Exception as e:
        print(f"メモ削除エラー: {e}")
        return False


def create_memo_delete_flex():
    """削除候補を読みやすい縦一覧で表示し、選択時はまだ削除しません。"""
    memos = get_memos_from_notion()
    if not memos:
        return None

    contents = [
        {"type": "text", "text": "🗑️ メモを削除", "weight": "bold", "size": "lg"},
        {
            "type": "text",
            "text": "削除したいメモを選んでください。次の画面で内容を確認してから削除します。",
            "size": "xs",
            "color": "#777777",
            "wrap": True,
            "margin": "sm"
        },
        {"type": "separator", "margin": "md"}
    ]

    for index, m in enumerate(memos[:20], start=1):
        title = m["title"] or "無題"
        preview = title if len(title) <= 80 else title[:77] + "..."
        date_text = m.get("date", "")[:10]

        item_contents = [
            {"type": "text", "text": f"{index}. {preview}", "size": "sm", "wrap": True, "weight": "bold"}
        ]
        if date_text:
            item_contents.append({
                "type": "text", "text": date_text, "size": "xxs", "color": "#999999", "margin": "xs"
            })

        contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "paddingAll": "10px",
            "backgroundColor": "#F7F7F7",
            "cornerRadius": "md",
            "contents": item_contents,
            "action": {
                "type": "postback",
                "data": f"action=prepare_delete_memo&id={m['id']}&title={quote(title[:200], safe='')}"
            }
        })

    if len(memos) > 20:
        contents.append({
            "type": "text",
            "text": f"ほか {len(memos) - 20} 件あります。古いメモは「メモ一覧」で確認できます。",
            "size": "xxs",
            "color": "#999999",
            "wrap": True,
            "margin": "md"
        })

    flex_json = {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": contents},
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "キャンセル",
                        "data": "action=cancel_registration"
                    }
                }
            ]
        }
    }
    return FlexMessage(alt_text="削除するメモを選択", contents=FlexContainer.from_json(json.dumps(flex_json)))


def create_memo_delete_confirm_flex(page_id, title):
    """削除直前の確認Flex。ここで「削除する」を押した時だけ実削除します。"""
    safe_title = title or "無題"
    display_title = safe_title if len(safe_title) <= 300 else safe_title[:297] + "..."

    flex_json = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "⚠️ 削除の確認",
                    "weight": "bold",
                    "size": "md",
                    "color": "#D32F2F"
                }
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "このメモを削除しますか？", "weight": "bold", "size": "sm"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "paddingAll": "12px",
                    "backgroundColor": "#F7F7F7",
                    "cornerRadius": "md",
                    "contents": [
                        {"type": "text", "text": display_title, "size": "sm", "wrap": True}
                    ]
                },
                {
                    "type": "text",
                    "text": "削除後はLINEから元に戻せません。",
                    "size": "xxs",
                    "color": "#999999",
                    "wrap": True,
                    "margin": "md"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "削除する",
                        "data": f"action=confirm_delete_memo&id={page_id}&title={quote(safe_title[:200], safe='')}"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "やめる",
                        "data": "action=cancel_registration"
                    }
                }
            ]
        }
    }
    return FlexMessage(alt_text="メモ削除の確認", contents=FlexContainer.from_json(json.dumps(flex_json)))
