import os
import requests
from datetime import datetime, timezone, timedelta

import card_rules
import fixed_rules

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_CARD_PENDING_DATABASE_ID = os.environ.get("NOTION_CARD_PENDING_DATABASE_ID", "")

JST = timezone(timedelta(hours=9), "JST")
_title_property_cache = None


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _get_title_property_name():
    global _title_property_cache
    if _title_property_cache:
        return _title_property_cache
    if not NOTION_CARD_PENDING_DATABASE_ID:
        return None

    res = requests.get(
        f"https://api.notion.com/v1/databases/{NOTION_CARD_PENDING_DATABASE_ID}",
        headers=_headers(), timeout=10,
    )
    if res.status_code != 200:
        print(f"カード未処理DBスキーマ取得エラー ({res.status_code}): {res.text}")
        return None

    props = res.json().get("properties", {})
    if props.get("GmailMessageID", {}).get("type") == "title":
        _title_property_cache = "GmailMessageID"
        return _title_property_cache
    for name, prop in props.items():
        if prop.get("type") == "title":
            _title_property_cache = name
            print(f"[Card Queue] Titleプロパティを自動検出: {name}")
            return _title_property_cache
    return None


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
    title_name = _get_title_property_name() or "GmailMessageID"
    return {
        "id": page.get("id"),
        "message_id": _title_value(props.get(title_name, {})),
        "card": _rich_text_value(props.get("カード", {})),
        "store": _rich_text_value(props.get("利用先", {})),
        "amount": props.get("金額", {}).get("number") or 0,
        "date": date_obj.get("start", ""),
        "notified": bool(props.get("通知済み", {}).get("checkbox", False)),
    }


def get_matching_pending_items(card, store):
    """同じカード＋正規化店名の未処理を古い順に返す。"""
    target_card = str(card or "").strip()
    target_store = card_rules.normalize_store_name(store)
    if not target_card or not target_store:
        return []
    return [
        item for item in get_pending_items(limit=1000)
        if item.get("card", "").strip() == target_card
        and card_rules.normalize_store_name(item.get("store")) == target_store
    ]


def find_pending_transaction(card, store, amount, date_str, candidate_check=False):
    """同一取引候補を探す。自動削除には使わず、明示的な確認用途だけ返す。"""
    if not candidate_check:
        return None
    target_store = card_rules.normalize_store_name(store)
    for item in get_matching_pending_items(card, store):
        if (
            card_rules.normalize_store_name(item.get("store")) == target_store
            and float(item.get("amount") or 0) == float(amount)
            and str(item.get("date", ""))[:10] == str(date_str)[:10]
        ):
            return item
    return None


def enqueue_card(message_id, card, store, amount, date_str):
    """固定費除外とGmail Message ID重複防止を通して未処理へ保存する。

    別Message IDの同日同額利用は正当な複数利用の可能性があるため、
    ここでは自動統合しない。保存時の重複確認フローで本人判断へ回す。
    """
    if fixed_rules.is_card_detection_excluded(card, store):
        print(f"[Card Queue] 固定費/サブスクのため検出除外: {card} / {store}")
        return {
            "ok": True, "created": False, "ignored_fixed": True,
            "item": {
                "id": f"fixed-excluded:{message_id}", "message_id": str(message_id),
                "card": str(card), "store": str(store), "amount": float(amount),
                "date": str(date_str), "notified": True,
            },
        }

    if not NOTION_CARD_PENDING_DATABASE_ID:
        return {"ok": False, "error": "NOTION_CARD_PENDING_DATABASE_ID is not configured"}

    title_name = _get_title_property_name()
    if not title_name:
        return {"ok": False, "error": "カード未処理DBにTitleプロパティがありません"}

    existing = _query({
        "page_size": 1,
        "filter": {"property": title_name, "title": {"equals": str(message_id)}},
    })
    if existing:
        return {"ok": True, "created": False, "item": _page_to_item(existing[0]), "duplicate_message": True}

    payload = {
        "parent": {"database_id": NOTION_CARD_PENDING_DATABASE_ID},
        "properties": {
            title_name: {"title": [{"text": {"content": str(message_id)}}]},
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

    return {"ok": True, "created": True, "item": _page_to_item(res.json())}


def mark_notified(page_id):
    return _patch(page_id, {"通知済み": {"checkbox": True}})


def update_store(page_id, store):
    return _patch(page_id, {"利用先": {"rich_text": [{"text": {"content": str(store)}}]}})


def remove(page_id):
    if not page_id:
        return False
    res = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}", headers=_headers(),
        json={"archived": True}, timeout=10,
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
        f"https://api.notion.com/v1/pages/{page_id}", headers=_headers(),
        json={"properties": properties}, timeout=10,
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
    data = res.json()
    if data.get("archived") or data.get("in_trash"):
        return None
    return _page_to_item(data)
