import os
import re
from datetime import datetime

import requests
from linebot.v3.messaging import FlexMessage, FlexContainer
import json

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _text(prop):
    if not prop:
        return ""
    kind = prop.get("type")
    if kind == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if kind == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    return ""


def get_latest_entry():
    if not NOTION_API_KEY or not NOTION_KAKEIBO_DATABASE_ID:
        return None, "家計簿DBが未設定です。"
    payload = {
        "page_size": 1,
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
    }
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_KAKEIBO_DATABASE_ID}/query",
            headers=_headers(), json=payload, timeout=12,
        )
    except Exception as e:
        return None, f"Notion取得エラー: {e}"
    if res.status_code != 200:
        return None, f"家計簿の取得に失敗しました ({res.status_code})"
    rows = res.json().get("results", [])
    if not rows:
        return None, "家計簿に登録がありません。"
    page = rows[0]
    p = page.get("properties", {})
    date_obj = p.get("日付", {}).get("date") or {}
    cat_obj = p.get("ジャンル", {}).get("select") or {}
    card_obj = p.get("カード・支払方法", {}).get("select") or {}
    return {
        "id": page.get("id"),
        "store": _text(p.get("内容・店名")) or "未入力",
        "amount": float(p.get("金額", {}).get("number") or 0),
        "date": (date_obj.get("start") or "")[:10],
        "category": cat_obj.get("name") or "未分類",
        "card": card_obj.get("name") or "未設定",
    }, None


def format_entry(entry):
    return (
        f"{entry['date']}\n"
        f"{entry['store']} / ¥{int(entry['amount']):,}\n"
        f"ジャンル: {entry['category']}\n"
        f"支払方法: {entry['card']}"
    )


def create_last_entry_menu_flex(entry):
    def msg_button(label, text, style="primary"):
        return {
            "type": "button", "style": style, "height": "sm",
            "action": {"type": "message", "label": label[:20], "text": text},
        }
    flex = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "✏️ 直前の家計簿", "weight": "bold", "size": "lg"},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "text", "text": format_entry(entry), "size": "sm", "wrap": True},
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            msg_button("金額を修正", "直前修正 金額"),
            msg_button("店名を修正", "直前修正 店名"),
            msg_button("日付を修正", "直前修正 日付"),
            msg_button("ジャンルを修正", "直前修正 ジャンル"),
            msg_button("支払方法を修正", "直前修正 支払方法"),
            msg_button("直前登録を取り消す", "直前取り消し", "secondary"),
        ]},
    }
    return FlexMessage(alt_text="直前登録を修正", contents=FlexContainer.from_json(json.dumps(flex, ensure_ascii=False)))


def create_undo_confirm_flex(entry):
    flex = {
        "type": "bubble", "size": "mega",
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "text", "text": "⚠️ 直前登録を取り消しますか？", "weight": "bold", "size": "lg", "wrap": True},
            {"type": "text", "text": format_entry(entry), "size": "sm", "wrap": True, "margin": "md"},
            {"type": "text", "text": "Notionでは削除ではなくアーカイブします。", "size": "xs", "color": "#888888", "wrap": True, "margin": "md"},
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "button", "style": "primary", "height": "sm",
             "action": {"type": "message", "label": "取り消す", "text": "直前取り消し 確定"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "やめる", "text": "キャンセル"}},
        ]},
    }
    return FlexMessage(alt_text="直前登録の取り消し確認", contents=FlexContainer.from_json(json.dumps(flex, ensure_ascii=False)))


def _patch_latest(properties=None, archived=None):
    entry, err = get_latest_entry()
    if not entry:
        return False, err
    payload = {}
    if properties is not None:
        payload["properties"] = properties
    if archived is not None:
        payload["archived"] = archived
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{entry['id']}", headers=_headers(), json=payload, timeout=12,
        )
    except Exception as e:
        return False, f"Notion更新エラー: {e}"
    if res.status_code != 200:
        return False, f"更新に失敗しました ({res.status_code})"
    return True, entry


def _edit_help(field):
    examples = {
        "金額": "直前修正 金額 1500",
        "店名": "直前修正 店名 サミット",
        "日付": "直前修正 日付 2026-09-12",
        "ジャンル": "直前修正 ジャンル 食費",
        "支払方法": "直前修正 支払方法 JCB",
    }
    return f"新しい{field}を続けて送ってください。\n例: {examples[field]}\nやめる場合は「キャンセル」"


def handle_text_command(text):
    message = (text or "").strip().replace("　", " ")

    if message in {"直前登録", "直前修正", "直前の支出", "最後の支出"}:
        entry, err = get_latest_entry()
        return create_last_entry_menu_flex(entry) if entry else err

    if message == "直前取り消し":
        entry, err = get_latest_entry()
        return create_undo_confirm_flex(entry) if entry else err

    if message == "直前取り消し 確定":
        ok, result = _patch_latest(archived=True)
        if not ok:
            return f"⚠️ {result}"
        return f"✅ 直前登録を取り消しました。\n{format_entry(result)}"

    if message.startswith("直前修正 "):
        parts = message.split(maxsplit=2)
        if len(parts) == 2:
            field = parts[1]
            if field in {"金額", "店名", "日付", "ジャンル", "支払方法"}:
                return _edit_help(field)
            return "修正できる項目は 金額 / 店名 / 日付 / ジャンル / 支払方法 です。"

        field, value = parts[1], parts[2].strip()
        if field == "金額":
            cleaned = value.replace(",", "").replace("円", "")
            try:
                amount = float(cleaned)
            except ValueError:
                return "金額は数字で入力してください。例: 直前修正 金額 1500"
            if amount < 0:
                return "金額は0以上にしてください。"
            props = {"金額": {"number": amount}}
        elif field == "店名":
            props = {"内容・店名": {"title": [{"text": {"content": value[:2000]}}]}}
        elif field == "日付":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return "日付は YYYY-MM-DD 形式で入力してください。"
            props = {"日付": {"date": {"start": value}}}
        elif field == "ジャンル":
            props = {"ジャンル": {"select": {"name": value}}}
        elif field == "支払方法":
            props = {"カード・支払方法": {"select": {"name": value}}}
        else:
            return "修正できる項目は 金額 / 店名 / 日付 / ジャンル / 支払方法 です。"

        ok, result = _patch_latest(properties=props)
        if not ok:
            return f"⚠️ {result}"
        updated, err = get_latest_entry()
        if not updated:
            return f"✅ {field}を更新しました。"
        return f"✅ {field}を更新しました。\n\n{format_entry(updated)}"

    return None
