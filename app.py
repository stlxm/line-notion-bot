import os
import re
import json
import threading
from urllib.parse import parse_qsl
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    PushMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

import kakeibo
import notion_helper
import memo
import menu
import budget
import insights
import ui

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
NOTION_PAGE_URL = os.environ.get("NOTION_PAGE_URL", "")
NOTION_DATABASE_IDS = os.environ.get("NOTION_DATABASE_IDS", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "")
SCHEDULER_SECRET = os.environ.get("SCHEDULER_SECRET", "")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
user_states = {}
JST = timezone(timedelta(hours=9), "JST")


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


def _scheduler_authorized():
    if not SCHEDULER_SECRET:
        return False
    return request.headers.get("X-API-KEY", "") == SCHEDULER_SECRET


@app.route("/api/register-fixed", methods=["POST"])
def api_register_fixed():
    count, total = kakeibo.register_monthly_fixed_expenses()
    return json.dumps({"status": "success", "count": count, "total": total}), 200


@app.route("/api/monthly-notice", methods=["POST"])
def api_monthly_notice():
    if ADMIN_USER_ID:
        push_line(ADMIN_USER_ID, kakeibo.create_monthly_budget_prompt_flex())
    return json.dumps({"status": "success", "message": "Monthly notice triggered"}), 200


@app.route("/api/daily-memo", methods=["POST"])
def api_daily_memo():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    if not ADMIN_USER_ID:
        return json.dumps({"status": "error", "message": "ADMIN_USER_ID is not configured"}), 500

    memos = memo.get_memos_from_notion()
    if memos:
        lines = ["📝 今日のメモ一覧", ""]
        for item in memos[:30]:
            lines.append(f"・{item['title']}")
        if len(memos) > 30:
            lines.append(f"\nほか {len(memos) - 30} 件あります。")
        lines.append("\n不要なものは「メモ削除」で整理できます。")
        message = "\n".join(lines)
    else:
        message = "📝 今日のメモ一覧\n\n現在保存されているメモはありません。"

    try:
        push_line(ADMIN_USER_ID, message)
        return json.dumps({"status": "success", "count": len(memos)}), 200
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}), 500


@app.route("/api/budget-alert", methods=["POST"])
def api_budget_alert():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    if not ADMIN_USER_ID:
        return json.dumps({"status": "error", "message": "ADMIN_USER_ID is not configured"}), 500

    alerts = insights.get_budget_alerts()
    if not alerts:
        return json.dumps({"status": "success", "sent": False, "alerts": 0}), 200

    try:
        push_line(ADMIN_USER_ID, insights.create_budget_alert_flex())
        return json.dumps({"status": "success", "sent": True, "alerts": len(alerts)}), 200
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}), 500


@app.route("/api/weekly-report", methods=["POST"])
def api_weekly_report():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    if not ADMIN_USER_ID:
        return json.dumps({"status": "error", "message": "ADMIN_USER_ID is not configured"}), 500

    try:
        push_line(ADMIN_USER_ID, insights.create_weekly_report_flex())
        return json.dumps({"status": "success", "sent": True}), 200
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}), 500


def _format_messages(messages):
    if isinstance(messages, str):
        return [TextMessage(text=messages)]
    if not isinstance(messages, list):
        messages = [messages]
    return [TextMessage(text=m) if isinstance(m, str) else m for m in messages]


def reply_line(reply_token, messages):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=_format_messages(messages))
        )


def push_line(user_id, messages):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(to=user_id, messages=_format_messages(messages))
        )


def start_db_selection(user_id, reply_token):
    db_list = [db_id.strip() for db_id in NOTION_DATABASE_IDS.split(",") if db_id.strip()]
    if not db_list:
        reply_line(reply_token, "登録先データベースが設定されていません。NOTION_DATABASE_IDS を確認してください。")
        return

    display_names = [notion_helper.get_database_title(db_id) for db_id in db_list]
    user_states[user_id] = {"step": "SELECT_DB", "db_list": db_list}
    lines = ["追加するデータベースを番号で選んでください。"]
    for index, title in enumerate(display_names, start=1):
        lines.append(f"{index}. {title}")
    lines.append("\nやめる場合は「キャンセル」と送信してください。")
    reply_line(reply_token, "\n".join(lines))


