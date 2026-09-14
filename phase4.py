import calendar
import html
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import requests

JST = timezone(timedelta(hours=9), "JST")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_MEMO_DATABASE_ID = os.environ.get("NOTION_MEMO_DATABASE_ID", "")
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")

WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _schema(db_id):
    if not db_id or not NOTION_API_KEY:
        return {}
    try:
        r = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=_headers(), timeout=10)
        if r.status_code == 200:
            return r.json().get("properties", {})
        print(f"Phase4 schema error ({r.status_code}): {r.text[:500]}")
    except Exception as e:
        print(f"Phase4 schema exception: {e}")
    return {}


def _title_name(schema):
    return next((name for name, prop in schema.items() if prop.get("type") == "title"), None)


def _plain(prop):
    ptype = (prop or {}).get("type")
    values = (prop or {}).get(ptype, []) if ptype in {"title", "rich_text"} else []
    return "".join(x.get("plain_text", "") for x in (values or []))


def _month_end(year, month):
    return datetime(year, month, calendar.monthrange(year, month)[1]).date()


def _weekday_date(today, weekday, mode="next"):
    target = WEEKDAYS[weekday]
    if mode == "next_week":
        monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return monday + timedelta(days=target)
    if mode == "this_week":
        monday = today - timedelta(days=today.weekday())
        return monday + timedelta(days=target)
    delta = (target - today.weekday()) % 7
    return today + timedelta(days=delta)


def _due_date(text):
    """メモ本文に明示された自然な期限表現をJSTの日付へ変換する。

    内容だけから勝手に期限を推測はしない。日付・曜日・相対表現がある時だけ期限を付ける。
    """
    today = datetime.now(JST).date()
    value = str(text or "")

    if "明後日" in value:
        return (today + timedelta(days=2)).isoformat()
    if "明日" in value:
        return (today + timedelta(days=1)).isoformat()
    if "今日" in value or "本日" in value:
        return today.isoformat()

    m = re.search(r"(\d+)\s*日後", value)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s*週間後", value)
    if m:
        return (today + timedelta(weeks=int(m.group(1)))).isoformat()

    if "来月末" in value or "来月中" in value:
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        return _month_end(year, month).isoformat()
    if "今月末" in value or "今月中" in value or re.search(r"(?<!来)月末", value):
        return _month_end(today.year, today.month).isoformat()

    if "来週中" in value:
        monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return (monday + timedelta(days=6)).isoformat()
    if "今週中" in value or re.search(r"(?<!来)週末", value):
        monday = today - timedelta(days=today.weekday())
        return (monday + timedelta(days=6)).isoformat()

    m = re.search(r"来週(?:の)?([月火水木金土日])曜(?:日)?", value)
    if m:
        return _weekday_date(today, m.group(1), "next_week").isoformat()
    m = re.search(r"今週(?:の)?([月火水木金土日])曜(?:日)?", value)
    if m:
        return _weekday_date(today, m.group(1), "this_week").isoformat()
    m = re.search(r"(?:次の)?([月火水木金土日])曜(?:日)?(?:まで(?:に)?|迄(?:に)?)?", value)
    if m:
        return _weekday_date(today, m.group(1), "next").isoformat()

    m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?", value)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
        except ValueError:
            pass

    m = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日", value)
    if m:
        try:
            d = datetime(today.year, int(m.group(1)), int(m.group(2))).date()
            if d < today - timedelta(days=30):
                d = d.replace(year=today.year + 1)
            return d.isoformat()
        except ValueError:
            pass

    m = re.search(r"(?<!\d)(\d{1,2})[/-](\d{1,2})", value)
    if m:
        try:
            d = datetime(today.year, int(m.group(1)), int(m.group(2))).date()
            if d < today - timedelta(days=30):
                d = d.replace(year=today.year + 1)
            return d.isoformat()
        except ValueError:
            pass
    return None


