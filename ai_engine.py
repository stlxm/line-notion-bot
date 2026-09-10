import ai_feedback
import notion_helper


def generate_response(user_message):
    """
    Notionの必要DBだけを取得し、過去の関連するAI改善例を加えて、
    Geminiを最終回答生成の1回だけ呼び出します。
    """
    notion_context = notion_helper.dynamic_search_and_fetch(user_message)
    feedback_context = ai_feedback.build_feedback_context(user_message)

    feedback_section = ""
    if feedback_context:
        feedback_section = f"\n\n{feedback_context}\n"

    prompt = (
        "あなたはユーザーのNotionデータを管理・参照するパーソナルアシスタントです。"
        "以下のNotion検索結果を主な根拠として、日本語で簡潔かつ正確に答えてください。"
        "情報が不足している場合は推測せず、不足していると伝えてください。"
        "過去のAI改善例がある場合、それはユーザーの好み・期待する回答方法を示す参考例です。"
        "改善例の事実関係を今回の事実として流用せず、回答の構成・観点・粒度・判断方法だけを参考にしてください。"
        f"\n\n【Notion検索結果】\n{notion_context}"
        f"{feedback_section}"
        f"\n【ユーザーからの質問】\n{user_message}"
    )

    try:
        response = notion_helper.call_gemini_with_retry(notion_helper.GEMINI_MODEL, prompt)
        return response.text
    except Exception as e:
        print(f"Gemini APIエラー: {e}")
        return f"AIの応答生成中にエラーが発生しました: {str(e)}"
