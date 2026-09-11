import os
import re
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from google import genai

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")
NOTION_MEMO_DATABASE_ID = os.environ.get("NOTION_MEMO_DATABASE_ID", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")
NOTION_MONTHLY_DATABASE_ID = os.environ.get("NOTION_MONTHLY_DATABASE_ID", "")
NOTION_FIXED_DATABASE_ID = os.environ.get("NOTION_FIXED_DATABASE_ID", "")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

JST = timezone(timedelta(hours=9), "JST")
_SCHEMA_CACHE = {}
_SCHEMA_CACHE_TTL = 600
MAX_AI_DATABASES = 2
MAX_ROWS_PER_DB = 40
MAX_CONTEXT_CHARS = 18000

ROLE_HINTS = {
    "家計簿": [
        "家計簿", "支出", "出費", "食費", "日用品", "交通費", "娯楽",
        "買った", "購入", "使った", "金額", "店", "カード", "支払", "決済",
    ],
    "月別管理": [
        "予算", "残額", "残り", "使える", "月別", "予算超過", "消化率",
    ],
    "固定費": [
        "固定費", "サブスク", "定額", "月額", "Netflix", "Amazon Prime",
    ],
    "メモ": [
        "メモ", "TODO", "ToDo", "todo", "覚えて", "やること", "備忘録",
    ],
    "URL": [
        "URL", "url", "リンク", "あとで見る", "記事", "サイト", "Web", "web",
    ],
}


def call_gemini_with_retry(model_name, prompt, max_retries=3, initial_delay=2):
    """Geminiの一時エラーのみ指数バックオフで再試行します。"""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
        except Exception as e:
            err_str = str(e)
            transient = (
                "503" in err_str
                or "UNAVAILABLE" in err_str
                or "high demand" in err_str.lower()
                or "429" in err_str
                or "RESOURCE_EXHAUSTED" in err_str
            )
            if transient and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def _notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _is_configured(database_id):
    return bool(str(database_id or "").strip())


def get_all_database_ids():
    ids = []
    for db_id in [
        NOTION_KAKEIBO_DATABASE_ID,
        NOTION_MONTHLY_DATABASE_ID,
        NOTION_FIXED_DATABASE_ID,
        NOTION_MEMO_DATABASE_ID,
        NOTION_URL_DATABASE_ID,
    ]:
        if _is_configured(db_id) and db_id not in ids:
            ids.append(db_id)

    for db_id in [x.strip() for x in NOTION_DATABASE_IDS.split(",") if x.strip()]:
        if db_id not in ids:
            ids.append(db_id)
    return ids


def get_database_title(database_id):
    try:
        res = requests.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers=_notion_headers(),
            timeout=10,
        )
        if res.status_code != 200:
            return "無題DB"
        title_items = res.json().get("title", [])
        title = "".join(x.get("plain_text", "") for x in title_items).strip()
        return title or "無題DB"
    except Exception:
        return "無題DB"


def get_database_properties(database_id):
    try:
        res = requests.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers=_notion_headers(),
            timeout=10,
        )
        if res.status_code != 200:
            return []
        props = res.json().get("properties", {})
        supported = {"title", "rich_text", "number", "select", "multi_select", "date", "checkbox", "url"}
        return [(name, p.get("type")) for name, p in props.items() if p.get("type") in supported]
    except Exception as e:
        print(f"Notionプロパティ取得エラー: {e}")
        return []


def create_notion_page(database_id, collected_data, prop_types):
    properties = {}
    for name, value in collected_data.items():
        prop_type = prop_types.get(name)
        if prop_type == "title":
            properties[name] = {"title": [{"text": {"content": str(value)}}]}
        elif prop_type == "rich_text":
            properties[name] = {"rich_text": [{"text": {"content": str(value)}}]}
        elif prop_type == "number":
            try:
                properties[name] = {"number": float(str(value).replace(",", ""))}
            except Exception:
                properties[name] = {"number": None}
        elif prop_type == "select":
            properties[name] = {"select": {"name": str(value)}}
        elif prop_type == "multi_select":
            values = [x.strip() for x in re.split(r"[,、]", str(value)) if x.strip()]
            properties[name] = {"multi_select": [{"name": x} for x in values]}
        elif prop_type == "date":
            properties[name] = {"date": {"start": str(value)}}
        elif prop_type == "checkbox":
            properties[name] = {"checkbox": str(value).lower() in {"true", "1", "yes", "はい", "on"}}
        elif prop_type == "url":
            properties[name] = {"url": str(value)}

    try:
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_notion_headers(),
            json={"parent": {"database_id": database_id}, "properties": properties},
            timeout=15,
        )
        if res.status_code != 200:
            print(f"Notionページ作成エラー ({res.status_code}): {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"Notionページ作成通信エラー: {e}")
        return False


def add_url_to_notion(url):
    if not NOTION_URL_DATABASE_ID:
        return "URL保存DBが設定されていません。"
    props = get_database_properties(NOTION_URL_DATABASE_ID)
    if not props:
        return "URL保存DBのプロパティ取得に失敗しました。"
    prop_map = {name: ptype for name, ptype in props}
    title_name = next((name for name, ptype in props if ptype == "title"), None)
    if not title_name:
        return "URL保存DBにTitleプロパティがありません。"
    data = {title_name: url}
    for name, ptype in props:
        if ptype == "url" and name != title_name:
            data[name] = url
            break
    return "URLをNotionに保存しました。" if create_notion_page(NOTION_URL_DATABASE_ID, data, prop_map) else "URLの保存に失敗しました。"


def _get_schema(database_id):
    now = time.time()
    cached = _SCHEMA_CACHE.get(database_id)
    if cached and now - cached[0] < _SCHEMA_CACHE_TTL:
        return cached[1]
    try:
        res = requests.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers=_notion_headers(),
            timeout=10,
        )
        if res.status_code != 200:
            return {}
        data = res.json()
        schema = {
            "title": get_database_title(database_id),
            "properties": data.get("properties", {}),
        }
        _SCHEMA_CACHE[database_id] = (now, schema)
        return schema
    except Exception as e:
        print(f"Notionスキーマ取得エラー: {e}")
        return {}


