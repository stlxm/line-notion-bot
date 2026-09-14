import re

import ai_feedback
import notion_helper

LITE_MODEL = "gemini-3.5-flash-lite"
FLASH_MODEL = "gemini-3.6-flash"
_selected_model = LITE_MODEL


def get_selected_model():
    return _selected_model


def get_selected_model_label():
    return "Lite" if get_selected_model() == LITE_MODEL else "Flash"


def set_selected_model(mode):
    global _selected_model
    normalized = str(mode or "").strip().lower()
    if normalized in {"lite", "l", "軽量", "ライト"}:
        _selected_model = LITE_MODEL
        return True, "Lite"
    if normalized in {"flash", "f", "通常", "高性能"}:
        _selected_model = FLASH_MODEL
        return True, "Flash"
    return False, get_selected_model_label()


def sanitize_for_line(text):
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"```(?:[a-zA-Z0-9_+-]+)?\n?", "", cleaned)
    cleaned = cleaned.replace("```", "")
    cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("~~", "").replace("`", "")
    cleaned = re.sub(r"(?m)^\s*>\s?", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*+]\s+", "・", cleaned)
    cleaned = re.sub(r"(?m)^\s*(\d+)\.\s+", r"\1. ", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_referenced_db_titles(notion_context):
    titles = []
    for match in re.finditer(r"【DB:\s*(.+?)】", notion_context or ""):
        title = match.group(1).strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def _build_rationale(question, notion_context, source_titles):
    date_scope = ""
    for word in ["今日", "昨日", "今週", "先週", "今月", "先月", "今年"]:
        if word in question:
            date_scope = f"質問の「{word}」に合わせて期間を絞ったデータ"
            break
    parts = []
    if source_titles:
        parts.append("参照DBから取得した実データ")
    if date_scope:
        parts.append(date_scope)
    if "該当するNotionデータが見つかりませんでした" in (notion_context or ""):
        parts.append("該当データなしという検索結果")
    return "、".join(parts) or "Notion検索結果とユーザーの質問"


def generate_response(user_message):
    command = str(user_message or "").strip()
    if command.lower() in {"lite", "l"} or command in {"軽量", "ライト"}:
        _, label = set_selected_model("lite")
        return f"AIモデルを {label} に切り替えました。\n使用モデル: {get_selected_model()}\n次から「AI 質問内容」で使えます。"
    if command.lower() in {"flash", "f"} or command in {"通常", "高性能"}:
        _, label = set_selected_model("flash")
        return f"AIモデルを {label} に切り替えました。\n使用モデル: {get_selected_model()}\n次から「AI 質問内容」で使えます。"
    if command.lower() in {"model", "モデル"}:
        return f"現在のAIモデル: {get_selected_model_label()}\n{get_selected_model()}\n切替: AI Lite / AI Flash"

    router_hints = ai_feedback.get_router_hint(user_message)
    routing_query = user_message
    if router_hints:
        routing_query += "\n参照候補DB: " + " / ".join(router_hints)

    notion_context = notion_helper.dynamic_search_and_fetch(routing_query)
    feedback_context = ai_feedback.build_feedback_context(user_message)
    source_titles = _extract_referenced_db_titles(notion_context)
    rationale = _build_rationale(user_message, notion_context, source_titles)

    feedback_section = ""
    if feedback_context:
        feedback_section = f"\n\n{feedback_context}\n"

    prompt = (
        "あなたはユーザーのNotionデータを管理・参照するパーソナルアシスタントです。"
        "以下のNotion検索結果を主な根拠として、日本語で簡潔かつ正確に答えてください。"
        "情報が不足している場合は推測せず、不足していると伝えてください。"
        "過去のAI改善例がある場合、それはユーザーの好み・期待する回答方法を示す参考例です。"
        "改善例の事実関係を今回の事実として流用せず、回答の構成・観点・粒度・判断方法だけを参考にしてください。"
        "LINEにそのまま表示するため、Markdown記法は一切使わないでください。"
        "回答本文だけを生成し、参照DBや根拠の見出しは付けないでください。これらはシステム側で付与します。"
        f"\n\n【Notion検索結果】\n{notion_context}"
        f"{feedback_section}"
        f"\n【ユーザーからの質問】\n{user_message}"
    )

    try:
        response = notion_helper.call_gemini_with_retry(get_selected_model(), prompt)
        answer = sanitize_for_line(response.text)
        refs = "\n".join(f"・{title}" for title in source_titles) if source_titles else "・該当DBを特定できませんでした"
        return (
            f"{answer}\n\n"
            f"【参照DB】\n{refs}\n\n"
            f"【根拠】\n{rationale}\n\n"
            "評価する場合: AI評価 👍 / AI評価 👎"
        )
    except Exception as e:
        print(f"Gemini APIエラー ({get_selected_model()}): {e}")
        return f"AIの応答生成中にエラーが発生しました: {str(e)}"
