import os
import re
from datetime import datetime, timezone, timedelta

import requests

JST = timezone(timedelta(hours=9), "JST")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_FEATURE_REQUEST_DATABASE_ID = os.environ.get("NOTION_FEATURE_REQUEST_DATABASE_ID", "")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


FEATURES = [
    {
        "name": "予算設定",
        "status": "implemented",
        "aliases": ["予算", "月予算", "全体予算", "毎月1日予算"],
        "usage": "「予算設定」または「予算 100000」。毎月1日の通知から「設定する」でも入力できます。",
    },
    {
        "name": "家計簿入力",
        "status": "implemented",
        "aliases": ["支出入力", "家計簿登録", "支出登録"],
        "usage": "「支出 1200 ラーメン」のように送信します。",
    },
    {
        "name": "カード未処理整理",
        "status": "implemented",
        "aliases": ["カード未処理", "カード整理", "カード分類"],
        "usage": "「カード未処理」と送信すると未分類カードを順番に処理できます。",
    },
    {
        "name": "貸し借り管理",
        "status": "implemented",
        "aliases": [
            "貸した", "借りた", "貸し借り", "貸借", "立替", "立て替え",
            "貸し借りの記録", "貸し借り記録", "お金の貸し借り", "お金の貸し借り記録",
        ],
        "usage": "「貸した 田中 3000 ランチ代」「借りた 田中 2000」「貸し借り一覧」「精算 田中 3000」が使えます。",
    },
    {
        "name": "メモ",
        "status": "implemented",
        "aliases": ["メモ保存", "メモ一覧", "todo", "やること"],
        "usage": "「メモ 牛乳を買う」「メモ一覧」「メモ削除」が使えます。",
    },
    {
        "name": "予算提案",
        "status": "implemented",
        "aliases": ["予算おすすめ", "予算提案"],
        "usage": "「予算提案」と送ると過去実績から目安を表示します。",
    },
    {
        "name": "月次レビュー",
        "status": "implemented",
        "aliases": ["月次レビュー", "月レビュー", "振り返り"],
        "usage": "「月次レビュー」または「月次レビュー 2026-08」。",
    },
    {
        "name": "サミット特売通知",
        "status": "implemented",
        "aliases": ["チラシ", "特売", "サミット", "セール"],
        "usage": "日次トリガーで確認済み特売をLINE通知します。手動確認はGASの testTodaySummitFlyerNotification。",
    },
    {
        "name": "レシート入力",
        "status": "planned",
        "aliases": ["レシート", "レシート読取", "レシート読み取り"],
        "usage": "Phase 3Aで実装予定です。現在はまだ利用できません。",
    },
    {
        "name": "自然文家計簿入力",
        "status": "planned",
        "aliases": ["自然文入力", "自然文家計簿", "普通の文章で家計簿"],
        "usage": "Phase 3Aで実装予定です。",
    },
    {
        "name": "家計簿検索",
        "status": "planned",
        "aliases": ["検索", "家計簿検索", "過去の支出を探す"],
        "usage": "Phase 3Cで実装予定です。",
    },
    {
        "name": "CSVエクスポート",
        "status": "planned",
        "aliases": ["csv", "エクスポート", "csv出力"],
        "usage": "Phase 7で実装予定です。",
    },
    {
        "name": "月次PDFレポート",
        "status": "planned",
        "aliases": ["pdf", "pdfレポート", "月次pdf"],
        "usage": "Phase 7で実装予定です。",
    },
]


def _normalize(text):
    value = (text or "").strip().lower()
    value = value.replace("　", " ")
    value = re.sub(r"[？?！!。、,.・]", "", value)
    value = re.sub(r"\s+", "", value)
    return value


