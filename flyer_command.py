import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta

import requests

JST = timezone(timedelta(hours=9), "JST")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
ACTIVE_LIFE_CALENDAR_DATABASE_ID = "684f959e451047389505a95ed368a7d6"
DELETED_OLD_FLYER_DATABASE_ID = "3d90efb323d080b5999bed1820a6665e"
_configured_flyer_db = os.environ.get("NOTION_FLYER_DATABASE_ID", "").strip()
# 3d90... は削除済みの旧「特売カレンダー」。誤設定が残っていても実運用中の生活カレンダーへ退避する。
NOTION_FLYER_DATABASE_ID = (
    ACTIVE_LIFE_CALENDAR_DATABASE_ID
    if not _configured_flyer_db or _configured_flyer_db == DELETED_OLD_FLYER_DATABASE_ID
    else _configured_flyer_db
)
STORE_NAME = "サミット ミナノ分倍河原店"
OFFICIAL_URL = "https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer"
MAX_RESULTS = 20


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _plain(prop, key):
    values = (prop or {}).get(key, []) or []
    return "".join(x.get("plain_text", "") for x in values)


def _select(prop):
    value = (prop or {}).get("select") or {}
    return value.get("name", "")


def _query_all():
    if not NOTION_API_KEY or not NOTION_FLYER_DATABASE_ID:
        return []
    if _configured_flyer_db == DELETED_OLD_FLYER_DATABASE_ID:
        print(
            "NOTION_FLYER_DATABASE_ID に削除済み旧DBが設定されています。"
            f"生活カレンダー {ACTIVE_LIFE_CALENDAR_DATABASE_ID} を使用します。"
        )
    url = f"https://api.notion.com/v1/databases/{NOTION_FLYER_DATABASE_ID}/query"
    results = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        try:
            res = requests.post(url, headers=_headers(), json=body, timeout=12)
        except Exception as e:
            print(f"特売Notion取得エラー: {e}")
            return []
        if res.status_code != 200:
            print(f"特売Notion取得エラー ({res.status_code}): {res.text[:700]}")
            return []
        data = res.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor or len(results) >= 1000:
            break
    return results


def _date_range(prop):
    value = (prop or {}).get("date") or {}
    start = str(value.get("start") or "")[:10]
    end = str(value.get("end") or start)[:10]
    return start, end


def _span_days(item):
    try:
        start = datetime.strptime(item["start"], "%Y-%m-%d").date()
        end = datetime.strptime(item["end"], "%Y-%m-%d").date()
        return (end - start).days + 1
    except Exception:
        return 9999


def _normalize_product(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(r"(?:北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)産(?:ほか|他)?", "", text)
    text = text.replace("国内産", "").replace("ケース購入", "").replace("1ケース", "").replace("ケース", "")
    text = text.replace("切りおとし", "切り落とし").replace("切りおろし", "切り落とし")
    text = text.replace("ソース焼きそば", "ソースやきそば").replace("サーモンタラト", "サーモントラウト")
    return re.sub(r"[・･／/\-ー\s　]", "", text)


def _normalize_price(value):
    return re.sub(r"[,円￥¥\s　]", "", str(value or ""))


def _dedupe(items):
    chosen = {}
    for item in items:
        key = (_normalize_product(item["product"]), _normalize_price(item["price"]), item["unit"].strip())
        old = chosen.get(key)
        if old is None:
            chosen[key] = item
            continue
        if _span_days(item) < _span_days(old) or (
            _span_days(item) == _span_days(old) and len(item["notes"]) > len(old["notes"])
        ):
            chosen[key] = item
    return list(chosen.values())


def get_today_deals():
    today = datetime.now(JST).date().isoformat()
    deals = []
    for page in _query_all():
        props = page.get("properties", {})
        if _select(props.get("店舗")) != STORE_NAME:
            continue
        if props.get("有効", {}).get("checkbox") is False:
            continue
        kind = _select(props.get("種類"))
        if kind and kind != "特売":
            continue
        state = _select(props.get("確認状態"))
        if state and state != "確認済み":
            continue
        start, end = _date_range(props.get("日付"))
        if not start or start > today or end < today:
            continue
        deals.append({
            "product": _plain(props.get("予定名"), "title") or "特売商品",
            "price": _plain(props.get("価格"), "rich_text"),
            "unit": _plain(props.get("容量・単位"), "rich_text"),
            "notes": _plain(props.get("備考"), "rich_text"),
            "priority": props.get("優先度", {}).get("number") or 2,
            "start": start,
            "end": end,
        })
    deals = _dedupe(deals)
    deals.sort(key=lambda x: (_span_days(x), x["priority"], x["product"]))
    return deals[:MAX_RESULTS]


def build_today_deals_text():
    today = datetime.now(JST).date().isoformat()
    if not NOTION_API_KEY:
        return "特売情報を取得できません。Renderの NOTION_API_KEY を確認してください。"
    deals = get_today_deals()
    lines = [f"🛒 {STORE_NAME}", f"【{today} の特売】", ""]
    if not deals:
        lines += [
            "今日の確認済み特売はNotionに登録されていません。",
            "チラシ同期後にもう一度確認してください。",
        ]
    else:
        short = [d for d in deals if _span_days(d) <= 7]
        long = [d for d in deals if _span_days(d) > 7]
        if short:
            lines.append("🔥 今日・短期特売")
            for deal in short:
                _append(lines, deal)
            lines.append("")
        if long:
            lines.append("📅 月間・長期特売")
            for deal in long:
                _append(lines, deal)
            lines.append("")
        lines.append(f"表示: {len(deals)}件")
    lines += ["", f"チラシ: {OFFICIAL_URL}", "※価格・在庫は店頭表示を優先してください。"]
    return "\n".join(lines)[:4800]


def _append(lines, deal):
    line = f"・{deal['product']}"
    if deal["price"]:
        line += f" {deal['price']}"
    if deal["unit"]:
        line += f" / {deal['unit']}"
    lines.append(line)
    if deal["notes"]:
        lines.append(f"  {deal['notes']}")
    elif deal["start"] != deal["end"]:
        lines.append(f"  {deal['start']}〜{deal['end']}")


def handle_text_command(text):
    message = (text or "").strip()
    if message in ["特売", "特売情報", "今日の特売", "本日の特売", "サミット特売", "チラシ特売"]:
        return build_today_deals_text()
    return None
