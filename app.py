import os
import re
import json
from urllib.parse import parse_qsl
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort


from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

# 外部モジュールのインポート
import kakeibo
import notion_helper

app = Flask(__name__)

# 環境変数
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
NOTION_PAGE_URL = os.environ.get("NOTION_PAGE_URL", "")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_states = {}


@app.route("/", methods=["GET", "HEAD"])
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


@app.route("/api/register-fixed", methods=["POST"])
def api_register_fixed():
    """GAS等からの毎月1日自動実行用API"""
    count, total = kakeibo.register_monthly_fixed_expenses()
    return json.dumps({"status": "success", "count": count, "total": total}), 200


def reply_line(reply_token, messages):
    """LINEにメッセージを送信（文字列またはMessageオブジェクトのリストに対応）"""
    if isinstance(messages, str):
        messages = [TextMessage(text=messages)]
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )


def start_manual_kakeibo(user_id, reply_token, text):
    parts = text.strip().split()
    if len(parts) < 2:
        reply_line(reply_token, "形式が正しくありません。\n【入力例】\n支出 1200 ラーメン")
        return

    try:
        amount = float(parts[1])
    except ValueError:
        reply_line(reply_token, "金額は数値で入力してください。（例: 支出 1200 ラーメン）")
        return

    store_name = parts[2] if len(parts) >= 3 else "未入力"
    jst = timezone(timedelta(hours=+9), "JST")
    date_str = datetime.now(jst).strftime("%Y-%m-%d")

    user_states[user_id] = {
        "step": "MANUAL_KAKEIBO_GENRE",
        "amount": amount,
        "store": store_name,
        "date": date_str
    }

    categories = kakeibo.get_notion_select_options(
        NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=kakeibo.EXCLUDED_GENRES
    )
    if not categories:
        categories = ["食費", "日用品", "交通費", "娯楽"]

    flex_msg = kakeibo.create_button_grid_flex("ジャンルを選択してください", categories, "manual_cat_select", include_cancel=True)
    reply_line(reply_token, [flex_msg])


