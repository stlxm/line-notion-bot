import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests

import ai_engine
import notion_helper

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
        "name": "直前登録の修正・取り消し",
        "status": "implemented",
        "aliases": ["直前登録", "直前修正", "直前取り消し", "最後の支出修正", "家計簿修正"],
        "usage": "「直前登録」で最後の家計簿を表示し、金額・店名・日付・ジャンル・支払方法を修正できます。「直前取り消し」で確認後にアーカイブできます。",
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
            "貸し借り記録", "貸し借りの記録", "お金の貸し借り",
            "お金を貸した記録", "お金を借りた記録", "返済記録",
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

CURRENT_CAPABILITIES = [
    "今月の家計簿ダッシュボード",
    "支出登録（支出 金額 店名）",
    "直前登録の確認・金額/店名/日付/ジャンル/支払方法の修正・取り消し",
    "全体予算・ジャンル予算設定",
    "毎月1日の予算設定案内",
    "今日使える額",
    "支出ペース判定",
    "異常支出検知",
    "予算提案",
    "月締め・月締め確定",
    "月次AIレビュー",
    "年間支出予測",
    "貯金目標の追加・確認・更新",
    "週次レポート",
    "固定費・サブスク管理",
    "カード未処理分類・学習・自動登録",
    "貸した・借りた・未精算一覧・精算",
    "メモ保存・一覧・削除",
    "URL保存",
    "Notion任意DBへのデータ追加",
    "AI質問（Lite / Flash切替）",
    "目的ベースのヘルプ・おすすめ・コマンド一覧",
    "サミット特売チラシ解析・生活カレンダー・LINE通知",
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

    if normalized == "機能確認":
        return ""

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


def _gemini_feature_judgement(query):
    implemented = []
    planned = []
    for feature in FEATURES:
        line = f"{feature['name']}: {feature['usage']}"
        if feature["status"] == "implemented":
            implemented.append(line)
        else:
            planned.append(line)

    prompt = (
        "あなたはLINE Notion Botの機能案内専用判定器です。\n"
        "ユーザーが欲しい機能が、現在実装済みの機能を組み合わせれば実質的に利用できるか判定してください。\n"
        "新しい機能を想像して『ある』と答えてはいけません。下記の実装済み機能と能力だけを根拠にしてください。\n"
        "正式ロードマップ予定は現在利用不可なので available=false にしてください。ただし planned=true にしてください。\n"
        "実装済み機能で実現できる場合だけ available=true にし、usageにはユーザーがそのままLINEで使える具体的なコマンド例を書いてください。\n"
        "実現できない場合は available=false, planned=false にしてください。\n"
        "必ずJSONだけで返してください。Markdownは禁止です。\n"
        "形式: {\"available\":true|false,\"planned\":true|false,\"matched_feature\":\"機能名\",\"usage\":\"使い方\",\"reason\":\"短い理由\"}\n\n"
        "【実装済み機能】\n" + "\n".join(implemented) + "\n"
        "【現在の補助能力】\n" + "\n".join(f"・{x}" for x in CURRENT_CAPABILITIES) + "\n"
        "【正式ロードマップ・未実装】\n" + "\n".join(planned) + "\n"
        f"【確認したい機能】\n{query}"
    )

    try:
        response = notion_helper.call_gemini_with_retry(ai_engine.get_selected_model(), prompt)
        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return {
            "available": bool(data.get("available")),
            "planned": bool(data.get("planned")),
            "matched_feature": str(data.get("matched_feature") or "").strip(),
            "usage": str(data.get("usage") or "").strip(),
            "reason": str(data.get("reason") or "").strip(),
        }
    except Exception as e:
        print(f"機能確認Gemini判定エラー: {e}")
        return None


def handle_feature_question(text):
    query = _extract_feature_query(text)
    if query is None:
        return None

    if not query:
        return (
            "確認したい機能名も一緒に送ってください。\n"
            "例: 機能確認 貸し借り\n"
            "例: 機能確認 家計簿を後から直す"
        )

    feature = _find_feature(query)
    if feature:
        if feature["status"] == "implemented":
            return f"✅ あります。\n【{feature['name']}】\n{feature['usage']}"
        return (
            f"🛠️「{feature['name']}」はまだ使えませんが、正式ロードマップに入っています。\n"
            f"{feature['usage']}\n\n重複要望になるため、機能追加要望DBには新規登録しませんでした。"
        )

    judgement = _gemini_feature_judgement(query)
    if judgement:
        if judgement["available"]:
            matched = judgement["matched_feature"] or "既存機能"
            usage = judgement["usage"] or judgement["reason"] or "既存機能で対応できます。"
            return "✅ あります。既存機能から判断しました。\n" + f"【{matched}】\n{usage}"
        if judgement["planned"]:
            matched = judgement["matched_feature"] or query
            detail = judgement["usage"] or judgement["reason"] or "正式ロードマップに入っています。"
            return (
                f"🛠️「{matched}」は現在まだ使えません。\n"
                f"{detail}\n\n正式ロードマップ済みなので、機能追加要望DBには重複登録しませんでした。"
            )

        saved, message = _save_request(query, text)
        if saved:
            return (
                f"今のBotには「{query}」は見つかりませんでした。\n"
                f"📝 {message}\n要望名は「{query}」のまま保存しました。"
            )
        return (
            f"今のBotには「{query}」は見つかりませんでした。\n"
            f"⚠️ {message}\nSETUP.mdの NOTION_FEATURE_REQUEST_DATABASE_ID を確認してください。"
        )

    return (
        f"「{query}」は通常の機能一覧では見つかりませんでした。\n"
        "Geminiでの追加確認に失敗したため、今回は機能追加要望DBへ自動登録していません。\n"
        "少し時間を置いて「機能確認 " + query + "」をもう一度送ってください。"
    )