def _score_database(question, database_id):
    schema = _get_schema(database_id)
    title = schema.get("title", "")
    prop_names = " ".join(schema.get("properties", {}).keys())
    text = f"{title} {prop_names}".lower()
    question_lower = question.lower()
    score = 0
    for role, hints in ROLE_HINTS.items():
        title_match = role.lower() in text
        hint_matches = sum(1 for hint in hints if hint.lower() in question_lower)
        if title_match and hint_matches:
            score += 10 + hint_matches * 3
    for token in re.findall(r"[A-Za-z0-9一-龠ぁ-んァ-ヶー]+", question_lower):
        if len(token) >= 2 and token in text:
            score += 2
    return score


def _extract_plain_value(prop):
    ptype = prop.get("type")
    if ptype == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if ptype == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    if ptype == "number":
        return prop.get("number")
    if ptype == "select":
        obj = prop.get("select") or {}
        return obj.get("name")
    if ptype == "multi_select":
        return ", ".join(x.get("name", "") for x in prop.get("multi_select", []))
    if ptype == "date":
        obj = prop.get("date") or {}
        return obj.get("start")
    if ptype == "checkbox":
        return prop.get("checkbox")
    if ptype == "url":
        return prop.get("url")
    return None


def _query_database(database_id, date_filter=None, page_size=40):
    body = {"page_size": min(page_size, 100)}
    if date_filter:
        body["filter"] = date_filter
    results = []
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=_notion_headers(),
            json=body,
            timeout=15,
        )
        if res.status_code != 200:
            print(f"Notion DB query error ({res.status_code}): {res.text}")
            return []
        results.extend(res.json().get("results", []))
    except Exception as e:
        print(f"Notion DB query通信エラー: {e}")
    return results[:page_size]


def _find_date_property(schema):
    for name, prop in schema.get("properties", {}).items():
        if prop.get("type") == "date":
            return name
    return None


def _date_range_for_question(question):
    today = datetime.now(JST).date()
    if "今日" in question:
        start = today
        end = today + timedelta(days=1)
    elif "昨日" in question:
        start = today - timedelta(days=1)
        end = today
    elif "今週" in question:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7)
    elif "先週" in question:
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
    elif "今月" in question:
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    elif "先月" in question:
        this_month = today.replace(day=1)
        end = this_month
        if this_month.month == 1:
            start = this_month.replace(year=this_month.year - 1, month=12)
        else:
            start = this_month.replace(month=this_month.month - 1)
    elif "今年" in question:
        start = today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
    else:
        return None
    return start.isoformat(), end.isoformat()


def _serialize_database(database_id, question):
    schema = _get_schema(database_id)
    if not schema:
        return ""
    date_filter = None
    date_range = _date_range_for_question(question)
    date_prop = _find_date_property(schema)
    if date_range and date_prop:
        start, end = date_range
        date_filter = {
            "and": [
                {"property": date_prop, "date": {"on_or_after": start}},
                {"property": date_prop, "date": {"before": end}},
            ]
        }
    pages = _query_database(database_id, date_filter=date_filter, page_size=MAX_ROWS_PER_DB)
    lines = [f"【DB: {schema.get('title', '無題DB')}】"]
    for page in pages:
        props = page.get("properties", {})
        values = []
        for name, prop in props.items():
            value = _extract_plain_value(prop)
            if value not in [None, "", []]:
                values.append(f"{name}={value}")
        if values:
            lines.append("・" + " / ".join(values))
    return "\n".join(lines)


def dynamic_search_and_fetch(question):
    db_ids = get_all_database_ids()
    if not db_ids:
        return "Notionデータベースが設定されていません。"

    scored = []
    for db_id in db_ids:
        scored.append((_score_database(question, db_id), db_id))
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = [db_id for score, db_id in scored if score > 0][:MAX_AI_DATABASES]
    if not selected:
        selected = [db_id for _, db_id in scored[:MAX_AI_DATABASES]]

    chunks = []
    for db_id in selected:
        text = _serialize_database(db_id, question)
        if text:
            chunks.append(text)
    context = "\n\n".join(chunks)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n…（長いため省略）"
    return context or "該当するNotionデータが見つかりませんでした。"
