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

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
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


def _clean_id(database_id):
    if not database_id:
        return ""
    return database_id.strip().replace("-", "")


def get_all_database_sources():
    """
    専用DB IDと NOTION_DATABASE_IDS を自動統合し、重複を除去します。
    NOTION_DATABASE_IDS には「専用変数にない追加DB」だけ設定すればOKです。
    """
    sources = [
        ("家計簿", NOTION_KAKEIBO_DATABASE_ID),
        ("月別管理", NOTION_MONTHLY_DATABASE_ID),
        ("固定費", NOTION_FIXED_DATABASE_ID),
        ("メモ", NOTION_MEMO_DATABASE_ID),
        ("URL", NOTION_URL_DATABASE_ID),
    ]
    for database_id in NOTION_DATABASE_IDS.split(","):
        database_id = database_id.strip()
        if database_id:
            sources.append(("追加DB", database_id))

    deduped = []
    seen = set()
    for role, database_id in sources:
        normalized = _clean_id(database_id)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append({"role": role, "database_id": database_id.strip()})
    return deduped


def get_all_database_ids():
    return [item["database_id"] for item in get_all_database_sources()]


def get_database_title(database_id):
    schema = _get_database_schema(database_id)
    return schema.get("title", "データベース") if schema else "データベース"


def get_database_properties(database_id):
    schema = _get_database_schema(database_id)
    if not schema:
        return []
    return list(schema.get("properties", {}).items())


def _get_database_schema(database_id, force=False):
    """DBタイトルとプロパティ型を10分キャッシュし、毎回のNotionメタデータ取得を減らします。"""
    if not database_id:
        return None

    cache_key = _clean_id(database_id)
    now = time.time()
    cached = _SCHEMA_CACHE.get(cache_key)
    if cached and not force and now - cached["cached_at"] < _SCHEMA_CACHE_TTL:
        return cached["schema"]

    url = f"https://api.notion.com/v1/databases/{database_id}"
    try:
        res = requests.get(url, headers=_notion_headers(), timeout=7)
        if res.status_code != 200:
            print(f"DBスキーマ取得エラー ({res.status_code}): {res.text}")
            return None

        data = res.json()
        title_list = data.get("title", [])
        title = "".join(x.get("plain_text", "") for x in title_list).strip() or "データベース"
        properties = {}
        for name, details in data.get("properties", {}).items():
            p_type = details.get("type")
            if p_type:
                properties[name] = p_type

        schema = {
            "database_id": database_id,
            "title": title,
            "properties": properties,
        }
        _SCHEMA_CACHE[cache_key] = {"cached_at": now, "schema": schema}
        return schema
    except Exception as e:
        print(f"DBスキーマ取得エラー: {e}")
        return None


def create_notion_page(database_id, collected_data, prop_types):
    if not database_id:
        return False

    properties = {}
    for prop_name, val in collected_data.items():
        p_type = prop_types.get(prop_name)
        if p_type == "title":
            properties[prop_name] = {"title": [{"text": {"content": val}}]}
        elif p_type == "rich_text":
            properties[prop_name] = {"rich_text": [{"text": {"content": val}}]}
        elif p_type == "number":
            try:
                properties[prop_name] = {"number": float(val)}
            except ValueError:
                properties[prop_name] = {"number": 0}
        elif p_type == "select":
            properties[prop_name] = {"select": {"name": val}}
        elif p_type == "multi_select":
            values = [x.strip() for x in re.split(r"[,、]", val) if x.strip()]
            properties[prop_name] = {"multi_select": [{"name": x} for x in values]}
        elif p_type == "checkbox":
            properties[prop_name] = {"checkbox": str(val).lower() in ["true", "1", "yes", "はい", "on"]}
        elif p_type == "date":
            properties[prop_name] = {"date": {"start": val}}
        elif p_type == "url":
            properties[prop_name] = {"url": val}

    payload = {"parent": {"database_id": database_id}, "properties": properties}
    try:
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_notion_headers(),
            json=payload,
            timeout=7,
        )
        if res.status_code == 200:
            return True
        print(f"Notionページ作成エラー ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Notionページ作成エラー: {e}")
    return False


