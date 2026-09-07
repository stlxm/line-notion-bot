import os
from flask import Flask, request, abort
import requests
from google import genai
from google.genai import types
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# 環境変数の取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")

# クライアント初期化
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

def fetch_notion_context():
    """複数のNotionデータベースから全レコードを取得してテキスト化する"""
    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    formatted_data = []
    
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    for db_id in db_id_list:
        try:
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            res = requests.post(url, headers=headers)
            
            if res.status_code != 200:
                print(f"Notion API エラー ({res.status_code}): {res.text}")
                continue
                
            data = res.json()
            pages = data.get("results", [])
            
            for page in pages:
                props = page.get("properties", {})
                item_info = []
                
                for prop_name, prop_val in props.items():
                    p_type = prop_val.get("type")
                    val_str = ""
                    
                    if p_type == "title":
                        title_list = prop_val.get("title", [])
                        val_str = "".join([t.get("plain_text", "") for t in title_list])
                    elif p_type == "rich_text":
                        text_list = prop_val.get("rich_text", [])
                        val_str = "".join([t.get("plain_text", "") for t in text_list])
                    elif p_type == "number":
                        num = prop_val.get("number")
                        val_str = str(num) if num is not None else ""
                    elif p_type == "select":
                        select_obj = prop_val.get("select")
                        if select_obj:
                            val_str = select_obj.get("name", "")
                    elif p_type == "multi_select":
                        ms_list = prop_val.get("multi_select", [])
                        val_str = ", ".join([m.get("name", "") for m in ms_list])
                    elif p_type == "url":
                        val_str = prop_val.get("url", "")
                    
                    if val_str:
                        item_info.append(f"{prop_name}: {val_str}")
                
                if item_info:
                    formatted_data.append("- " + " | ".join(item_info))
        except Exception as e:
            print(f"データベース取得エラー (ID: {db_id}): {e}")
            
    return "\n".join(formatted_data)

def generate_gemini_response(user_query, notion_context):
    """Gemini 3.6 Flashで回答を生成する"""
    system_instruction = (
        "あなたはユーザーのプライベート生活情報を把握している優秀なパーソナルアシスタントです。\n"
        "提供されたNotionデータベースの最新情報を参考に、ユーザーからの質問に正確かつ丁寧に回答してください。\n\n"
        "【回答ルール】\n"
        "1. 提供されたNotionデータの中に該当する情報がある場合は、分かりやすく要約して回答してください。\n"
        "2. サブスクの合計金額など計算を求められた場合は、提供されたデータ内の数値をもとに正確に計算してください。\n"
        "3. Notionデータの中に存在しない情報について聞かれた場合は、適当な推測やでまかせを言わず『Notionに該当する情報が登録されていません』と明確に伝えてください。\n"
        "4. LINEのチャット画面で読みやすいように、適宜箇条書きや改行を活用してください。"
    )
    
    prompt = f"【Notionの最新データ】\n{notion_context}\n\n【ユーザーの質問】\n{user_query}"
    
    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )
    return response.text

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    
    try:
        notion_context = fetch_notion_context()
        ai_response = generate_gemini_response(user_message, notion_context)
    except Exception as e:
        ai_response = f"エラーが発生しました: {str(e)}"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ai_response)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
