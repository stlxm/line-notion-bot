import os
import json
import requests
from urllib.parse import parse_qsl
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort
from google import genai
from google.genai import types
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

app = Flask(__name__)

# 環境変数の取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")
NOTION_URL_DATABASE_ID = os.environ.get("NOTION_URL_DATABASE_ID", "")
NOTION_PAGE_URL = os.environ.get("NOTION_PAGE_URL", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")

# クライアント初期化
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

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
    """LINEにテキストメッセージを返信する"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


def get_notion_select_options(prop_name):
    """Notionの家計簿DBから指定した列（Select）の選択肢一覧を動的取得する"""
    if not NOTION_KAKEIBO_DATABASE_ID:
        return []

    url = f"https://api.notion.com/v1/databases/{NOTION_KAKEIBO_DATABASE_ID}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            props = data.get("properties", {})
            target_prop = props.get(prop_name, {})
            if target_prop.get("type") == "select":
                options = target_prop.get("select", {}).get("options", [])
                return [opt.get("name") for opt in options if opt.get("name")]
    except Exception as e:
        print(f"Notion選択肢取得エラー ({prop_name}): {e}")
    return []


def create_buttons_flex_message(title, options, callback_action):
    """選択肢のリストからLINEのボタンメッセージを生成する"""
    buttons = []
    # 2列並びのレイアウトに整形
    for i in range(0, len(options), 2):
        row_buttons = []
        for opt in options[i:i+2]:
            row_buttons.append({
                "type": "button",
                "style": "primary" if i == 0 else "secondary",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": opt[:20],
                    "data": f"action={callback_action}&val={opt}"
                }
            })
        buttons.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row_buttons
        })

    flex_json = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "md", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "lg"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
        }
    }
    return FlexMessage(alt_text=title, contents=FlexContainer.from_json(json.dumps(flex_json)))


def send_kakeibo_category_select(reply_token, card_name, store_name, amount, date_str):
    """GAS通知受領時：Notionのジャンル選択肢を表示する"""
    categories = get_notion_select_options("ジャンル")
    if not categories:
        categories = ["食費", "日用品", "交通費", "娯楽", "固定費", "未分類"]

    buttons = []
    for i in range(0, len(categories), 2):
        row_buttons = []
        for cat in categories[i:i+2]:
            row_buttons.append({
                "type": "button",
                "style": "primary" if i == 0 else "secondary",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": cat[:20],
                    "data": f"action=kakeibo_save&card={card_name}&store={store_name}&amount={amount}&date={date_str}&cat={cat}"
                }
            })
        buttons.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row_buttons
        })

    flex_json = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "💳 カード利用検知", "weight": "bold", "color": "#1DB446", "size": "sm"},
                {"type": "text", "text": f"¥{int(float(amount)):,}", "weight": "bold", "size": "xxl", "margin": "md"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                        {"type": "text", "text": "利用先", "color": "#aaaaaa", "size": "sm", "flex": 2},
                        {"type": "text", "text": store_name, "weight": "bold", "color": "#666666", "size": "sm", "flex": 5}
                    ]
                },
                {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                        {"type": "text", "text": "カード", "color": "#aaaaaa", "size": "sm", "flex": 2},
                        {"type": "text", "text": card_name, "color": "#666666", "size": "sm", "flex": 5}
                    ],
                    "margin": "xs"
                },
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "ジャンルを選択してください", "size": "xs", "color": "#888888", "margin": "lg", "align": "center"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
        }
    }

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(alt_text=f"カード利用: {store_name} ¥{amount}", contents=FlexContainer.from_json(json.dumps(flex_json)))]
            )
        )


def save_kakeibo_to_notion(card_name, store_name, amount, date_str, category):
    """Notionの家計簿データベースに保存する"""
    if not NOTION_KAKEIBO_DATABASE_ID:
        return "家計簿DB IDが設定されていません。Renderの環境変数 NOTION_KAKEIBO_DATABASE_ID を設定してください。"

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": NOTION_KAKEIBO_DATABASE_ID},
        "properties": {
            "内容・店名": {"title": [{"text": {"content": store_name}}]},
            "金額": {"number": float(amount)},
            "日付": {"date": {"start": date_str}},
            "ジャンル": {"select": {"name": category}},
            "カード・支払方法": {"select": {"name": card_name}}
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return f"家計簿に記録しました！\n\n【店名】{store_name}\n【金額】¥{int(float(amount)):,}\n【ジャンル】{category}\n【支払方法】{card_name}\n【日付】{date_str}"
        else:
            print(f"Notion家計簿保存エラー ({res.status_code}): {res.text}")
            return f"家計簿の保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        print(f"家計簿保存通信エラー: {e}")
        return f"エラーが発生しました: {str(e)}"


def start_manual_kakeibo(user_id, reply_token, text):
    """手動入力の開始（金額と店名の受領 -> ジャンル選択の提示）"""
    parts = text.strip().split()
    if len(parts) < 3:
        reply_line(reply_token, "形式が正しくありません。\n【入力例】\n支出 1200 ラーメン")
        return

    try:
        amount = float(parts[1])
    except ValueError:
        reply_line(reply_token, "金額は数値で入力してください。（例: 支出 1200 ラーメン）")
        return

    store_name = parts[2]
    jst = timezone(timedelta(hours=+9), "JST")
    date_str = datetime.now(jst).strftime("%Y-%m-%d")

    user_states[user_id] = {
        "step": "MANUAL_KAKEIBO_GENRE",
        "amount": amount,
        "store": store_name,
        "date": date_str
    }

    categories = get_notion_select_options("ジャンル")
    if not categories:
        categories = ["食費", "日用品", "交通費", "娯楽", "固定費", "未分類"]

    flex_msg = create_buttons_flex_message("ジャンルを選択してください", categories, "manual_cat_select")
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[flex_msg]
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

    jst = timezone(timedelta(hours=+9), "JST")
    now_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    payload = {
        "parent": {"database_id": NOTION_URL_DATABASE_ID},
        "properties": {
            "URL": {"title": [{"text": {"content": url_string}}]},
            "時間": {"rich_text": [{"text": {"content": now_str}}]}
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


@handler.add(PostbackEvent)
def handle_postback(event):
    """LINEのボタンが押された時のポストバック処理"""
    user_id = event.source.user_id
    data = event.postback.data
    params = dict(parse_qsl(data))
    action = params.get("action")

    # GAS通知からの保存
    if action == "kakeibo_save":
        card = params.get("card")
        store = params.get("store")
        amount = params.get("amount")
        date_str = params.get("date")
        category = params.get("cat")

        res_msg = save_kakeibo_to_notion(card, store, amount, date_str, category)
        reply_line(event.reply_token, res_msg)
        return

    # 手動記録: ジャンル選択後の処理
    if action == "manual_cat_select" and user_id in user_states:
        selected_cat = params.get("val")
        user_states[user_id]["category"] = selected_cat
        user_states[user_id]["step"] = "MANUAL_KAKEIBO_CARD"

        cards = get_notion_select_options("カード・支払方法")
        if not cards:
            cards = ["現金", "楽天カード", "三井住友カード", "PayPay", "その他"]

        flex_msg = create_buttons_flex_message("支払方法を選択してください", cards, "manual_card_select")

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[flex_msg]
                )
            )
        return

    # 手動記録: 支払方法選択後の完了処理
    if action == "manual_card_select" and user_id in user_states:
        selected_card = params.get("val")
        state_data = user_states[user_id]

        res_msg = save_kakeibo_to_notion(
            card_name=selected_card,
            store_name=state_data["store"],
            amount=state_data["amount"],
            date_str=state_data["date"],
            category=state_data["category"]
        )
        del user_states[user_id]
        reply_line(event.reply_token, res_msg)
        return


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # コマンド: GASからのカード通知判定（CARD_NOTIFY|カード名|店名|金額|日付）
    if user_message.startswith("CARD_NOTIFY|"):
        parts = user_message.split("|")
        if len(parts) >= 5:
            _, card_name, store_name, amount, date_str = parts[:5]
            send_kakeibo_category_select(event.reply_token, card_name, store_name, amount, date_str)
            return

    # コマンド: 手動で支出入力（例: 支出 1200 ラーメン）
    if user_message.startswith("支出 "):
        start_manual_kakeibo(user_id, event.reply_token, user_message)
        return

    # キャンセル処理
    if user_message == "キャンセル":
        if user_id in user_states:
            del user_states[user_id]
            reply_line(event.reply_token, "処理を中断しました。")
        else:
            reply_line(event.reply_token, "進行中の処理はありません。")
        return

    # 汎用対話モード中の処理
    if user_id in user_states:
        state_data = user_states[user_id]
        step = state_data.get("step")

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

    # コマンド: URL送信判定
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
            "例: 今月の食費合計は？ / 楽天カードの利用履歴教えて\n\n"
            "◆ 手動で支出記録（家計簿）\n"
            "「支出 金額 店名」と送信すると、Notion上の選択肢（ジャンル・支払方法）がボタンで表示されます。\n"
            "例: 支出 1200 ラーメン\n\n"
            "◆ 後で見るURL追加\n"
            "URL（http...）を送ると後で見るリストへ追加されます。\n\n"
            "◆ 汎用データ追加\n"
            "「データ追加」と送信すると対話形式で任意のNotion DBへ追加できます。\n\n"
            "◆ Notionリンク\n"
            "「Notion」と送信するとNotionページURLを表示します。"
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