def start_manual_kakeibo(user_id, reply_token, text):
    parts = text.replace("　", " ").strip().split()
    if len(parts) < 2:
        reply_line(reply_token, "形式が正しくありません。\n【入力例】\n支出 1200 ラーメン")
        return
    try:
        amount = float(parts[1])
    except ValueError:
        reply_line(reply_token, "金額は数値で入力してください。（例: 支出 1200 ラーメン）")
        return

    store_name = " ".join(parts[2:]) if len(parts) >= 3 else "未入力"
    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    user_states[user_id] = {
        "step": "MANUAL_KAKEIBO_GENRE",
        "amount": amount,
        "store": store_name,
        "date": date_str,
    }

    categories = kakeibo.get_notion_select_options(
        NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=kakeibo.EXCLUDED_GENRES
    ) or ["食費", "日用品", "交通費", "娯楽"]
    reply_line(reply_token, [ui.create_choice_flex(
        "ジャンルを選択してください", categories, "manual_cat_select", include_cancel=True
    )])


def _card_category_flex(card, store, amount, date_str):
    categories = kakeibo.get_notion_select_options(
        NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=kakeibo.EXCLUDED_GENRES
    ) or ["食費", "日用品", "交通費", "娯楽"]
    return ui.create_card_category_flex(card, store, amount, date_str, categories)


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    params = dict(parse_qsl(event.postback.data))
    action = params.get("action")

    if action == "quick_input_kakeibo":
        reply_line(event.reply_token, "支出を入力します。\n【送信例】\n・支出 1200 ラーメン\n・支出 500 コンビニ")
        return

    if action == "quick_input_memo":
        reply_line(event.reply_token, "メモを追加します。\n「メモ 」に続けて内容を送ってください。\n\n例: メモ 牛乳を買う")
        return

    if action == "cancel_registration":
        user_states.pop(user_id, None)
        reply_line(event.reply_token, "操作をキャンセルしました。")
        return

    if action == "start_monthly_budget_input":
        user_states[user_id] = {"step": "WAITING_MONTHLY_BUDGET"}
        reply_line(event.reply_token, "📅 今月の全体予算を入力して送信してください。\n（例: 100000）\n※やめる場合は キャンセル と送信してください")
        return

    if action == "card_select_cat":
        reply_line(event.reply_token, [
            TextMessage(text="ジャンル選択へ進みます。"),
            _card_category_flex(params.get("card"), params.get("store"), params.get("amount"), params.get("date")),
        ])
        return

    if action == "card_change_store_start":
        user_states[user_id] = {
            "step": "WAITING_STORE_NAME_CHANGE",
            "card": params.get("card"),
            "old_store": params.get("store"),
            "amount": params.get("amount"),
            "date": params.get("date"),
        }
        reply_line(event.reply_token, f"✏️ 新しい利用先・店名を入力してください。\n（現在の仮名称: {params.get('store')}）")
        return

    if action == "prepare_delete_memo":
        page_id = params.get("id")
        title = params.get("title", "無題")
        if not page_id:
            reply_line(event.reply_token, "削除対象のメモを特定できませんでした。")
            return
        reply_line(event.reply_token, [memo.create_memo_delete_confirm_flex(page_id, title)])
        return

    if action in ["confirm_delete_memo", "delete_memo"]:
        page_id = params.get("id")
        title = params.get("title", "メモ")
        success = memo.delete_memo_from_notion(page_id)
        reply_line(event.reply_token, f"🗑️ メモ「{title}」を削除しました。" if success else "メモの削除に失敗しました。")
        return

    if action == "kakeibo_save":
        res_msg = kakeibo.save_kakeibo_to_notion(
            params.get("card"), params.get("store"), params.get("amount"),
            params.get("date"), params.get("cat")
        )
        messages = [
            TextMessage(text=f"📌「{params.get('cat')}」を選択しました。"),
            TextMessage(text=res_msg),
        ]
        alerts = insights.get_budget_alerts()
        if alerts:
            messages.append(insights.create_budget_alert_flex())
        reply_line(event.reply_token, messages)
        return

    if action == "manual_cat_select" and user_id in user_states:
        selected_cat = params.get("val")
        user_states[user_id]["category"] = selected_cat
        user_states[user_id]["step"] = "MANUAL_KAKEIBO_CARD"
        cards = kakeibo.get_notion_select_options(
            NOTION_KAKEIBO_DATABASE_ID, "カード・支払方法"
        ) or ["現金", "JCB", "三井住友カード", "PayPay", "楽天カード"]
        reply_line(event.reply_token, [
            TextMessage(text=f"📌「{selected_cat}」を選択しました。"),
            ui.create_choice_flex("支払方法を選択してください", cards, "manual_card_select", include_cancel=True),
        ])
        return

    if action == "manual_card_select" and user_id in user_states:
        selected_card = params.get("val")
        state_data = user_states[user_id]
        res_msg = kakeibo.save_kakeibo_to_notion(
            selected_card, state_data["store"], state_data["amount"],
            state_data["date"], state_data["category"]
        )
        del user_states[user_id]
        messages = [
            TextMessage(text=f"💳「{selected_card}」を選択しました。"),
            TextMessage(text=res_msg),
        ]
        alerts = insights.get_budget_alerts()
        if alerts:
            messages.append(insights.create_budget_alert_flex())
        reply_line(event.reply_token, messages)
        return


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    reply_token = event.reply_token

    if user_message in ["メニュー", "機能", "機能一覧", "menu", "Menu"]:
        reply_line(reply_token, [menu.create_main_menu_flex()])
        return

    if user_message in ["今月", "ダッシュボード", "家計簿ダッシュボード", "今月の家計簿"]:
        try:
            reply_line(reply_token, [insights.create_dashboard_flex()])
        except Exception as e:
            print(f"ダッシュボードエラー: {e}")
            reply_line(reply_token, "家計簿ダッシュボードの取得に失敗しました。Notion設定を確認してください。")
        return

    if user_message in ["予算アラート", "予算警告", "アラート"]:
        try:
            reply_line(reply_token, [insights.create_budget_alert_flex()])
        except Exception as e:
            print(f"予算アラートエラー: {e}")
            reply_line(reply_token, "予算アラートの取得に失敗しました。")
        return

    if user_message in ["週次レポート", "週間レポート", "今週"]:
        try:
            reply_line(reply_token, [insights.create_weekly_report_flex()])
        except Exception as e:
            print(f"週次レポートエラー: {e}")
            reply_line(reply_token, "週次レポートの取得に失敗しました。")
        return

    if user_message.startswith("CARD_NOTIFY|"):
        parts = user_message.split("|")
        if len(parts) >= 5:
            _, card_name, store_name, amount, date_str = parts[:5]
            reply_line(reply_token, [kakeibo.create_card_notify_action_flex(card_name, store_name, amount, date_str)])
            return

    if user_message == "キャンセル":
        if user_id in user_states:
            state_data = user_states[user_id]
            if state_data.get("step") == "WAITING_STORE_NAME_CHANGE":
                flex_msg = _card_category_flex(
                    state_data["card"], state_data["old_store"], state_data["amount"], state_data["date"]
                )
                store = state_data["old_store"]
                del user_states[user_id]
                reply_line(reply_token, [f"店名変更をキャンセルしました。（元の名称: {store}）", flex_msg])
                return
            del user_states[user_id]
            reply_line(reply_token, "処理を中断しました。")
        else:
            reply_line(reply_token, "進行中の処理はありません。")
        return

    if user_id in user_states and user_states[user_id].get("step") == "WAITING_STORE_NAME_CHANGE":
        state_data = user_states.pop(user_id)
        flex_msg = _card_category_flex(
            state_data["card"], user_message, state_data["amount"], state_data["date"]
        )
        reply_line(reply_token, [TextMessage(text=f"店名を「{user_message}」に変更しました。"), flex_msg])
        return

    if user_id in user_states and user_states[user_id].get("step") == "WAITING_MONTHLY_BUDGET":
        if user_message.isdigit():
            budget_amount = int(user_message)
            target_month = datetime.now(JST).strftime("%Y-%m")
            success = kakeibo.set_budget_in_notion(target_month, budget_amount, category=None)
            del user_states[user_id]
            if success:
                reply_line(reply_token, f"設定完了！\n{target_month} の全体予算を ¥{budget_amount:,} に設定しました。")
            else:
                reply_line(reply_token, "予算の保存に失敗しました。Notionの月別管理DBを確認してください。")
        else:
            reply_line(reply_token, "金額は半角の数字のみで入力してください。\n（例: 100000）\n※やめる場合は キャンセル と送信してください")
        return

    if user_message.startswith("メモ ") or user_message.startswith("メモ　"):
        memo_text = user_message[3:].strip()
        if memo_text:
            reply_line(reply_token, memo.add_memo_to_notion(memo_text))
            return

    if user_message in ["メモ一覧", "メモ確認"]:
        memos = memo.get_memos_from_notion()
        if not memos:
            reply_line(reply_token, "現在保存されているメモはありません。")
        else:
            lines = ["【保存中のメモ一覧】"]
            for m in memos:
                date_text = f" ({m.get('date', '')[:10]})" if m.get("date") else ""
                lines.append(f"・{m['title']}{date_text}")
            lines.append("\n※ メモ削除 と送信すると、確認画面付きで削除できます。")
            reply_line(reply_token, "\n".join(lines))
        return

    if user_message in ["メモ削除", "メモ 削除", "メモ　削除"]:
        flex_msg = memo.create_memo_delete_flex()
        reply_line(reply_token, [flex_msg] if flex_msg else "削除できるメモがありません。")
        return

    if user_message in ["予算一覧", "予算確認", "今月の予算"]:
        try:
            reply_line(reply_token, [budget.create_budget_overview_flex()])
        except Exception as e:
            print(f"予算一覧エラー: {e}")
            reply_line(reply_token, "予算一覧の取得に失敗しました。Notionの月別管理DBと家計簿DBを確認してください。")
        return

    if user_message in ["予算設定", "予算を設定"]:
        user_states[user_id] = {"step": "WAITING_MONTHLY_BUDGET"}
        reply_line(reply_token, "今月の全体予算を数字で送信してください。\n例: 100000\n\nジャンル別は「予算 食費 30000」のように送信できます。")
        return

    if user_message.startswith("予算"):
        parts = user_message.replace("　", " ").split()
        target_month = datetime.now(JST).strftime("%Y-%m")
        category = None
        budget_val = None
        if len(parts) == 2 and parts[1].isdigit():
            budget_val = parts[1]
        elif len(parts) == 3:
            if re.match(r"^\d{4}-\d{2}$", parts[1]):
                target_month, budget_val = parts[1], parts[2]
            else:
                category, budget_val = parts[1], parts[2]
        elif len(parts) >= 4:
            target_month, category, budget_val = parts[1], parts[2], parts[3]

        if budget_val and budget_val.isdigit():
            success = kakeibo.set_budget_in_notion(target_month, int(budget_val), category)
            target_label = f"{category} の" if category else "全体の"
            reply_text = (
                f"予算設定完了\n{target_month} の{target_label}予算を ¥{int(budget_val):,} に設定しました"
                if success else "予算設定に失敗しました。Notionの月別管理DBを確認してください"
            )
        else:
            reply_text = "【予算設定の使い方】\n・一覧表示: 予算一覧\n・全体予算: 予算 100000\n・ジャンル別: 予算 食費 30000\n・年月指定: 予算 2026-10 食費 35000"
        reply_line(reply_token, reply_text)
        return

    if user_message.startswith("固定費追加"):
        parts = user_message.replace("　", " ").split()
        if len(parts) >= 3 and parts[2].isdigit():
            store_name = parts[1]
            amount = float(parts[2])
            category = parts[3] if len(parts) >= 4 else "固定費"
            card_name = parts[4] if len(parts) >= 5 else "現金"
            success = kakeibo.add_fixed_expense_to_notion(store_name, amount, category, card_name)
            if success:
                reply_text = (
                    f"【固定費マスタに追加しました】\n・内容: {store_name}\n・金額: ¥{int(amount):,}\n"
                    f"・ジャンル: {category}\n・支払方法: {card_name}\n\n"
                    "※ 次回の 固定費 一括登録から自動で反映されます。"
                )
            else:
                reply_text = "固定費マスタへの追加に失敗しました。Notionの設定を確認してください。"
        else:
            reply_text = (
                "【固定費追加の使い方】\n固定費追加 店名 金額 [ジャンル] [支払方法]\n\n"
                "例: 固定費追加 ジム会費 8000 固定費 三井住友カード\n"
                "例: 固定費追加 Netflix 1490 サブスク JCB"
            )
        reply_line(reply_token, reply_text)
        return

    if user_message in ["固定費", "固定費登録", "固定費 登録", "固定費　登録"]:
        count, total = kakeibo.register_monthly_fixed_expenses()
        today_month = datetime.now(JST).strftime("%Y-%m")
        if count > 0:
            reply_text = f"今月分（{today_month}）の固定費・サブスクを一括登録しました！\n・件数: {count} 件\n・合計: ¥{total:,}"
        else:
            reply_text = "登録対象の固定費が見つかりませんでした。Notionの固定費マスタを確認してください。"
        reply_line(reply_token, reply_text)
        return

    if user_message in ["固定費一覧", "固定費確認"]:
        items = kakeibo.get_fixed_expenses_from_notion()
        if not items:
            reply_line(reply_token, "有効な固定費が登録されていません。")
        else:
            lines = ["【現在有効な固定費一覧】"]
            total = 0
            for item in items:
                lines.append(f"・{item['store_name']}: ¥{int(item['amount']):,} ({item['card_name']})")
                total += item["amount"]
            lines.append(f"\n合計: ¥{int(total):,}/月")
            lines.append("\n※ LINEで 固定費 と送信すると、今月の家計簿へ一括登録されます。")
            reply_line(reply_token, "\n".join(lines))
        return

    if user_message.startswith("支出"):
        start_manual_kakeibo(user_id, reply_token, user_message)
        return

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
                        reply_line(reply_token, "プロパティの取得に失敗しました。最初からやり直してください。")
                        del user_states[user_id]
                        return
                    state_data.update({
                        "selected_db_id": selected_db_id,
                        "properties": props,
                        "current_prop_index": 0,
                        "collected_data": {},
                        "step": "INPUT_PROPERTY",
                    })
                    reply_line(reply_token, f"{props[0][0]} は何ですか？")
                    return
            reply_line(reply_token, "有効な番号を送信してください。（中断する場合は キャンセル と送信してください）")
            return

        if step == "INPUT_PROPERTY":
            props = state_data["properties"]
            curr_idx = state_data["current_prop_index"]
            prop_name, _ = props[curr_idx]
            state_data["collected_data"][prop_name] = user_message
            next_idx = curr_idx + 1
            if next_idx < len(props):
                state_data["current_prop_index"] = next_idx
                reply_line(reply_token, f"{props[next_idx][0]} は何ですか？")
            else:
                state_data["step"] = "CONFIRM"
                confirm_lines = ["【入力内容の確認】"]
                for p_name, val in state_data["collected_data"].items():
                    confirm_lines.append(f"{p_name}: {val}")
                confirm_lines.append("\nこの内容でデータベースに追加してよろしいですか？\n( はい / いいえ )")
                reply_line(reply_token, "\n".join(confirm_lines))
            return

        if step == "CONFIRM":
            if user_message == "はい":
                success = notion_helper.create_notion_page(
                    state_data["selected_db_id"], state_data["collected_data"],
                    {p[0]: p[1] for p in state_data["properties"]}
                )
                del user_states[user_id]
                reply_line(reply_token, "データベースに正常に追加しました！" if success else "登録に失敗しました。Notionの書き込み権限等を確認してください。")
            elif user_message == "いいえ":
                reply_line(reply_token, "登録をキャンセルし、最初からやり直します。")
                start_db_selection(user_id, reply_token)
            else:
                reply_line(reply_token, "はい または いいえ で送信してください。（中断する場合は キャンセル と送信してください）")
            return

    if user_message.startswith("http://") or user_message.startswith("https://"):
        reply_line(reply_token, notion_helper.add_url_to_notion(user_message))
        return

    if user_message in ["リンク", "Notion", "notion", "Notionリンク", "notionリンク"]:
        reply_line(reply_token, f"Notionのページはこちらです:\n{NOTION_PAGE_URL}" if NOTION_PAGE_URL else "NotionのURLが設定されていません。")
        return

    if user_message == "データ追加":
        start_db_selection(user_id, reply_token)
        return

    if user_message in ["ヘルプ", "help", "Help", "使い方"]:
        help_text = (
            "【Notionアシスタントの使い方】\n\n"
            "◆ 家計簿\n"
            "・今月: 家計簿ダッシュボード\n"
            "・週次レポート: 直近7日と前7日を比較\n"
            "・予算アラート: 80% / 90% / 100%を確認\n"
            "・支出入力: 支出 1200 ラーメン\n"
            "・予算一覧: 予算一覧\n"
            "・全体予算: 予算 100000\n"
            "・ジャンル予算: 予算 食費 30000\n"
            "・固定費一覧: 固定費一覧\n"
            "・固定費一括登録: 固定費\n\n"
            "◆ メモ\n"
            "・追加: メモ 卵を買う\n"
            "・一覧: メモ一覧\n"
            "・削除: メモ削除（確認あり）\n\n"
            "◆ Notion\n"
            "・データ追加: データ追加\n"
            "・URL保存: URLをそのまま送信\n"
            "・Notionリンク: Notion\n\n"
            "◆ AI検索\n知りたい情報をそのまま質問してください。"
        )
        reply_line(reply_token, help_text)
        return

    reply_line(reply_token, "最大60秒お待ちください…データを検索・処理しています。")

    def background_ai_search(uid, msg):
        result_container = {}

        def target_task():
            try:
                notion_context = notion_helper.fetch_notion_context()
                result_container["response"] = notion_helper.generate_gemini_response(msg, notion_context)
            except Exception as e:
                result_container["response"] = f"エラーが発生しました: {str(e)}"

        t = threading.Thread(target=target_task)
        t.start()
        t.join(timeout=60)
        if t.is_alive():
            push_line(uid, "申し訳ありません。60秒のタイムアウト制限を超えたため処理を中断しました。もう一度やり直してください。")
        else:
            push_line(uid, result_container.get("response", "応答の生成に失敗しました。"))

    threading.Thread(target=background_ai_search, args=(user_id, user_message)).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
