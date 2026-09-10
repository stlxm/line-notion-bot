import os
import re
import time
import requests
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_AI_FEEDBACK_DATABASE_ID = os.environ.get("NOTION_AI_FEEDBACK_DATABASE_ID", "")
JST = timezone(timedelta(hours=9), "JST")

# 直前のAI質問・回答は、ユーザーが「AI改善」を実行するまで短期保持します。
# Render再起動時には消えるため、永続化されるのは改善内容を確定した後です。
_recent_interactions = {}

MAX_FEEDBACK_ROWS = 100
MAX_RELEVANT_FEEDBACK = 3


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def remember_ai_interaction(user_id, question, answer):
    if not user_id or not question:
        return
    _recent_interactions[user_id] = {
        "question": question.strip(),
        "answer": (answer or "").strip(),
        "saved_at": time.time(),
    }


def get_last_ai_interaction(user_id):
    return _recent_interactions.get(user_id)


def clear_last_ai_interaction(user_id):
    _recent_interactions.pop(user_id, None)


def save_feedback(question, ai_answer, expected_answer):
    """AI改善ログDBへ質問・実回答・期待回答を保存します。"""
    if not NOTION_AI_FEEDBACK_DATABASE_ID:
        return False, "NOTION_AI_FEEDBACK_DATABASE_ID が設定されていません。"

    payload = {
        "parent": {"database_id": NOTION_AI_FEEDBACK_DATABASE_ID},
        "properties": {
            "質問": {"title": [{"text": {"content": question[:2000]}}]},
            "AI回答": {"rich_text": [{"text": {"content": ai_answer[:2000]}}]},
            "期待する回答": {"rich_text": [{"text": {"content": expected_answer[:2000]}}]},
            "登録日時": {"date": {"start": datetime.now(JST).isoformat()}},
        },
    }

    try:
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            return True, "AI改善ログに保存しました。次回以降の似た質問で参考にします。"
        print(f"AI改善ログ保存エラー ({response.status_code}): {response.text}")
        return False, "AI改善ログの保存に失敗しました。Notion DBのプロパティ名と型を確認してください。"
    except Exception as e:
        print(f"AI改善ログ保存エラー: {e}")
        return False, f"AI改善ログの保存中にエラーが発生しました: {e}"


def _plain_text(prop):
    p_type = prop.get("type")
    if p_type == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if p_type == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    if p_type == "date":
        value = prop.get("date") or {}
        return value.get("start", "")
    return ""


def _query_feedback_rows():
    if not NOTION_AI_FEEDBACK_DATABASE_ID:
        return []

    url = f"https://api.notion.com/v1/databases/{NOTION_AI_FEEDBACK_DATABASE_ID}/query"
    payload = {
        "page_size": MAX_FEEDBACK_ROWS,
        "sorts": [{"property": "登録日時", "direction": "descending"}],
    }
    try:
        response = requests.post(url, headers=_headers(), json=payload, timeout=10)
        if response.status_code != 200:
            print(f"AI改善ログ取得エラー ({response.status_code}): {response.text}")
            return []
        rows = []
        for page in response.json().get("results", []):
            props = page.get("properties", {})
            rows.append({
                "question": _plain_text(props.get("質問", {})),
                "answer": _plain_text(props.get("AI回答", {})),
                "expected": _plain_text(props.get("期待する回答", {})),
                "date": _plain_text(props.get("登録日時", {})),
            })
        return rows
    except Exception as e:
        print(f"AI改善ログ取得エラー: {e}")
        return []


def _normalize(text):
    return re.sub(r"[\s　、。,.!?！？:：;；\-_/()（）\[\]【】]", "", (text or "").lower())


def _char_ngrams(text, n=2):
    text = _normalize(text)
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _similarity(question, past_question):
    a = _normalize(question)
    b = _normalize(past_question)
    if not a or not b:
        return 0.0

    seq = SequenceMatcher(None, a, b).ratio()
    a_grams = _char_ngrams(a)
    b_grams = _char_ngrams(b)
    union = a_grams | b_grams
    jaccard = len(a_grams & b_grams) / len(union) if union else 0.0

    # 完全包含は強く評価。日本語でも追加の形態素解析ライブラリなしで動くようにする。
    contains_bonus = 0.25 if (a in b or b in a) else 0.0
    return min(1.0, seq * 0.55 + jaccard * 0.45 + contains_bonus)


def get_relevant_feedback(question, limit=MAX_RELEVANT_FEEDBACK):
    """Geminiを使わず、過去質問との文字列類似度で改善例を最大3件選びます。"""
    scored = []
    for row in _query_feedback_rows():
        if not row.get("question") or not row.get("expected"):
            continue
        score = _similarity(question, row["question"])
        if score >= 0.18:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limit]]


def build_feedback_context(question):
    examples = get_relevant_feedback(question)
    if not examples:
        return ""

    lines = [
        "【過去のAI改善例】",
        "以下は過去にユーザーが『こう答えてほしかった』と修正した例です。",
        "今回の質問と関連する場合は、内容・粒度・判断基準を参考にしてください。",
        "ただし過去例を事実として流用せず、今回取得したNotionデータを優先してください。",
    ]
    for index, item in enumerate(examples, start=1):
        lines.extend([
            f"\n例{index}",
            f"過去の質問: {item['question']}",
            f"当時のAI回答: {item['answer']}",
            f"ユーザーが期待した回答: {item['expected']}",
        ])
    return "\n".join(lines)
