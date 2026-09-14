import os
import re
import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_AI_FEEDBACK_DATABASE_ID = os.environ.get("NOTION_AI_FEEDBACK_DATABASE_ID", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
JST = timezone(timedelta(hours=9), "JST")

_recent_interactions = {}
MAX_FEEDBACK_ROWS = 100
MAX_RELEVANT_FEEDBACK = 3


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _push_ai_rating_buttons(user_id):
    """AI回答の直後に、LINE上で押せる 👍 / 👎 ボタンをPushする。"""
    if not user_id or not LINE_CHANNEL_ACCESS_TOKEN:
        return
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "flex",
                "altText": "AI回答を評価",
                "contents": {
                    "type": "bubble",
                    "size": "kilo",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": "この回答は役に立ちましたか？",
                                "weight": "bold",
                                "size": "sm",
                                "wrap": True,
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "button",
                                        "style": "primary",
                                        "height": "sm",
                                        "action": {
                                            "type": "message",
                                            "label": "👍 良い",
                                            "text": "AI評価 👍",
                                        },
                                    },
                                    {
                                        "type": "button",
                                        "style": "secondary",
                                        "height": "sm",
                                        "action": {
                                            "type": "message",
                                            "label": "👎 改善したい",
                                            "text": "AI評価 👎",
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                },
            }
        ],
    }
    try:
        response = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        if response.status_code >= 300:
            print(f"AI rating button push error ({response.status_code}): {response.text[:500]}")
    except Exception as e:
        print(f"AI rating button push exception: {e}")


def _schedule_ai_rating_buttons(user_id):
    # app.py がAI回答本文をPushした直後に表示されるよう、少しだけ遅らせる。
    timer = threading.Timer(1.5, _push_ai_rating_buttons, args=(user_id,))
    timer.daemon = True
    timer.start()


def remember_ai_interaction(user_id, question, answer):
    if not user_id or not question:
        return
    _recent_interactions[user_id] = {
        "question": question.strip(),
        "answer": (answer or "").strip(),
        "saved_at": time.time(),
    }
    _schedule_ai_rating_buttons(user_id)


def get_last_ai_interaction(user_id):
    return _recent_interactions.get(user_id)


def get_latest_ai_interaction():
    if not _recent_interactions:
        return None
    return max(_recent_interactions.values(), key=lambda x: x.get("saved_at", 0))


def clear_last_ai_interaction(user_id):
    _recent_interactions.pop(user_id, None)


def _extract_answer_metadata(answer):
    text = str(answer or "")
    refs = ""
    reason = ""
    ref_match = re.search(r"【参照DB】\s*\n?(.*?)(?=\n【|$)", text, flags=re.DOTALL)
    if ref_match:
        refs = re.sub(r"^[・\-]\s*", "", ref_match.group(1).strip(), flags=re.MULTILINE)
        refs = " / ".join(x.strip(" ・-") for x in refs.splitlines() if x.strip())
    reason_match = re.search(r"【根拠】\s*\n?(.*?)(?=\n【|$)", text, flags=re.DOTALL)
    if reason_match:
        reason = " ".join(x.strip() for x in reason_match.group(1).splitlines() if x.strip())
    return refs[:1900], reason[:1900]


def _create_feedback_row(question, ai_answer, expected_answer="", rating="改善"):
    if not NOTION_AI_FEEDBACK_DATABASE_ID:
        return False, "NOTION_AI_FEEDBACK_DATABASE_ID が設定されていません。"
    refs, reason = _extract_answer_metadata(ai_answer)
    props = {
        "質問": {"title": [{"text": {"content": question[:2000]}}]},
        "AI回答": {"rich_text": [{"text": {"content": ai_answer[:2000]}}]},
        "期待する回答": {"rich_text": [{"text": {"content": expected_answer[:2000]}}]},
        "登録日時": {"date": {"start": datetime.now(JST).isoformat()}},
        "評価": {"select": {"name": rating}},
        "参照DB": {"rich_text": [{"text": {"content": refs}}]},
        "根拠": {"rich_text": [{"text": {"content": reason}}]},
    }
    try:
        response = requests.post(
            "https://api.notion.com/v1/pages", headers=_headers(),
            json={"parent": {"database_id": NOTION_AI_FEEDBACK_DATABASE_ID}, "properties": props}, timeout=10,
        )
        if response.status_code == 200:
            return True, "AI改善ログに保存しました。"
        print(f"AI feedback save error ({response.status_code}): {response.text[:700]}")
        return False, "AI改善ログの保存に失敗しました。"
    except Exception as e:
        print(f"AI feedback save error: {e}")
        return False, f"AI改善ログの保存中にエラーが発生しました: {e}"


