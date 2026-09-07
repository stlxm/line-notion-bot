import os
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort
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
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")
NOTION_PAGE_URL = os.environ.get("NOTION_PAGE_URL", "")

# クライアント初期化
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ユーザーごとの対話状態を記録する辞書
user_states = {}


@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


def reply_line(reply_token, text):
    """LINEにメッセージを返信する共通関数"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


def add_url_to_notion(url_string):
    """URLと現在時刻をURL用データベースに追加する"""
    if not NOTION_URL_DATABASE_ID:
        return "URL保存用のデータベースIDが設定されていません。Renderの環境変数 NOTION_URL_DATABASE_ID を設定してください。"

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # 日本時間（JST）の取得
    jst = timezone(timedelta(hours=+9), "JST")
    now_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    payload = {
        "parent": {"database_id": NOTION_URL_DATABASE_ID},
        "properties": {
            "URL": {
                "title": [{"text": {"content": url_string}}]
            },
            "時間": {
                "rich_text": [{"text": {"content": now_str}}]
            }
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return f"後で見るURLに追加しました！\n\nURL: {url_string}\n時間: {now_str}"
        else:
            print(f"URL追加エラー ({res.status_code}): {res.text}")
            return f"URLの保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        print(f"URL追加通信エラー: {e}")
        return f"エラーが発生しました: {str(e)}"


def get_database_title(db_id):
    """データベースのタイトル名を取得する"""
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            title_list = data.get("title", [])
            title_text = "".join([t.get("plain_text", "") for t in title_list])
            if title_text:
                return title_text
    except Exception as e:
        print(f"DBタイトル取得エラー: {e}")
    return f"データベース ({db_id[:6]}...)"


def get_database_properties(db_id):
    """データベースの列名一覧を取得する"""
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            props = data.get("properties", {})
            prop_list = []
            title_prop = None

            for p_name, p_info in props.items():
                p_type = p_info.get("type")
                if p_type == "title":
                    title_prop = (p_name, p_type)
                else:
                    prop_list.append((p_name, p_type))

            if title_prop:
                prop_list.insert(0, title_prop)

            return prop_list
    except Exception as e:
        print(f"プロパティ取得エラー: {e}")
    return []


def create_notion_page(db_id, collected_data, prop_types):
    """手動追加用：収集したデータからNotionへページを追加する"""
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties_payload = {}
    for p_name, val in collected_data.items():
        p_type = prop_types.get(p_name, "rich_text")
        if p_type == "title":
            properties_payload[p_name] = {"title": [{"text": {"content": val}}]}
        elif p_type == "rich_text":
            properties_payload[p_name] = {"rich_text": [{"text": {"content": val}}]}
        elif p_type == "number":
            try:
                num_val = float(val) if "." in val else int(val)
                properties_payload[p_name] = {"number": num_val}
            except ValueError:
                properties_payload[p_name] = {"number": None}
        elif p_type == "select":
            properties_payload[p_name] = {"select": {"name": val}}
        elif p_type == "multi_select":
            items = [item.strip() for item in val.split(",")]
            properties_payload[p_name] = {"multi_select": [{"name": item} for item in items]}
        elif p_type == "url":
            properties_payload[p_name] = {"url": val}
        else:
            properties_payload[p_name] = {"rich_text": [{"text": {"content": val}}]}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties_payload
    }

    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200


def fetch_notion_context():
    """検索用：全データベースのデータを取得"""
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
                        val_str = "".join([t.get("plain_text", "") for t in prop_val.get("title", [])])
                    elif p_type == "rich_text":
                        val_str = "".join([t.get("plain_text", "") for t in prop_val.get("rich_text", [])])
                    elif p_type == "number":
                        num = prop_val.get("number")
                        val_str = str(num) if num is not None else ""
                    elif p_type == "select":
                        select_obj = prop_val.get("select")
                        if select_obj:
                            val_str = select_obj.get("name", "")
                    elif p_type == "multi_select":
                        val_str = ", ".join([m.get("name", "") for m in prop_val.get("multi_select", [])])
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
    """Geminiで検索回答"""
    system_instruction = (
        "あなたはユーザーのプライベート生活情報を把握している優秀なパーソナルアシスタントです。\n"
        "提供されたNotionデータベースの最新情報を参考に、ユーザーからの質問に正確かつ丁寧に回答してください。\n\n"
        "【回答ルール】\n"
        "1. 提供されたNotionデータの中に該当する情報がある場合は、分かりやすく要約して回答してください。\n"
        "2. 計算を求められた場合は数値をもとに正確に計算してください。\n"
        "3. 情報がない場合はNotionに該当する情報が登録されていませんと伝えてください。"
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


def start_db_selection(user_id, reply_token):
    """データベース選択の初期状態を開始する"""
    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    if not db_id_list:
        reply_line(reply_token, "連携されているNotionデータベースがありません。")
        return

    db_options = []
    for idx, db_id in enumerate(db_id_list, 1):
        db_title = get_database_title(db_id)
        db_options.append(f"{idx}. {db_title}")

    user_states[user_id] = {
        "step": "SELECT_DB",
        "db_list": db_id_list
    }

    msg = "追加先のデータベースの番号を送信してください。\n（途中でやめる場合は キャンセル と送信してください）\n\n" + "\n".join(db_options)
    reply_line(reply_token, msg)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # キャンセル処理
    if user_message == "キャンセル":
        if user_id in user_states:
            del user_states[user_id]
            reply_line(event.reply_token, "データの追加処理を中断しました。")
        else:
            reply_line(event.reply_token, "現在進行中の追加処理はありません。")
        return

    # 対話モード中の処理
    if user_id in user_states:
        state_data = user_states[user_id]
        step = state_data["step"]

        if step == "SELECT_DB":
            if user_message.isdigit():
                idx = int(user_message) - 1
                db_list = state_data["db_list"]
                if 0 <= idx < len(db_list):
                    selected_db_id = db_list[idx]
                    props = get_database_properties(selected_db_id)
                    if not props:
                        reply_line(event.reply_token, "プロパティの取得に失敗しました。最初からやり直してください。")
                        del user_states[user_id]
                        return

                    state_data["selected_db_id"] = selected_db_id
                    state_data["properties"] = props
                    state_data["current_prop_index"] = 0
                    state_data["collected_data"] = {}
                    state_data["step"] = "INPUT_PROPERTY"

                    first_prop_name = props[0][0]
                    reply_line(event.reply_token, f"{first_prop_name} は何ですか？")
                    return
            reply_line(event.reply_token, "有効な番号を送信してください。（中断する場合は キャンセル と送信してください）")
            return

        elif step == "INPUT_PROPERTY":
            props = state_data["properties"]
            curr_idx = state_data["current_prop_index"]
            prop_name, _ = props[curr_idx]

            state_data["collected_data"][prop_name] = user_message

            next_idx = curr_idx + 1
            if next_idx < len(props):
                state_data["current_prop_index"] = next_idx
                next_prop_name = props[next_idx][0]
                reply_line(event.reply_token, f"{next_prop_name} は何ですか？")
                return
            else:
                state_data["step"] = "CONFIRM"
                confirm_lines = ["【入力内容の確認】"]
                for p_name, val in state_data["collected_data"].items():
                    confirm_lines.append(f"{p_name}: {val}")
                confirm_lines.append("\nこの内容でデータベースに追加してよろしいですか？\n( はい / いいえ )")
                reply_line(event.reply_token, "\n".join(confirm_lines))
                return

        elif step == "CONFIRM":
            if user_message == "はい":
                db_id = state_data["selected_db_id"]
                collected_data = state_data["collected_data"]
                prop_types = {p[0]: p[1] for p in state_data["properties"]}

                success = create_notion_page(db_id, collected_data, prop_types)
                if success:
                    reply_text = "データベースに正常に追加しました！"
                else:
                    reply_text = "登録に失敗しました。Notionの書き込み権限等を確認してください。"
                del user_states[user_id]
                reply_line(event.reply_token, reply_text)
                return
            elif user_message == "いいえ":
                reply_line(event.reply_token, "登録をキャンセルし、最初からやり直します。")
                start_db_selection(user_id, event.reply_token)
                return
            else:
                reply_line(event.reply_token, "はい または いいえ で送信してください。（中断する場合は キャンセル と送信してください）")
                return

    # コマンド: URL送信判定（http:// または https:// で始まる場合）
    if user_message.startswith("http://") or user_message.startswith("https://"):
        res_text = add_url_to_notion(user_message)
        reply_line(event.reply_token, res_text)
        return

    # コマンド: Notion リンク表示
    if user_message in ["リンク", "Notion", "notion", "Notionリンク", "notionリンク"]:
        if NOTION_PAGE_URL:
            reply_line(event.reply_token, f"Notionのページはこちらです:\n{NOTION_PAGE_URL}")
        else:
            reply_line(event.reply_token, "NotionのURLが設定されていません。Renderの環境変数 NOTION_PAGE_URL を設定してください。")
        return

    # コマンド: データ追加
    if user_message == "データ追加":
        start_db_selection(user_id, event.reply_token)
        return

    # コマンド: ヘルプ
    if user_message in ["ヘルプ", "help", "Help", "使い方"]:
        help_text = (
            "【Notionアシスタントの使い方】\n\n"
            "◆ データ検索\n"
            "知りたい情報をそのまま質問してください。\n"
            "例: ドライバーどこ？ / サブスクの合計金額は？\n\n"
            "◆ 後で見るURL追加\n"
            "URL（http...）をそのまま送信すると後で見るリストへ日時付きで追加されます。\n\n"
            "◆ データ追加\n"
            "データ追加 と送信すると対話形式でNotionへデータを保存できます。\n\n"
            "◆ Notionリンク\n"
            "リンク または Notion と送信するとNotionのページURLを表示します。\n\n"
            "◆ キャンセル\n"
            "入力途中で キャンセル と送るといつでも処理を中断できます。"
        )
        reply_line(event.reply_token, help_text)
        return

    # 通常検索（Gemini回答）
    try:
        notion_context = fetch_notion_context()
        ai_response = generate_gemini_response(user_message, notion_context)
    except Exception as e:
        ai_response = f"エラーが発生しました: {str(e)}"

    reply_line(event.reply_token, ai_response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
