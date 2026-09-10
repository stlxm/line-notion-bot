import os

import requests

import card_rules

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_FIXED_DATABASE_ID = os.environ.get("NOTION_FIXED_DATABASE_ID", "")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _query_active_fixed():
    """有効な固定費を全件取得。失敗時は None を返して安全側に倒す。"""
    if not NOTION_API_KEY or not NOTION_FIXED_DATABASE_ID:
        return None

    url = f"https://api.notion.com/v1/databases/{NOTION_FIXED_DATABASE_ID}/query"
    body = {
        "page_size": 100,
        "filter": {"property": "有効", "checkbox": {"equals": True}},
    }
    results = []
    try:
        while True:
            res = requests.post(url, headers=_headers(), json=body, timeout=10)
            if res.status_code != 200:
                print(f"固定費除外ルール検索エラー ({res.status_code}): {res.text}")
                return None
            data = res.json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            body["start_cursor"] = data.get("next_cursor")
        return results
    except Exception as e:
        print(f"固定費除外ルール検索通信エラー: {e}")
        return None


def _title_text(prop):
    return "".join(x.get("plain_text", "") for x in prop.get("title", []))


def _fixed_page_to_item(page):
    props = page.get("properties", {})
    cat = props.get("ジャンル", {}).get("select") or {}
    card = props.get("カード・支払方法", {}).get("select") or {}
    return {
        "page_id": page.get("id"),
        "store": _title_text(props.get("内容・店名", {})),
        "amount": props.get("金額", {}).get("number") or 0,
        "category": cat.get("name", "固定費"),
        "card": card.get("name", "現金"),
    }


def _find_in_pages(pages, card_name, store_name):
    target_card = str(card_name or "").strip()
    target_store = card_rules.normalize_store_name(store_name)
    if not target_card or not target_store:
        return None

    for page in pages:
        item = _fixed_page_to_item(page)
        if (
            item["card"].strip() == target_card
            and card_rules.normalize_store_name(item["store"]) == target_store
        ):
            return item
    return None


def find_fixed_match(card_name, store_name):
    """カード名 + 正規化店名が一致する有効固定費を返す。"""
    pages = _query_active_fixed()
    if pages is None:
        return None
    return _find_in_pages(pages, card_name, store_name)


def is_card_detection_excluded(card_name, store_name):
    """固定費DBに一致するカード利用なら通常カード検出から除外する。

    Notion検索に失敗した場合は誤除外を避けるため False にする。
    """
    pages = _query_active_fixed()
    if pages is None:
        return False
    return _find_in_pages(pages, card_name, store_name) is not None


def ensure_fixed_expense(store_name, amount, category, card_name):
    """固定費/サブスクを重複作成せず固定費DBへ登録・更新する。

    戻り値: (success, created)
    Notion側の既存確認に失敗した場合は、重複作成を避けるため新規作成しない。
    """
    if category not in {"固定費", "サブスク"}:
        return False, False
    if not NOTION_API_KEY or not NOTION_FIXED_DATABASE_ID:
        return False, False

    pages = _query_active_fixed()
    if pages is None:
        print("固定費マスタの既存確認に失敗したため登録を中止しました。")
        return False, False

    existing = _find_in_pages(pages, card_name, store_name)
    properties = {
        "内容・店名": {"title": [{"text": {"content": str(store_name)}}]},
        "金額": {"number": float(amount)},
        "ジャンル": {"select": {"name": str(category)}},
        "カード・支払方法": {"select": {"name": str(card_name)}},
        "有効": {"checkbox": True},
    }

    try:
        if existing:
            res = requests.patch(
                f"https://api.notion.com/v1/pages/{existing['page_id']}",
                headers=_headers(),
                json={"properties": properties},
                timeout=10,
            )
            if res.status_code != 200:
                print(f"固定費マスタ更新エラー ({res.status_code}): {res.text}")
                return False, False
            return True, False

        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_headers(),
            json={"parent": {"database_id": NOTION_FIXED_DATABASE_ID}, "properties": properties},
            timeout=10,
        )
        if res.status_code != 200:
            print(f"固定費マスタ作成エラー ({res.status_code}): {res.text}")
            return False, False
        return True, True
    except Exception as e:
        print(f"固定費マスタ登録通信エラー: {e}")
        return False, False
