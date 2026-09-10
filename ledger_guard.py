import os

import requests

import card_rules

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _title_text(prop):
    return "".join(x.get("plain_text", "") for x in prop.get("title", []))


def find_duplicate(card_name, store_name, amount, date_str):
    """家計簿DBから同日・同額・同カード・同一正規化店名の支出を探す。

    カード会社の別メール（速報/確定など）が別Gmail Message IDで届いても、
    同一取引と判断できるものを二重登録しないための最終ガード。
    """
    if not NOTION_API_KEY or not NOTION_KAKEIBO_DATABASE_ID:
        return None

    target_store = card_rules.normalize_store_name(store_name)
    if not target_store or not date_str:
        return None

    payload = {
        "page_size": 100,
        "filter": {
            "and": [
                {"property": "日付", "date": {"equals": str(date_str)[:10]}},
                {"property": "金額", "number": {"equals": float(amount)}},
                {"property": "カード・支払方法", "select": {"equals": str(card_name)}},
            ]
        },
    }

    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_KAKEIBO_DATABASE_ID}/query",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if res.status_code != 200:
            print(f"家計簿重複検索エラー ({res.status_code}): {res.text}")
            return None

        for page in res.json().get("results", []):
            props = page.get("properties", {})
            store = _title_text(props.get("内容・店名", {}))
            if card_rules.normalize_store_name(store) == target_store:
                category = (props.get("ジャンル", {}).get("select") or {}).get("name", "")
                return {
                    "page_id": page.get("id"),
                    "store": store,
                    "amount": props.get("金額", {}).get("number") or 0,
                    "date": (props.get("日付", {}).get("date") or {}).get("start", ""),
                    "card": str(card_name),
                    "category": category,
                }
    except Exception as e:
        print(f"家計簿重複検索通信エラー: {e}")
    return None