def _clean_due_words(text):
    value = str(text or "").strip()
    suffix = r"(?:まで(?:に)?|迄(?:に)?)?"
    patterns = [
        rf"(?:今日|本日|明日|明後日){suffix}",
        rf"\d+\s*(?:日後|週間後){suffix}",
        rf"(?:今週中|来週中|週末|今月中|今月末|来月中|来月末|月末){suffix}",
        rf"(?:今週|来週)(?:の)?[月火水木金土日]曜(?:日)?{suffix}",
        rf"(?:次の)?[月火水木金土日]曜(?:日)?{suffix}",
        rf"20\d{{2}}[-/年]\d{{1,2}}[-/月]\d{{1,2}}日?{suffix}",
        rf"(?<!\d)\d{{1,2}}月\d{{1,2}}日{suffix}",
        rf"(?<!\d)\d{{1,2}}[/-]\d{{1,2}}{suffix}",
    ]
    for pattern in patterns:
        value = re.sub(pattern, "", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = re.sub(r"を\s*に(?=[一-龠ぁ-んァ-ヶ])", "を", value)
    return value.strip(" 　、,")


def classify_memo(text, forced=None):
    if forced:
        return forced
    value = str(text or "").lower()
    if any(k in value for k in ["買う", "購入", "買って", "買い物", "補充", "スーパー", "ドラッグストア"]):
        return "買い物"
    if any(k in value for k in ["提出", "申請", "連絡", "返信", "予約", "支払", "払う", "やる", "する", "確認"]):
        return "やること"
    if any(k in value for k in ["予定", "会議", "面談", "ライブ", "旅行", "病院", "美容院"]):
        return "予定"
    if any(k in value for k in ["アイデア", "案", "思いつ", "作りたい", "試したい"]):
        return "アイデア"
    return "その他"


def add_smart_memo(text, forced_category=None):
    if not NOTION_MEMO_DATABASE_ID:
        return "メモDB IDが設定されていません。"
    raw = str(text or "").strip()
    if not raw:
        return "内容を入力してください。例: メモ 住民票を明日までに提出"
    schema = _schema(NOTION_MEMO_DATABASE_ID)
    title = _title_name(schema)
    if not title:
        return "メモDBのTitleプロパティを確認できませんでした。"
    due = _due_date(raw)
    cleaned = _clean_due_words(raw) or raw
    category = classify_memo(cleaned, forced_category)
    props = {title: {"title": [{"text": {"content": cleaned[:2000]}}]}}
    if schema.get("日付", {}).get("type") == "date":
        props["日付"] = {"date": {"start": datetime.now(JST).isoformat()}}
    if due and schema.get("期限", {}).get("type") == "date":
        props["期限"] = {"date": {"start": due}}
    if schema.get("分類", {}).get("type") == "select":
        props["分類"] = {"select": {"name": category}}
    if schema.get("完了", {}).get("type") == "checkbox":
        props["完了"] = {"checkbox": False}
    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json={"parent": {"database_id": NOTION_MEMO_DATABASE_ID}, "properties": props}, timeout=12)
        if r.status_code != 200:
            print(f"Phase4 memo save error ({r.status_code}): {r.text[:700]}")
            return "メモの保存に失敗しました。"
    except Exception as e:
        return f"メモ保存中に通信エラーが発生しました: {e}"
    lines = ["✅ メモを保存しました。", f"内容: {cleaned}", f"分類: {category}"]
    if due:
        lines.append(f"期限: {due}")
    else:
        lines.append("期限: なし")
    return "\n".join(lines)


def _memo_pages():
    if not NOTION_MEMO_DATABASE_ID:
        return []
    try:
        r = requests.post(f"https://api.notion.com/v1/databases/{NOTION_MEMO_DATABASE_ID}/query", headers=_headers(), json={"page_size": 100}, timeout=12)
        return r.json().get("results", []) if r.status_code == 200 else []
    except Exception as e:
        print(f"Phase4 memo query exception: {e}")
        return []


def build_memo_list(category=None):
    schema = _schema(NOTION_MEMO_DATABASE_ID)
    title = _title_name(schema)
    rows = []
    for page in _memo_pages():
        props = page.get("properties", {})
        if props.get("完了", {}).get("checkbox") is True:
            continue
        item_category = (props.get("分類", {}).get("select") or {}).get("name", "")
        if category and item_category != category:
            continue
        due = ((props.get("期限", {}).get("date") or {}).get("start") or "")[:10]
        rows.append((_plain(props.get(title, {})) or "無題", item_category or "未分類", due))
    rows.sort(key=lambda x: (x[2] == "", x[2], x[0]))
    label = "買い物リスト" if category == "買い物" else "メモ一覧"
    if not rows:
        return f"【{label}】\n現在、未完了の項目はありません。"
    lines = [f"【{label}】"]
    for name, cat, due in rows[:30]:
        category_text = "" if category else f" / {cat}"
        due_text = f" / 期限 {due}" if due else ""
        lines.append(f"・{name}{category_text}{due_text}")
    if len(rows) > 30:
        lines.append(f"\nほか {len(rows)-30} 件あります。")
    if category == "買い物":
        lines.append("\n購入済みは「買った 商品名」と送信できます。")
    return "\n".join(lines)


def complete_shopping_item(keyword):
    key = str(keyword or "").strip()
    if not key:
        return "「買った 牛乳」のように商品名を続けてください。"
    schema = _schema(NOTION_MEMO_DATABASE_ID)
    title = _title_name(schema)
    matches = []
    for page in _memo_pages():
        props = page.get("properties", {})
        cat = (props.get("分類", {}).get("select") or {}).get("name", "")
        name = _plain(props.get(title, {}))
        if cat == "買い物" and props.get("完了", {}).get("checkbox") is not True and key.lower() in name.lower():
            matches.append((page.get("id"), name))
    if not matches:
        return f"買い物リストに「{key}」が見つかりませんでした。"
    if len(matches) > 1:
        return "「{}」に一致する項目が複数あります。もう少し詳しく指定してください。\n{}".format(key, "\n".join(f"・{x[1]}" for x in matches[:8]))
    try:
        r = requests.patch(f"https://api.notion.com/v1/pages/{matches[0][0]}", headers=_headers(), json={"properties": {"完了": {"checkbox": True}}}, timeout=12)
        return f"✅「{matches[0][1]}」を購入済みにしました。" if r.status_code == 200 else "購入済みへの更新に失敗しました。"
    except Exception as e:
        return f"更新中に通信エラーが発生しました: {e}"


