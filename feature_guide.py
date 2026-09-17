import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests

import ai_engine
import notion_helper
import phase4
import phase5

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
    {"name": "予算設定", "status": "implemented", "aliases": ["予算", "月予算", "全体予算", "毎月1日予算", "ジャンル予算"], "usage": "「予算 100000」「予算 お菓子 3000」「予算 2026-10 食費 35000」が使えます。"},
    {"name": "家計簿入力", "status": "implemented", "aliases": ["支出入力", "家計簿登録", "支出登録"], "usage": "「支出 1200 ラーメン」のように送信します。"},
    {"name": "自然文家計簿入力", "status": "implemented", "aliases": ["自然文入力", "自然文家計簿", "普通の文章で家計簿"], "usage": "「今日サミットで2380円使った」のように送れます。不足項目はボタンで確認します。"},
    {"name": "支出テンプレート", "status": "implemented", "aliases": ["よく使う支出", "テンプレート", "支出テンプレ"], "usage": "「支出テンプレート」と送ると直近90日から候補を表示します。"},
    {"name": "本日のレポート", "status": "implemented", "aliases": ["今日のレポート", "日次レポート", "本日レポート"], "usage": "「本日のレポート」で今日の支出・今月残り予算・カード未処理などをまとめて表示します。"},
    {"name": "直前登録の修正・取り消し", "status": "implemented", "aliases": ["直前登録", "直前修正", "直前取り消し", "最後の支出修正", "家計簿修正"], "usage": "「直前登録」で最新家計簿を表示し、金額・店名・日付・ジャンル・支払方法を修正できます。"},
    {"name": "カード未処理整理", "status": "implemented", "aliases": ["カード未処理", "カード整理", "カード分類"], "usage": "「カード未処理」で未分類カードを順番に処理できます。"},
    {"name": "カード店名の小書き文字補正", "status": "implemented", "aliases": ["店名補正", "店名自動補正", "小文字補正", "小書き文字補正", "サミツト", "サミット"], "usage": "カード未処理の店名変更で「サミツト→サミット」のように小書き文字だけ直すと、その補正を学習します。過去の同じ旧店名も家計簿・未処理・固定費で一括修正し、次回から自動補正します。"},
    {"name": "貸し借り管理", "status": "implemented", "aliases": ["貸した", "借りた", "貸し借り", "貸借", "立替", "立て替え", "貸し借り記録", "貸し借りの記録", "お金の貸し借り", "返済記録"], "usage": "「貸した 田中 3000 ランチ代」「借りた 田中 2000」「貸し借り一覧」「精算 田中 3000」が使えます。"},
    {"name": "メモ期限・自動分類", "status": "implemented", "aliases": ["メモ", "メモ保存", "メモ一覧", "todo", "やること", "メモ期限", "メモ分類"], "usage": "「メモ 住民票を明日までに提出」のように送ると、期限と分類を自動保存します。"},
    {"name": "買い物リスト", "status": "implemented", "aliases": ["買い物", "買うもの", "買い物メモ", "買い物リスト"], "usage": "「買い物 牛乳」で追加、「買い物リスト」で一覧、「買った 牛乳」で完了にできます。"},
    {"name": "URLタイトル取得・分類", "status": "implemented", "aliases": ["URL保存", "リンク保存", "URLタイトル", "URL分類", "後で見る"], "usage": "URLをそのまま送るとページタイトル・カテゴリ・ドメインを取得してNotionへ保存します。"},
    {"name": "AI回答評価", "status": "implemented", "aliases": ["AI評価", "👍", "👎", "AIフィードバック"], "usage": "AI回答の後に「AI評価 👍」または「AI評価 👎」で評価を保存できます。👎の後は「AI改善」で具体的な修正を残せます。"},
    {"name": "AI参照DB・根拠表示", "status": "implemented", "aliases": ["参照DB", "AI根拠", "根拠表示", "AIの根拠"], "usage": "AI回答の末尾に【参照DB】と【根拠】を自動表示します。"},
    {"name": "AI改善DBルーター反映", "status": "implemented", "aliases": ["AI改善ルーター", "DBルーター", "AI改善反映"], "usage": "過去の👎/改善ログに残った参照DBを、似た質問の次回DB選択候補へ反映します。"},
    {"name": "Notion DBヘルスチェック", "status": "implemented", "aliases": ["DBヘルス", "Notionヘルス", "DBチェック", "Notion DBチェック"], "usage": "「DBヘルスチェック」で環境変数・DBアクセス・必須プロパティをまとめて確認します。"},
    {"name": "予算提案", "status": "implemented", "aliases": ["予算おすすめ", "予算提案"], "usage": "「予算提案」で過去実績から目安を表示します。"},
    {"name": "月次レビュー", "status": "implemented", "aliases": ["月次レビュー", "月レビュー", "振り返り"], "usage": "「月次レビュー」または「月次レビュー 2026-08」。"},
    {"name": "サミット特売情報", "status": "implemented", "aliases": ["チラシ", "特売", "特売情報", "今日の特売", "サミット", "セール"], "usage": "LINEで「特売」「特売情報」「今日の特売」と送ると、生活カレンダーの今日の特売を最大20件表示します。チラシは手動確認なしで自動反映する運用です。"},
    {"name": "家計簿検索", "status": "planned", "aliases": ["検索", "家計簿検索", "過去の支出を探す"], "usage": "Phase 3Cで実装予定です。"},
    {"name": "CSVエクスポート", "status": "planned", "aliases": ["csv", "エクスポート", "csv出力"], "usage": "Phase 7で実装予定です。"},
    {"name": "月次PDFレポート", "status": "planned", "aliases": ["pdf", "pdfレポート", "月次pdf"], "usage": "Phase 7で実装予定です。"},
]