def start_db_selection(user_id, reply_token):
    db_id_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    if not db_id_list:
        reply_line(reply_token, "連携されているNotionデータベースがありません。")
        return

    db_options = []
    for idx, db_id in enumerate(db_id_list, 1):
        db_title = notion_helper.get_database_title(db_id)
        db_options.append(f"{idx}. {db_title}")

    user_states[user_id] = {
        "step": "SELECT_DB",
        "db_list": db_id_list
    }
    msg = "追加先のデータベースの番号を送信してください。\n（途中でやめる場合は キャンセル と送信してください）\n\n" + "\n".join(db_options)
    reply_line(reply_token, msg)


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    params = dict(parse_qsl(data))
    action = params.get("action")

    if action == "cancel_registration":
        if user_id in user_states:
            del user_states[user_id]
        reply_line(event.reply_token, "登録をキャンセルしました。")
        return

    if action == "kakeibo_save":
        card = params.get("card")
        store = params.get("store")
        amount = params.get("amount")
        date_str = params.get("date")
        category = params.get("cat")

        res_msg = kakeibo.save_kakeibo_to_notion(card, store, amount, date_str, category)
        reply_line(event.reply_token, res_msg)
        return

    if action == "manual_cat_select" and user_id in user_states:
        selected_cat = params.get("val")
        user_states[user_id]["category"] = selected_cat
        user_states[user_id]["step"] = "MANUAL_KAKEIBO_CARD"

        cards = kakeibo.get_notion_select_options(NOTION_KAKEIBO_DATABASE_ID, "カード・支払方法")
        if not cards:
            cards = ["現金", "JCB", "三井住友カード", "PayPay", "楽天カード"]

        flex_msg = kakeibo.create_button_grid_flex("支払方法を選択してください", cards, "manual_card_select", include_cancel=True)
        reply_line(event.reply_token, [flex_msg])
        return

    if action == "manual_card_select" and user_id in user_states:
        selected_card = params.get("val")
        state_data = user_states[user_id]

        res_msg = kakeibo.save_kakeibo_to_notion(
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

    # 1. GASカード通知
    if user_message.startswith("CARD_NOTIFY|"):
        parts = user_message.split("|")
        if len(parts) >= 5:
            _, card_name, store_name, amount, date_str = parts[:5]
            flex_msg = kakeibo.create_card_notify_flex(card_name, store_name, amount, date_str)
            reply_line(event.reply_token, [flex_msg])
            return

    # 2. 予算設定コマンド
    if user_message.startswith("予算"):
        parts = user_message.split()
        jst = timezone(timedelta(hours=+9), "JST")
        current_month = datetime.now(jst).strftime("%Y-%m")
        target_month = current_month
        category = None
        budget_val = None

        if len(parts) == 2 and parts[1].isdigit():
            budget_val = parts[1]
        elif len(parts) == 3:
            if re.match(r"^\d{4}-\d{2}$", parts[1]):
                target_month = parts[1]
                budget_val = parts[2]
            else:
                category = parts[1]
                budget_val = parts[2]
        elif len(parts) >= 4:
            target_month = parts[1]
            category = parts[2]
            budget_val = parts[3]

        if budget_val and budget_val.isdigit():
            success = kakeibo.set_budget_in_notion(target_month, int(budget_val), category)
            target_label = f"{category} の" if category else "全体の"
            if success:
                reply_text = f"予算設定完了\n{target_month} の{target_label}予算を ¥{int(budget_val):,} に設定しました"
            else:
                reply_text = f"予算設定に失敗しました。Notionの月別管理DBを確認してください"
        else:
            reply_text = "【予算設定の使い方】\n・全体予算: 予算 100000\n・ジャンル別: 予算 食費 30000\n・年月指定: 予算 2026-10 食費 35000"

        reply_line(event.reply_token, reply_text)
        return

    # 3. 固定費一括登録
    if user_message in ["固定費", "固定費登録", "固定費 登録"]:
        count, total = kakeibo.register_monthly_fixed_expenses()
        jst = timezone(timedelta(hours=+9), "JST")
        today_month = datetime.now(jst).strftime("%Y-%m")
        if count > 0:
            reply_text = f"今月分（{today_month}）の固定費・サブスクを一括登録しました！\n・件数: {count} 件\n・合計: ¥{total:,}"
        else:
            reply_text = "登録対象の固定費が見つかりませんでした。Notionの固定費マスタを確認してください。"
        reply_line(event.reply_token, reply_text)
        return

    # 4. 固定費一覧
    if user_message in ["固定費一覧", "固定費確認"]:
        items = kakeibo.get_fixed_expenses_from_notion()
        if not items:
            reply_text = "有効な固定費が登録されていません。"
        else:
            lines = ["【現在有効な固定費一覧】"]
            total = 0
            for item in items:
                lines.append(f"・{item['store_name']}: ¥{int(item['amount']):,} ({item['card_name']})")
                total += item["amount"]
            lines.append(f"\n合計: ¥{int(total):,}/月")
            lines.append("\n※ LINEで 固定費 と送信すると、今月の家計簿へ一括登録されます。")
            reply_text = "\n".join(lines)
        reply_line(event.reply_token, reply_text)
        return

    # 5. 手動で支出入力
    if user_message.startswith("支出"):
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

    # 6. 対話型データ追加モード中の処理
    if user_id in user_states:
        state_data = user_states[user_id]
        step = state_data.get("step")

        if step == "SELECT_DB":
            if user_message.isdigit():
                idx = int(user_message) - 1
                db_list = state_data["db_list"]
                if 0 <= idx < len(db_list):
                    selected_db_id = db_list[idx]
                    props = notion_helper.get_database_properties(selected_db_id)
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
                success = notion_helper.create_notion_page(db_id, collected_data, prop_types)
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

    # 7. URL送信
    if user_message.startswith("http://") or user_message.startswith("https://"):
        res_text = notion_helper.add_url_to_notion(user_message)
        reply_line(event.reply_token, res_text)
        return

    # 8. Notion リンク表示
    if user_message in ["リンク", "Notion", "notion", "Notionリンク", "notionリンク"]:
        if NOTION_PAGE_URL:
            reply_line(event.reply_token, f"Notionのページはこちらです:\n{NOTION_PAGE_URL}")
        else:
            reply_line(event.reply_token, "NotionのURLが設定されていません。")
        return

    # 9. データ追加
    if user_message == "データ追加":
        start_db_selection(user_id, event.reply_token)
        return

    # 10. ヘルプ
    if user_message in ["ヘルプ", "help", "Help", "使い方"]:
        help_text = (
            "【Notionアシスタントの使い方】\n\n"
            "◆ データ検索\n"
            "知りたい情報をそのまま質問してください。\n"
            "例: 今月の食費合計は？ / 楽天カードの利用履歴教えて\n\n"
            "◆ 手動で支出記録\n"
            "支出 金額 店名（例: 支出 1200 ラーメン）\n\n"
            "◆ 予算の設定\n"
            "・全体予算: 予算 100000\n"
            "・ジャンル予算: 予算 食費 30000\n\n"
            "◆ 固定費・サブスクの一括登録\n"
            "・一括登録: 固定費\n"
            "・一覧確認: 固定費一覧\n\n"
            "◆ 後で見るURL追加\n"
            "URL（http...）を送るとリストへ追加されます。\n\n"
            "◆ 汎用データ追加\n"
            "データ追加 と送信すると対話形式で任意のNotion DBへ追加できます。\n\n"
            "◆ Notionリンク\n"
            "Notion と送信するとページURLを表示します。"
        )
        reply_line(event.reply_token, help_text)
        return

    # 11. 通常検索（Gemini回答）
    try:
        notion_context = notion_helper.fetch_notion_context()
        ai_response = notion_helper.generate_gemini_response(user_message, notion_context)
    except Exception as e:
        ai_response = f"エラーが発生しました: {str(e)}"

    reply_line(event.reply_token, ai_response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
