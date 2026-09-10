import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta

import requests

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_CARD_RULES_DATABASE_ID = os.environ.get("NOTION_CARD_RULES_DATABASE_ID", "")
JST = timezone(timedelta(hours=9), "JST")

AUTO_REGISTER_MIN_MATCHES = int(os.environ.get("CARD_AUTO_REGISTER_MIN_MATCHES", "3"))


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def normalize_store_name(store_name):
    """カード会社固有の表記ゆれを比較しやすい店名キーへ正規化する。"""
    text = unicodedata.normalize("NFKC", str(store_name or "")).strip()
    text = text.upper()
    text = re.sub(r"[\s　]+", " ", text)
    text = re.sub(r"(?:ご利用|利用|決済|購入)$", "", text).strip()
    text = re.sub(r"[^0-9A-Zァ-ヶー一-龠々〆ヵヶ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def _query_rule(store_key):
    if not NOTION_API_KEY or not NOTION_CARD_RULES_DATABASE_ID or not store_key:
        return None
    url = f"https://api.notion.com/v1/databases/{NOTION_CARD_RULES_DATABASE_ID}/query"
    payload = {"page_size": 1, "filter": {"property": "店名キー", "title": {"equals": store_key}}}
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
    learn_count = int(props.get("学習回数", {}).get("number") or 0)
    match_count = int(props.get("一致回数", {}).get("number") or 0)
    confidence = min(1.0, match_count / max(learn_count, 1)) if learn_count else 0.0
    eligible = match_count >= AUTO_REGISTER_MIN_MATCHES and confidence >= 1.0
    return {
        "page_id": page.get("id"),
        "store_key": "".join(x.get("plain_text", "") for x in props.get("店名キー", {}).get("title", [])),
        "display_name": "".join(x.get("plain_text", "") for x in display_rt),
        "category": category_obj.get("name", ""),
        "learn_count": learn_count,
        "match_count": match_count,
        "confidence": confidence,
        "eligible_for_auto": eligible,
        "auto_register": bool(props.get("自動登録", {}).get("checkbox", False)),
    }


def get_rule(store_name):
    return _page_to_rule(_query_rule(normalize_store_name(store_name)))


def suggest_category(store_name):
    rule = get_rule(store_name)
    if not rule or not rule.get("category"):
        return None
    return {**rule, "can_auto_register": bool(rule.get("auto_register") and rule.get("eligible_for_auto"))}


def learn_category(store_name, category, display_name=None):
    """ユーザーが確定した分類だけを学習する。自動登録結果は呼び出し側で学習しない。"""
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
    properties = {
        "表示名": {"rich_text": [{"text": {"content": str(display_name or store_name)[:2000]}}]},
        "ジャンル": {"select": {"name": str(category)}},
        "学習回数": {"number": rule.get("learn_count", 0) + 1},
        "一致回数": {"number": rule.get("match_count", 0) + 1 if same_category else 1},
        "最終更新": {"date": {"start": now}},
    }
    if not same_category:
        properties["自動登録"] = {"checkbox": False}

    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{rule['page_id']}",
            headers=_headers(), json={"properties": properties}, timeout=8,
        )
        if res.status_code != 200:
            print(f"カード学習ルール更新エラー ({res.status_code}): {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"カード学習ルール更新通信エラー: {e}")
        return False


def set_auto_register(store_name, enabled):
    rule = get_rule(store_name)
    if not rule:
        return False, "学習ルールが見つかりません。"
    return set_auto_register_by_page_id(rule["page_id"], enabled)


def set_auto_register_by_page_id(page_id, enabled):
    """自動登録ONは3回以上・一致率100%を満たすルールだけ許可する。"""
    if not page_id or not NOTION_API_KEY:
        return False, "カード学習ルールDBが設定されていません。"
    try:
        res = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=_headers(), timeout=8)
        if res.status_code != 200:
            return False, "カード学習ルールを取得できませんでした。"
        rule = _page_to_rule(res.json())
        if enabled and not rule.get("eligible_for_auto"):
            return False, f"自動登録には同じジャンルで{AUTO_REGISTER_MIN_MATCHES}回以上の一致が必要です。"
        patch = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}", headers=_headers(),
            json={"properties": {"自動登録": {"checkbox": bool(enabled)}}}, timeout=8,
        )
        if patch.status_code != 200:
            return False, "自動登録設定の更新に失敗しました。"
        return True, "自動登録をONにしました。" if enabled else "自動登録をOFFにしました。"
    except Exception as e:
        print(f"カード自動登録設定エラー: {e}")
        return False, "自動登録設定の通信に失敗しました。"


def get_rules(limit=30):
    """カード設定画面用。最近更新された学習ルールを返す。"""
    if not NOTION_API_KEY or not NOTION_CARD_RULES_DATABASE_ID:
        return []
    payload = {
        "page_size": min(max(int(limit), 1), 100),
        "sorts": [{"property": "最終更新", "direction": "descending"}],
    }
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_CARD_RULES_DATABASE_ID}/query",
            headers=_headers(), json=payload, timeout=8,
        )
        if res.status_code != 200:
            print(f"カード学習ルール一覧エラー ({res.status_code}): {res.text}")
            return []
        return [_page_to_rule(p) for p in res.json().get("results", [])]
    except Exception as e:
        print(f"カード学習ルール一覧通信エラー: {e}")
        return []