CURRENT_CAPABILITIES = [
    "今月の家計簿ダッシュボード", "自然文を含む支出登録", "よく使う支出テンプレート", "本日のレポート",
    "直前登録の修正・取り消し", "全体予算・ジャンル予算設定", "毎月1日の予算設定案内", "今日使える額",
    "支出ペース判定", "異常支出検知", "予算提案", "月締め・月次AIレビュー", "年間支出予測",
    "貯金目標", "週次レポート", "固定費・サブスク管理", "カード未処理分類・学習・自動登録・店名小書き文字補正学習・過去同名店の一括修正",
    "貸した・借りた・未精算一覧・精算", "期限付きメモ・メモ自動分類・買い物リスト",
    "URLタイトル取得・URLカテゴリ分類・URL保存", "Notion任意DBへのデータ追加",
    "サミット特売チラシ解析・生活カレンダー・今日の特売コマンド・LINE通知・手動確認なしの自動反映",
    "AI質問（Lite / Flash切替）・AI評価・参照DB表示・根拠表示・改善ログによるDBルーター補助・DBヘルスチェック",
    "目的ベースのヘルプ・おすすめ・コマンド一覧",
]


def _normalize(text):
    value = (text or "").strip().lower().replace("　", " ")
    value = re.sub(r"[？?！!。、,.・]", "", value)
    return re.sub(r"\s+", "", value)


def _extract_feature_query(text):
    raw = (text or "").strip().replace("　", " ")
    if raw == "機能確認":
        return ""
    for prefix in ["機能確認 ", "機能ある？ ", "この機能ある？ ", "この機能ありますか？ "]:
        if raw.startswith(prefix):
            return raw[len(prefix):].strip()
    if raw.startswith("機能確認") and len(raw) > 4:
        return raw[4:].strip(" ：:")
    for pattern in [
        r"^(.+?)(?:って|は)?(?:できる|できますか|できる\?|できる？)$",
        r"^(.+?)(?:って|は)?(?:ある|ありますか|ある\?|ある？)$",
        r"^(.+?)機能(?:って|は)?(?:ある|ありますか|ある\?|ある？)$",
    ]:
        match = re.match(pattern, raw)
        if match and 0 < len(match.group(1).strip()) <= 60:
            return match.group(1).strip()
    return None


def _find_feature(query):
    q = _normalize(query)
    best, score_best = None, 0
    for feature in FEATURES:
        for term in [feature["name"]] + feature.get("aliases", []):
            t = _normalize(term)
            score = 100 if q == t else (70 + min(len(t), 20) if t and t in q else (50 + min(len(q), 20) if q and q in t and len(q) >= 2 else 0))
            if score > score_best:
                best, score_best = feature, score
    return best if score_best >= 52 else None