def _page_title(url):
    try:
        r = requests.get(url, timeout=10, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; LINE-Notion-Bot/1.0)"})
        if r.status_code >= 400:
            return ""
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text[:300000], flags=re.IGNORECASE | re.DOTALL)
        return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:500] if m else ""
    except Exception as e:
        print(f"URL title fetch error: {e}")
        return ""


def classify_url(url, title=""):
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    text = f"{host} {parsed.path} {title}".lower()
    if any(x in host for x in ["youtube.com", "youtu.be", "nicovideo.jp", "tiktok.com"]):
        return "動画"
    if any(x in host for x in ["x.com", "twitter.com", "instagram.com", "threads.net", "facebook.com"]):
        return "SNS"
    if any(x in host for x in ["amazon.", "rakuten.", "yahoo.co.jp", "zozo.jp", "mercari.com"]):
        return "買い物"
    if any(x in text for x in [".pdf", "/docs", "/document", "slides", "drive.google"]):
        return "資料"
    if any(x in text for x in ["news", "article", "blog", "note.com", "qiita.com", "zenn.dev", "medium.com"]):
        return "記事"
    return "その他"


def save_url(url):
    if not NOTION_URL_DATABASE_ID:
        return "URL保存DBが設定されていません。"
    schema = _schema(NOTION_URL_DATABASE_ID)
    title_name = _title_name(schema)
    if not title_name:
        return "URL保存DBのTitleプロパティを確認できませんでした。"
    page_title = _page_title(url)
    domain = (urlparse(url).netloc or "").removeprefix("www.")
    category = classify_url(url, page_title)
    now = datetime.now(JST)
    props = {title_name: {"title": [{"text": {"content": url[:2000]}}]}}
    if "ページタイトル" in schema:
        props["ページタイトル"] = {"rich_text": [{"text": {"content": (page_title or domain or url)[:2000]}}]}
    if "カテゴリ" in schema:
        props["カテゴリ"] = {"select": {"name": category}}
    if "ドメイン" in schema:
        props["ドメイン"] = {"rich_text": [{"text": {"content": domain[:2000]}}]}
    if "保存日時" in schema:
        props["保存日時"] = {"date": {"start": now.isoformat()}}
    if schema.get("時間", {}).get("type") == "rich_text":
        props["時間"] = {"rich_text": [{"text": {"content": now.strftime("%Y-%m-%d %H:%M")}}]}
    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json={"parent": {"database_id": NOTION_URL_DATABASE_ID}, "properties": props}, timeout=12)
        if r.status_code != 200:
            print(f"Phase4 URL save error ({r.status_code}): {r.text[:700]}")
            return "URLの保存に失敗しました。"
    except Exception as e:
        return f"URL保存中に通信エラーが発生しました: {e}"
    return f"✅ URLを保存しました。\nタイトル: {page_title or 'タイトル取得不可'}\nカテゴリ: {category}\nドメイン: {domain}"


def handle_text_command(text):
    message = str(text or "").strip().replace("　", " ")
    if message.lower() in {"phase4", "フェーズ4"}:
        return (
            "【Phase 4】\n"
            "メモ本文の期限表現を自動で読み取ります。期限が書かれていなければ期限なしです。\n\n"
            "例:\n"
            "・メモ 住民票を明日までに提出\n"
            "・メモ レポートを金曜までに出す\n"
            "・メモ 更新手続きを3日後までに確認\n"
            "・メモ 書類提出 9月20日まで\n"
            "・メモ 課題を来週月曜までに終える\n"
            "・買い物 牛乳\n"
            "・買い物リスト\n"
            "・買った 牛乳\n"
            "・URLをそのまま送信 → タイトル/カテゴリ付き保存"
        )
    if message.startswith("買い物 "):
        return add_smart_memo(message[4:].strip(), "買い物")
    if message in ["買い物リスト", "買物リスト", "買うもの"]:
        return build_memo_list("買い物")
    if message.startswith("買った "):
        return complete_shopping_item(message[4:].strip())
    if message.startswith("メモ "):
        return add_smart_memo(message[3:].strip())
    if message in ["メモ一覧", "メモ確認"]:
        return build_memo_list()
    if message.startswith("http://") or message.startswith("https://"):
        return save_url(message)
    return None
