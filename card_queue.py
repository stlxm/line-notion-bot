import os
import requests
from datetime import datetime, timezone, timedelta

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_CARD_PENDING_DATABASE_ID = os.environ.get("NOTION_CARD_PENDING_DATABASE_ID", "")

JST = timezone(timedelta(hours=9), "JST")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _query(payload):
    if not NOTION_CARD_PENDING_DATABASE_ID:
        return []

    url = f"https://api.notion.com/v1/databases/{NOTION_CARD_PENDING_DATABASE_ID}/query"
    results = []
    body = dict(payload)
    while True:
        res = requests.post(url, headers=_headers(), json=body, timeout=10)
        if res.status_code != 200:
            print(f"カード未処理DB検索エラー ({res.status_code}): {res.text}")
            return results
        data = res.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        body["start_cursor"] = data.get("next_cursor")
    return results


def _rich_text_value(prop):
    return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))


def _title_value(prop):
    return "".join(x.get("plain_text", "") for x in prop.get("title", []))


def _page_to_item(page):
    props = page.get("properties", {})
    date_obj = props.get("利用日", {}).get("date") or {}
    return {
        "id": page.get("id"),
        "message_id": _title_value(props.get("GmailMessageID", {})),
        "card": _rich_text_value(props.get("カード", {})),
        "store": _rich_text_value(props.get("利用先", {})),
        "amount": props.get("金額", {}).get("number") or 0,
        "date": date_obj.get("start", ""),
        "notified": bool(props.get("通知済み", {}).get("checkbox", False)),
    }


def enqueue_card(message_id, card, store, amount, date_str):
    """Gmail Message IDで重複防止しながら未処理カードを保存します。"""
    if not NOTION_CARD_PENDING_DATABASE_ID:
        return {"ok": False, "error": "NOTION_CARD_PENDING_DATABASE_ID is not configured"}

    existing = _query({
        "page_size": 1,
        "filter": {"property": "GmailMessageID", "title": {"equals": str(message_id)}},
    })
    if existing:
        item = _page_to_item(existing[0])
        return {"ok": True, "created": False, "item": item}

    payload = {
        "parent": {"database_id": NOTION_CARD_PENDING_DATABASE_ID},
        "properties": {
            "GmailMessageID": {"title": [{"text": {"content": str(message_id)}}]},
            "カード": {"rich_text": [{"text": {"content": str(card)}}]},
            "利用先": {"rich_text": [{"text": {"content": str(store)}}]},
            "金額": {"number": float(amount)},
            "利用日": {"date": {"start": str(date_str)}},
            "通知済み": {"checkbox": False},
            "登録日時": {"date": {"start": datetime.now(JST).isoformat()}},
        },
    }
    res = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json=payload, timeout=10)
    if res.status_code != 200:
        print(f"カード未処理DB作成エラー ({res.status_code}): {res.text}")
        return {"ok": False, "error": res.text[:500]}

    item = _page_to_item(res.json())
    return {"ok": True, "created": True, "item": item}


def mark_notified(page_id):
    return _patch(page_id, {"通知済み": {"checkbox": True}})


def update_store(page_id, store):
    return _patch(page_id, {"利用先": {"rich_text": [{"text": {"content": str(store)}}]}})


def remove(page_id):
    """処理済み/スキップ済みのキュー項目をNotionでアーカイブして一覧から消します。"""
    if not page_id:
        return False
    res = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_headers(),
        json={"archived": True},
        timeout=10,
    )
    if res.status_code != 200:
        print(f"カード未処理DBアーカイブエラー ({res.status_code}): {res.text}")
        return False
    return True


def complete(page_id):
    return remove(page_id)


def skip(page_id):
    return remove(page_id)


def _patch(page_id, properties):
    if not page_id:
        return False
    res = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_headers(),
        json={"properties": properties},
        timeout=10,
    )
    if res.status_code != 200:
        print(f"カード未処理DB更新エラー ({res.status_code}): {res.text}")
        return False
    return True


def get_pending_items(limit=100):
    results = _query({
        "page_size": min(limit, 100),
        "sorts": [
            {"property": "利用日", "direction": "ascending"},
            {"property": "登録日時", "direction": "ascending"},
        ],
    })
    return [_page_to_item(x) for x in results[:limit]]


def get_pending_count():
    return len(get_pending_items(limit=1000))


def get_next_pending(exclude_id=None):
    for item in get_pending_items(limit=100):
        if item.get("id") != exclude_id:
            return item
    return None


def get_item(page_id):
    if not page_id:
        return None
    res = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=_headers(), timeout=10)
    if res.status_code != 200:
        return None
    return _page_to_item(res.json())
