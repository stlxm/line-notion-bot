import os
import requests
from datetime import datetime, timezone, timedelta

import card_rules
import fixed_rules

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_CARD_PENDING_DATABASE_ID = os.environ.get("NOTION_CARD_PENDING_DATABASE_ID", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")
NOTION_FIXED_DATABASE_ID = os.environ.get("NOTION_FIXED_DATABASE_ID", "")

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


def _query_database(database_id, payload):
    if not database_id:
        return []
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    results = []
    body = dict(payload)
    while True:
        try:
            res = requests.post(url, headers=_headers(), json=body, timeout=10)
        except Exception as e:
            print(f"店名一括補正DB検索通信エラー: {e}")
            return results
        if res.status_code != 200:
            print(f"店名一括補正DB検索エラー ({res.status_code}): {res.text}")
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

    過去に「サミツト→サミット」のような小書き仮名補正を学習済みなら、
    カード明細の店名を保存前に自動補正する。

    別Message IDの同日同額利用は正当な複数利用の可能性があるため、
    ここでは自動統合しない。保存時の重複確認フローで本人判断へ回す。
    """
    original_store = str(store or "").strip()
    store = card_rules.resolve_store_name(original_store)
    if store != original_store:
        print(f"[Card Queue] 学習済み店名補正: {original_store} -> {store}")

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


def _replace_pending_store_name(old_store, new_store):
    if not NOTION_CARD_PENDING_DATABASE_ID:
        return 0
    pages = _query({
        "page_size": 100,
        "filter": {"property": "利用先", "rich_text": {"equals": str(old_store)}},
    })
    updated = 0
    for page in pages:
        if _patch(page.get("id"), {"利用先": {"rich_text": [{"text": {"content": str(new_store)}}]}}):
            updated += 1
    return updated


def _replace_title_store_name(database_id, old_store, new_store):
    """家計簿・固定費DBの同名店を過去分も含めて一括補正する。"""
    if not database_id:
        return 0
    pages = _query_database(database_id, {
        "page_size": 100,
        "filter": {"property": "内容・店名", "title": {"equals": str(old_store)}},
    })
    updated = 0
    for page in pages:
        page_id = page.get("id")
        if not page_id:
            continue
        try:
            res = requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                headers=_headers(),
                json={"properties": {
                    "内容・店名": {"title": [{"text": {"content": str(new_store)}}]}
                }},
                timeout=10,
            )
            if res.status_code == 200:
                updated += 1
            else:
                print(f"店名一括補正更新エラー ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"店名一括補正更新通信エラー: {e}")
    return updated


def replace_store_name_everywhere(old_store, new_store):
    """小書き仮名補正時に、未処理・過去家計簿・固定費マスタをまとめて修正する。"""
    return {
        "pending": _replace_pending_store_name(old_store, new_store),
        "kakeibo": _replace_title_store_name(NOTION_KAKEIBO_DATABASE_ID, old_store, new_store),
        "fixed": _replace_title_store_name(NOTION_FIXED_DATABASE_ID, old_store, new_store),
    }


def update_store(page_id, store):
    """未処理カードの店名を変更する。

    変更内容が大きい仮名→小書き仮名だけなら補正を学習し、
    過去の同じ店名も一括修正する。その他の店名変更は現在の1件だけ変更する。
    """
    if not page_id:
        return False
    new_store = str(store or "").strip()
    if not new_store:
        return False

    current = get_item(page_id)
    old_store = (current or {}).get("store", "").strip()
    if not old_store:
        return _patch(page_id, {"利用先": {"rich_text": [{"text": {"content": new_store}}]}})

    if card_rules.is_small_kana_correction(old_store, new_store):
        learned = card_rules.learn_store_name_correction(old_store, new_store)
        counts = replace_store_name_everywhere(old_store, new_store)
        print(
            f"[Card Queue] 店名小文字補正: {old_store} -> {new_store} / "
            f"learned={learned} / pending={counts['pending']} / "
            f"kakeibo={counts['kakeibo']} / fixed={counts['fixed']}"
        )
        # 一括更新で現在ページが拾えなかった場合だけ個別に補完する。
        refreshed = get_item(page_id)
        if refreshed and refreshed.get("store") == new_store:
            return True
        return _patch(page_id, {"利用先": {"rich_text": [{"text": {"content": new_store}}]}})

    return _patch(page_id, {"利用先": {"rich_text": [{"text": {"content": new_store}}]}})


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