def _extract_feature_query(text):
    raw = (text or "").strip()
    normalized = raw.replace("　", " ")

    prefixes = ["機能確認 ", "機能ある？ ", "この機能ある？ ", "この機能ありますか？ "]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return normalized[len(prefix):].strip()

    if normalized.startswith("機能確認") and len(normalized) > 4:
        return normalized[4:].strip(" ：:")

    patterns = [
        r"^(.+?)(?:って|は)?(?:できる|できますか|できる\?|できる？)$",
        r"^(.+?)(?:って|は)?(?:ある|ありますか|ある\?|ある？)$",
        r"^(.+?)機能(?:って|は)?(?:ある|ありますか|ある\?|ある？)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, normalized)
        if match:
            query = match.group(1).strip()
            if query and len(query) <= 60:
                return query
    return None


def _find_feature(query):
    q = _normalize(query)
    if not q:
        return None

    best = None
    best_score = 0
    for feature in FEATURES:
        terms = [feature["name"]] + feature.get("aliases", [])
        for term in terms:
            t = _normalize(term)
            if not t:
                continue
            score = 0
            if q == t:
                score = 100
            elif t in q:
                score = 70 + min(len(t), 20)
            elif q in t and len(q) >= 2:
                score = 50 + min(len(q), 20)
            if score > best_score:
                best = feature
                best_score = score
    return best if best_score >= 52 else None


def _query_request(title):
    if not NOTION_API_KEY or not NOTION_FEATURE_REQUEST_DATABASE_ID:
        return None
    payload = {"filter": {"property": "要望", "title": {"equals": title}}, "page_size": 1}
    res = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_FEATURE_REQUEST_DATABASE_ID}/query",
        headers=_headers(), json=payload, timeout=12,
    )
    if res.status_code != 200:
        return None
    results = res.json().get("results", [])
    return results[0] if results else None


def _save_request(query, original_text):
    if not NOTION_API_KEY or not NOTION_FEATURE_REQUEST_DATABASE_ID:
        return False, "機能追加要望DBが未設定です。"

    title = query[:100].strip() or "未分類要望"
    existing = _query_request(title)
    today = datetime.now(JST).strftime("%Y-%m-%d")

    if existing:
        props = existing.get("properties", {})
        count = int(props.get("回数", {}).get("number") or 1) + 1
        payload = {"properties": {"回数": {"number": count}, "登録日": {"date": {"start": today}}}}
        try:
            res = requests.patch(
                f"https://api.notion.com/v1/pages/{existing['id']}",
                headers=_headers(), json=payload, timeout=12,
            )
            return res.status_code == 200, "既存の要望の回数を更新しました。"
        except Exception:
            return False, "要望DBの更新に失敗しました。"

    payload = {
        "parent": {"database_id": NOTION_FEATURE_REQUEST_DATABASE_ID},
        "properties": {
            "要望": {"title": [{"text": {"content": title}}]},
            "問い合わせ文": {"rich_text": [{"text": {"content": original_text[:1900]}}]},
            "状態": {"select": {"name": "未確認"}},
            "登録日": {"date": {"start": today}},
            "回数": {"number": 1},
        },
    }
    try:
        res = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json=payload, timeout=12)
        return res.status_code == 200, "機能追加要望DBへ登録しました。"
    except Exception:
        return False, "機能追加要望DBへの保存に失敗しました。"


def handle_feature_question(text):
    query = _extract_feature_query(text)
    if not query:
        return None

    feature = _find_feature(query)
    if feature:
        if feature["status"] == "implemented":
            return f"✅ あります。\n【{feature['name']}】\n{feature['usage']}"
        return (
            f"🛠️「{feature['name']}」はまだ使えませんが、正式ロードマップに入っています。\n"
            f"{feature['usage']}\n\n重複要望になるため、機能追加要望DBには新規登録しませんでした。"
        )

    saved, message = _save_request(query, text)
    if saved:
        return (
            f"今のBotには「{query}」に一致する機能は見つかりませんでした。\n"
            f"📝 {message}\n将来の追加候補として確認できるようにしておきました。"
        )
    return (
        f"今のBotには「{query}」に一致する機能は見つかりませんでした。\n"
        f"⚠️ {message}\nSETUP.mdの NOTION_FEATURE_REQUEST_DATABASE_ID を設定すると自動記録できます。"
    )