def _query_request(title):
    if not NOTION_API_KEY or not NOTION_FEATURE_REQUEST_DATABASE_ID:
        return None
    res = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_FEATURE_REQUEST_DATABASE_ID}/query",
        headers=_headers(), json={"filter": {"property": "要望", "title": {"equals": title}}, "page_size": 1}, timeout=12,
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
    try:
        if existing:
            count = int(existing.get("properties", {}).get("回数", {}).get("number") or 1) + 1
            res = requests.patch(
                f"https://api.notion.com/v1/pages/{existing['id']}", headers=_headers(),
                json={"properties": {"回数": {"number": count}, "登録日": {"date": {"start": today}}}}, timeout=12,
            )
            return res.status_code == 200, "既存の要望の回数を更新しました。"
        payload = {
            "parent": {"database_id": NOTION_FEATURE_REQUEST_DATABASE_ID},
            "properties": {
                "要望": {"title": [{"text": {"content": title}}]},
                "問い合わせ文": {"rich_text": [{"text": {"content": original_text[:1900]}}]},
                "状態": {"select": {"name": "未確認"}}, "登録日": {"date": {"start": today}}, "回数": {"number": 1},
            },
        }
        res = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json=payload, timeout=12)
        return res.status_code == 200, "機能追加要望DBへ登録しました。"
    except Exception:
        return False, "機能追加要望DBへの保存に失敗しました。"


def _gemini_feature_judgement(query):
    implemented, planned = [], []
    for feature in FEATURES:
        line = f"{feature['name']}: {feature['usage']}"
        (implemented if feature["status"] == "implemented" else planned).append(line)
    prompt = (
        "あなたはLINE Notion Botの機能案内専用判定器です。新機能を想像せず、下記能力だけで判定してください。"
        "正式ロードマップ予定は available=false, planned=true。実装済みで実現できる場合だけ available=true。"
        "必ずJSONだけで返してください。形式: "
        "{\"available\":true|false,\"planned\":true|false,\"matched_feature\":\"機能名\",\"usage\":\"使い方\",\"reason\":\"理由\"}\n\n"
        "【実装済み】\n" + "\n".join(implemented) + "\n【能力】\n" + "\n".join(CURRENT_CAPABILITIES) +
        "\n【未実装ロードマップ】\n" + "\n".join(planned) + f"\n【確認】\n{query}"
    )
    try:
        response = notion_helper.call_gemini_with_retry(ai_engine.get_selected_model(), prompt)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (response.text or "").strip(), flags=re.IGNORECASE)
        data = json.loads(raw)
        return {"available": bool(data.get("available")), "planned": bool(data.get("planned")), "matched_feature": str(data.get("matched_feature") or "").strip(), "usage": str(data.get("usage") or "").strip(), "reason": str(data.get("reason") or "").strip()}
    except Exception as e:
        print(f"機能確認Gemini判定エラー: {e}")
        return None


def handle_feature_question(text):
    phase4_reply = phase4.handle_text_command(text)
    if phase4_reply is not None:
        return phase4_reply

    phase5_reply = phase5.handle_text_command(text)
    if phase5_reply is not None:
        return phase5_reply

    query = _extract_feature_query(text)
    if query is None:
        return None
    if not query:
        return "確認したい機能名も一緒に送ってください。\n例: 機能確認 買い物リスト\n例: 機能確認 DBヘルス"
    feature = _find_feature(query)
    if feature:
        if feature["status"] == "implemented":
            return f"✅ あります。\n【{feature['name']}】\n{feature['usage']}"
        return f"🛠️「{feature['name']}」はまだ使えませんが、正式ロードマップに入っています。\n{feature['usage']}\n\n重複要望になるため、機能追加要望DBには新規登録しませんでした。"
    judgement = _gemini_feature_judgement(query)
    if judgement:
        if judgement["available"]:
            return f"✅ あります。既存機能から判断しました。\n【{judgement['matched_feature'] or '既存機能'}】\n{judgement['usage'] or judgement['reason'] or '既存機能で対応できます。'}"
        if judgement["planned"]:
            return f"🛠️「{judgement['matched_feature'] or query}」は現在まだ使えません。\n{judgement['usage'] or judgement['reason'] or '正式ロードマップに入っています。'}\n\n機能追加要望DBには重複登録しませんでした。"
        saved, message = _save_request(query, text)
        return (f"今のBotには「{query}」は見つかりませんでした。\n📝 {message}\n要望名は「{query}」のまま保存しました。" if saved else f"今のBotには「{query}」は見つかりませんでした。\n⚠️ {message}")
    return f"「{query}」は通常の機能一覧では見つかりませんでした。\nGeminiでの追加確認に失敗したため、今回は機能追加要望DBへ自動登録していません。"