def add_url_to_notion(url_text):
    if not NOTION_URL_DATABASE_ID:
        return "URL保存先のデータベースが設定されていません。"

    payload = {
        "parent": {"database_id": NOTION_URL_DATABASE_ID},
        "properties": {"URL": {"title": [{"text": {"content": url_text}}]}},
    }
    try:
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_notion_headers(),
            json=payload,
            timeout=7,
        )
        if res.status_code == 200:
            return "後で見るURLデータベースに保存しました！"
        print(f"URL保存エラー ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"URL保存エラー: {e}")
    return "URLの保存に失敗しました。"


def fetch_notion_context():
    """互換性維持用。AI検索は dynamic_search_and_fetch() を利用します。"""
    return ""


def _text_similarity(question, text):
    question = question.lower().replace(" ", "")
    text = text.lower().replace(" ", "")
    if not text or text in ["db", "database", "データベース", "管理", "一覧"]:
        return 0
    if text in question:
        return 8
    if len(text) >= 2:
        ratio = SequenceMatcher(None, text, question).ratio()
        if ratio >= 0.45:
            return ratio * 4
    return 0


def _score_database(question, source, schema):
    q = question.lower()
    score = 0.0
    reasons = []

    role = source["role"]
    for keyword in ROLE_HINTS.get(role, []):
        if keyword.lower() in q:
            score += 6
            reasons.append(f"role:{keyword}")

    title = schema.get("title", "")
    title_score = _text_similarity(question, title)
    if title_score:
        score += title_score + 4
        reasons.append(f"title:{title}")

    for prop_name in schema.get("properties", {}):
        prop_score = _text_similarity(question, prop_name)
        if prop_score:
            score += min(5, prop_score)
            reasons.append(f"prop:{prop_name}")

    prop_types = set(schema.get("properties", {}).values())
    if any(word in q for word in ["いくら", "金額", "合計", "平均", "高い", "安い"]) and "number" in prop_types:
        score += 2
    if any(word in q for word in ["今日", "昨日", "今週", "先週", "今月", "先月", "今年", "最近"]) and "date" in prop_types:
        score += 2
    if any(word in q for word in ["種類", "カテゴリ", "ジャンル", "分類"]) and ("select" in prop_types or "multi_select" in prop_types):
        score += 2

    return score, reasons


def _build_catalog():
    catalog = []
    for source in get_all_database_sources():
        schema = _get_database_schema(source["database_id"])
        if not schema:
            continue
        item = dict(source)
        item["schema"] = schema
        catalog.append(item)
    return catalog


def select_databases_for_question(question, max_databases=MAX_AI_DATABASES):
    """Geminiを使わず、DB名・専用役割・プロパティ名・型から最大2DBを選択します。"""
    catalog = _build_catalog()
    if not catalog:
        return []

    scored = []
    for item in catalog:
        score, reasons = _score_database(question, item, item["schema"])
        scored.append((score, item, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    positive = [x for x in scored if x[0] > 0]

    if positive:
        selected = positive[:max_databases]
    else:
        extras = [x for x in scored if x[1]["role"] == "追加DB"]
        selected = (extras or scored)[:max_databases]

    print(
        "[AI Router] "
        + " / ".join(
            f"{x[1]['schema']['title']} score={x[0]:.1f} reasons={','.join(x[2][:4]) or '-'}"
            for x in selected
        )
    )
    return [x[1] for x in selected]


def _date_range_from_question(question):
    now = datetime.now(JST)
    today = now.date()

    if "今日" in question:
        start = today
        end = today + timedelta(days=1)
    elif "昨日" in question:
        start = today - timedelta(days=1)
        end = today
    elif "先週" in question:
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday
    elif "今週" in question:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7)
    elif "先月" in question:
        first_this_month = today.replace(day=1)
        end = first_this_month
        prev_last_day = first_this_month - timedelta(days=1)
        start = prev_last_day.replace(day=1)
    elif "今月" in question:
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    elif "今年" in question:
        start = today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
    else:
        return None

    return start.isoformat(), end.isoformat()


def _build_query_payload(question, schema):
    payload = {"page_size": MAX_ROWS_PER_DB}
    date_props = [name for name, p_type in schema.get("properties", {}).items() if p_type == "date"]
    period = _date_range_from_question(question)

    if date_props:
        date_prop = date_props[0]
        payload["sorts"] = [{"property": date_prop, "direction": "descending"}]
        if period:
            start, end = period
            payload["filter"] = {
                "and": [
                    {"property": date_prop, "date": {"on_or_after": start}},
                    {"property": date_prop, "date": {"before": end}},
                ]
            }
    return payload


def _property_to_text(prop_val):
    v_type = prop_val.get("type")
    if v_type == "title":
        return "".join(x.get("plain_text", "") for x in prop_val.get("title", []))
    if v_type == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop_val.get("rich_text", []))
    if v_type == "number":
        value = prop_val.get("number")
        return "" if value is None else str(value)
    if v_type == "select":
        value = prop_val.get("select")
        return value.get("name", "") if value else ""
    if v_type == "multi_select":
        return ", ".join(x.get("name", "") for x in prop_val.get("multi_select", []) if x.get("name"))
    if v_type == "date":
        value = prop_val.get("date")
        if not value:
            return ""
        start = value.get("start", "")
        end = value.get("end")
        return f"{start}〜{end}" if end else start
    if v_type == "checkbox":
        return "はい" if prop_val.get("checkbox") else "いいえ"
    if v_type == "url":
        return prop_val.get("url") or ""
    if v_type == "status":
        value = prop_val.get("status")
        return value.get("name", "") if value else ""
    return ""


def _fetch_database_context(question, item):
    database_id = item["database_id"]
    schema = item["schema"]
    query_url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = _build_query_payload(question, schema)

    try:
        response = requests.post(
            query_url,
            headers=_notion_headers(),
            json=payload,
            timeout=10,
        )
    except Exception as e:
        return f"--- データベース: {schema['title']} ---\n取得エラー: {e}"

    if response.status_code != 200:
        return f"--- データベース: {schema['title']} ---\nNotion検索エラー: {response.text[:500]}"

    results = response.json().get("results", [])
    lines = [f"--- データベース: {schema['title']} / {len(results)}件 ---"]

    for page in results[:MAX_ROWS_PER_DB]:
        row_parts = []
        for prop_name, prop_val in page.get("properties", {}).items():
            text = _property_to_text(prop_val)
            if text:
                row_parts.append(f"{prop_name}: {text}")
        if row_parts:
            lines.append(" | ".join(row_parts))

    if len(lines) == 1:
        lines.append("該当データなし")
    return "\n".join(lines)


def dynamic_search_and_fetch(user_message):
    """
    質問内容から必要なDBをPythonで選び、最大2DBだけ取得します。
    DB選択にはGemini APIを使いません。
    """
    selected = select_databases_for_question(user_message)
    if not selected:
        return "参照可能なNotionデータベースが設定されていません。"

    contexts = []
    total_chars = 0
    for item in selected:
        context = _fetch_database_context(user_message, item)
        remaining = MAX_CONTEXT_CHARS - total_chars
        if remaining <= 0:
            break
        context = context[:remaining]
        contexts.append(context)
        total_chars += len(context)

    return "\n\n".join(contexts)


def generate_gemini_response(user_message, notion_context=""):
    """
    1質問につきGeminiは最終回答生成の1回だけ呼び出します。
    DBルーティングはPython、Notion取得後の要約・分析のみGeminiが担当します。
    """
    try:
        dynamic_context = dynamic_search_and_fetch(user_message)
        prompt = (
            "あなたはユーザーのNotionデータを管理・参照するパーソナルアシスタントです。"
            "以下のNotion検索結果だけを根拠として、日本語で簡潔かつ正確に答えてください。"
            "情報が不足している場合は推測せず、不足していると伝えてください。\n\n"
            f"【Notion検索結果】\n{dynamic_context}\n\n"
            f"【ユーザーからの質問】\n{user_message}"
        )
        response = call_gemini_with_retry(GEMINI_MODEL, prompt)
        return response.text
    except Exception as e:
        print(f"Gemini APIエラー: {e}")
        return f"AIの応答生成中にエラーが発生しました: {str(e)}"
