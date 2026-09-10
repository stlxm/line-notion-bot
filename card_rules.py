import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta

import requests

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_CARD_RULES_DATABASE_ID = os.environ.get("NOTION_CARD_RULES_DATABASE_ID", "")
JST = timezone(timedelta(hours=9), "JST")

# 自動登録は誤分類を避けるため保守的にする。
AUTO_REGISTER_MIN_MATCHES = int(os.environ.get("CARD_AUTO_REGISTER_MIN_MATCHES", "3"))


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def normalize_store_name(store_name):
    """カード会社固有の表記ゆれを比較しやすい店名キーへ正規化する。

    元の表示名は失わず、照合用キーとしてだけ使う。
    """
    text = unicodedata.normalize("NFKC", str(store_name or "")).strip()
    text = text.upper()
    text = re.sub(r"[\s　]+", " ", text)
    text = re.sub(r"(?:ご利用|利用|決済|購入)$", "", text).strip()
    # 比較に不要になりやすい記号を除くが、日本語・英数は残す。
    text = re.sub(r"[^0-9A-Zァ-ヶー一-龠々〆ヵヶ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def _query_rule(store_key):
    if not NOTION_API_KEY or not NOTION_CARD_RULES_DATABASE_ID or not store_key:
        return None

    url = f"https://api.notion.com/v1/databases/{NOTION_CARD_RULES_DATABASE_ID}/query"
    payload = {
        "page_size": 1,
        "filter": {"property": "店名キー", "title": {"equals": store_key}},
    }
    try:
        res = requests.post(url, headers=_headers(), json=payload, timeout=8)
        if res.status_code != 200:
            print(f"カード学習ルール検索エラー ({res.status_code}): {res.text}")
            return None
        results = res.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"カード学習ルール検索通信エラー: {e}")
        return None


def _page_to_rule(page):
    if not page:
        return None
    props = page.get("properties", {})
    display_rt = props.get("表示名", {}).get("rich_text", [])
    category_obj = props.get("ジャンル", {}).get("select") or {}
    return {
        "page_id": page.get("id"),
        "store_key": "".join(x.get("plain_text", "") for x in props.get("店名キー", {}).get("title", [])),
        "display_name": "".join(x.get("plain_text", "") for x in display_rt),
        "category": category_obj.get("name", ""),
        "learn_count": int(props.get("学習回数", {}).get("number") or 0),
        "match_count": int(props.get("一致回数", {}).get("number") or 0),
        "auto_register": bool(props.get("自動登録", {}).get("checkbox", False)),
    }


def get_rule(store_name):
    return _page_to_rule(_query_rule(normalize_store_name(store_name)))


def suggest_category(store_name):
    """学習済みなら推奨ジャンルと信頼度を返す。Geminiは使わない。"""
    rule = get_rule(store_name)
    if not rule or not rule.get("category"):
        return None

    learn_count = max(rule.get("learn_count", 0), 1)
    confidence = min(1.0, rule.get("match_count", 0) / learn_count)
    return {
        **rule,
        "confidence": confidence,
        "can_auto_register": (
            rule.get("auto_register", False)
            and rule.get("match_count", 0) >= AUTO_REGISTER_MIN_MATCHES
            and confidence >= 1.0
        ),
    }


def learn_category(store_name, category, display_name=None):
    """ユーザーが確定したジャンルを学習する。

    同じ店でジャンルが変わった場合は自動登録を勝手に有効化せず、
    新ジャンルを現在候補として保持しながら一致回数を1へ戻す。
    """
    if not NOTION_API_KEY or not NOTION_CARD_RULES_DATABASE_ID:
        return False

    store_key = normalize_store_name(store_name)
    if not store_key or not category:
        return False

    existing_page = _query_rule(store_key)
    now = datetime.now(JST).isoformat()

    if not existing_page:
        payload = {
            "parent": {"database_id": NOTION_CARD_RULES_DATABASE_ID},
            "properties": {
                "店名キー": {"title": [{"text": {"content": store_key}}]},
                "表示名": {"rich_text": [{"text": {"content": str(display_name or store_name)[:2000]}}]},
                "ジャンル": {"select": {"name": str(category)}},
                "学習回数": {"number": 1},
                "一致回数": {"number": 1},
                "自動登録": {"checkbox": False},
                "最終更新": {"date": {"start": now}},
            },
        }
        try:
            res = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json=payload, timeout=8)
            if res.status_code != 200:
                print(f"カード学習ルール作成エラー ({res.status_code}): {res.text}")
            return res.status_code == 200
        except Exception as e:
            print(f"カード学習ルール作成通信エラー: {e}")
            return False

    rule = _page_to_rule(existing_page)
    same_category = rule.get("category") == category
    learn_count = rule.get("learn_count", 0) + 1
    match_count = rule.get("match_count", 0) + 1 if same_category else 1

    properties = {
        "表示名": {"rich_text": [{"text": {"content": str(display_name or store_name)[:2000]}}]},
        "ジャンル": {"select": {"name": str(category)}},
        "学習回数": {"number": learn_count},
        "一致回数": {"number": match_count},
        "最終更新": {"date": {"start": now}},
    }

    # 分類が変わったら誤自動登録を避けるため自動登録をOFFへ戻す。
    if not same_category:
        properties["自動登録"] = {"checkbox": False}

    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{rule['page_id']}",
            headers=_headers(),
            json={"properties": properties},
            timeout=8,
        )
        if res.status_code != 200:
            print(f"カード学習ルール更新エラー ({res.status_code}): {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"カード学習ルール更新通信エラー: {e}")
        return False


def set_auto_register(store_name, enabled):
    """ユーザーが明示的に自動登録ON/OFFを変更するための関数。"""
    rule = get_rule(store_name)
    if not rule:
        return False
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{rule['page_id']}",
            headers=_headers(),
            json={"properties": {"自動登録": {"checkbox": bool(enabled)}}},
            timeout=8,
        )
        return res.status_code == 200
    except Exception as e:
        print(f"カード自動登録設定エラー: {e}")
        return False
