import os
import requests

import ai_feedback

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")

DB_CONFIG = [
    ("家計簿", "NOTION_KAKEIBO_DATABASE_ID", ["金額", "日付", "ジャンル"]),
    ("月別管理", "NOTION_MONTHLY_DATABASE_ID", ["年月", "全体予算"]),
    ("固定費", "NOTION_FIXED_DATABASE_ID", []),
    ("メモ", "NOTION_MEMO_DATABASE_ID", ["メモ", "日付", "期限", "分類", "完了"]),
    ("URL", "NOTION_URL_DATABASE_ID", ["ページタイトル", "カテゴリ", "ドメイン", "保存日時"]),
    ("AI改善ログ", "NOTION_AI_FEEDBACK_DATABASE_ID", ["質問", "AI回答", "期待する回答", "評価", "参照DB", "根拠"]),
    ("カード未処理", "NOTION_CARD_PENDING_DATABASE_ID", []),
    ("カード学習ルール", "NOTION_CARD_RULES_DATABASE_ID", []),
    ("貯金目標", "NOTION_SAVINGS_GOALS_DATABASE_ID", []),
    ("貸し借り", "NOTION_LOAN_DATABASE_ID", ["相手", "種類", "金額", "状態"]),
    ("機能追加要望", "NOTION_FEATURE_REQUEST_DATABASE_ID", ["要望", "状態"]),
    ("生活カレンダー", "NOTION_FLYER_DATABASE_ID", ["予定名", "日付", "種類", "店舗"]),
]


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _check_database(label, env_name, required):
    database_id = os.environ.get(env_name, "").strip()
    if not database_id:
        return {"label": label, "status": "missing_env", "env": env_name, "missing": required}
    if not NOTION_API_KEY:
        return {"label": label, "status": "missing_api", "env": env_name, "missing": required}
    try:
        res = requests.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers=_headers(), timeout=10,
        )
    except Exception as e:
        return {"label": label, "status": "network", "env": env_name, "error": str(e), "missing": required}
    if res.status_code != 200:
        return {
            "label": label,
            "status": f"http_{res.status_code}",
            "env": env_name,
            "error": (res.json().get("message") if res.headers.get("content-type", "").startswith("application/json") else res.text[:200]),
            "missing": required,
        }
    props = res.json().get("properties", {})
    missing = [name for name in required if name not in props]
    return {"label": label, "status": "ok" if not missing else "schema", "env": env_name, "missing": missing}


def build_health_report():
    results = [_check_database(*config) for config in DB_CONFIG]
    ok = [x for x in results if x["status"] == "ok"]
    warnings = [x for x in results if x["status"] != "ok"]
    lines = ["🩺 Notion DBヘルスチェック", f"正常: {len(ok)} / {len(results)}", ""]
    for item in results:
        status = item["status"]
        if status == "ok":
            lines.append(f"✅ {item['label']}")
        elif status == "missing_env":
            lines.append(f"⚠️ {item['label']}: {item['env']} 未設定")
        elif status == "schema":
            lines.append(f"⚠️ {item['label']}: 必須列不足 → {', '.join(item['missing'])}")
        else:
            lines.append(f"❌ {item['label']}: {status} / {item.get('error', '')}")
    if not warnings:
        lines += ["", "✅ 現在確認対象のDBはすべて正常です。"]
    else:
        lines += ["", f"要確認: {len(warnings)}件"]
    return "\n".join(lines)[:4800]


def handle_text_command(text):
    message = str(text or "").strip().replace("　", " ")
    lowered = message.lower()

    if lowered in {"ai評価 👍", "ai 評価 👍", "ai good", "ai評価 good"}:
        success, result = ai_feedback.save_rating("👍")
        return ("✅ " if success else "⚠️ ") + result
    if lowered in {"ai評価 👎", "ai 評価 👎", "ai bad", "ai評価 bad"}:
        success, result = ai_feedback.save_rating("👎")
        return ("✅ " if success else "⚠️ ") + result
    if message in ["DBヘルス", "DBヘルスチェック", "Notionヘルス", "Notion DBヘルス", "Notion DBヘルスチェック"]:
        return build_health_report()
    if lowered in {"phase5", "フェーズ5"}:
        return (
            "【Phase 5】\n"
            "・AI回答末尾に参照DBと根拠を表示\n"
            "・AI評価 👍 / AI評価 👎\n"
            "・👎後に AI改善 で具体的な改善を保存\n"
            "・過去改善ログを次回のDBルーターへ反映\n"
            "・DBヘルスチェック でNotion設定を確認"
        )
    return None