def save_feedback(question, ai_answer, expected_answer):
    success, message = _create_feedback_row(question, ai_answer, expected_answer, "改善")
    if success:
        return True, "AI改善ログに保存しました。次回以降の似た質問で回答方法とDB選択の参考にします。"
    return False, message


def save_rating(rating):
    normalized = "👍" if rating in {"👍", "good", "up", "1"} else "👎" if rating in {"👎", "bad", "down", "0"} else ""
    if not normalized:
        return False, "評価は 👍 または 👎 を指定してください。"
    item = get_latest_ai_interaction()
    if not item:
        return False, "評価できる直前のAI回答がありません。先に「AI 質問内容」を使ってください。"
    success, _ = _create_feedback_row(item["question"], item["answer"], "", normalized)
    if not success:
        return False, "AI評価の保存に失敗しました。"
    if normalized == "👍":
        return True, "👍 評価を保存しました。今後のDB選択・回答改善の参考にします。"
    return True, "👎 評価を保存しました。具体的に直したい場合は続けて「AI改善」と送ってください。"


def _plain_text(prop):
    p_type = prop.get("type")
    if p_type == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if p_type == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    if p_type == "date":
        value = prop.get("date") or {}
        return value.get("start", "")
    if p_type == "select":
        value = prop.get("select") or {}
        return value.get("name", "")
    return ""


def _query_feedback_rows():
    if not NOTION_AI_FEEDBACK_DATABASE_ID:
        return []
    url = f"https://api.notion.com/v1/databases/{NOTION_AI_FEEDBACK_DATABASE_ID}/query"
    payload = {"page_size": MAX_FEEDBACK_ROWS, "sorts": [{"property": "登録日時", "direction": "descending"}]}
    try:
        response = requests.post(url, headers=_headers(), json=payload, timeout=10)
        if response.status_code != 200:
            print(f"AI改善ログ取得エラー ({response.status_code}): {response.text[:700]}")
            return []
        rows = []
        for page in response.json().get("results", []):
            props = page.get("properties", {})
            rows.append({
                "question": _plain_text(props.get("質問", {})),
                "answer": _plain_text(props.get("AI回答", {})),
                "expected": _plain_text(props.get("期待する回答", {})),
                "date": _plain_text(props.get("登録日時", {})),
                "rating": _plain_text(props.get("評価", {})),
                "sources": _plain_text(props.get("参照DB", {})),
                "reason": _plain_text(props.get("根拠", {})),
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
    contains_bonus = 0.25 if (a in b or b in a) else 0.0
    return min(1.0, seq * 0.55 + jaccard * 0.45 + contains_bonus)


def get_relevant_feedback(question, limit=MAX_RELEVANT_FEEDBACK):
    scored = []
    for row in _query_feedback_rows():
        if not row.get("question"):
            continue
        score = _similarity(question, row["question"])
        if score >= 0.18:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limit]]


def build_feedback_context(question):
    examples = [x for x in get_relevant_feedback(question) if x.get("expected")]
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


def get_router_hint(question):
    """#72: 過去の類似AI評価/改善ログから、以前参照したDB名をルーターの補助語として返す。"""
    hints = []
    for row in get_relevant_feedback(question, limit=5):
        if row.get("rating") not in {"👎", "改善"}:
            continue
        sources = row.get("sources", "")
        for name in re.split(r"\s*/\s*|[,、]", sources):
            name = name.strip()
            if name and name not in hints:
                hints.append(name)
    return hints[:2]
