import os
import re
import json
import threading
import uuid
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
import ai_feedback
import ai_engine
import card_queue
import card_rules
import card_phase1
import ledger_guard
import finance_phase2
import phase2_commands

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
NOTION_PAGE_URL = os.environ.get("NOTION_PAGE_URL", "")
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
    return bool(SCHEDULER_SECRET) and request.headers.get("X-API-KEY", "") == SCHEDULER_SECRET


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


@app.route("/api/card-pending", methods=["POST"])
def api_card_pending():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    required = ["message_id", "card", "store", "amount", "date"]
    missing = [key for key in required if data.get(key) in [None, ""]]
    if missing:
        return json.dumps({"status": "error", "message": f"missing: {','.join(missing)}"}), 400

    ledger_dup = ledger_guard.find_duplicate(data["card"], data["store"], data["amount"], data["date"])
    if ledger_dup:
        return json.dumps({
            "status": "success", "created": False,
            "pending_id": f"ledger-reconciled:{data['message_id']}",
            "notified": True, "reconciled_ledger": True,
            "pending_count": card_queue.get_pending_count(),
        }, ensure_ascii=False), 200

    result = card_queue.enqueue_card(data["message_id"], data["card"], data["store"], data["amount"], data["date"])
    if not result.get("ok"):
        return json.dumps({"status": "error", "message": result.get("error", "enqueue failed")}), 500

    item = result["item"]
    if result.get("ignored_fixed"):
        return json.dumps({
            "status": "success", "created": False,
            "pending_id": item.get("id"), "notified": True,
            "ignored_fixed": True, "pending_count": card_queue.get_pending_count(),
        }, ensure_ascii=False), 200

    auto = card_phase1.try_auto_register(item.get("id"))
    if auto.get("status") == "saved":
        if ADMIN_USER_ID:
            push_line(
                ADMIN_USER_ID,
                f"💳 カード利用を自動登録しました。\n{auto['item']['store']} / ¥{int(float(auto['item']['amount'])):,}\nジャンル: {auto['category']}"
            )
        return json.dumps({
            "status": "success", "created": result.get("created", False),
            "pending_id": item.get("id"), "notified": True,
            "auto_registered": True, "pending_count": card_queue.get_pending_count(),
        }, ensure_ascii=False), 200

    return json.dumps({
        "status": "success", "created": result.get("created", False),
        "pending_id": item.get("id"), "notified": item.get("notified", False),
        "reconciled_pending": result.get("reconciled_pending", False),
        "pending_count": card_queue.get_pending_count(),
    }, ensure_ascii=False), 200


@app.route("/api/card-pending-notified", methods=["POST"])
def api_card_pending_notified():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    pending_id = data.get("pending_id")
    if not pending_id:
        return json.dumps({"status": "error", "message": "pending_id is required"}), 400
    success = card_queue.mark_notified(pending_id)
    return json.dumps({"status": "success" if success else "error"}), 200 if success else 500


@app.route("/api/card-pending-reminder", methods=["POST"])
def api_card_pending_reminder():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    if not ADMIN_USER_ID:
        return json.dumps({"status": "error", "message": "ADMIN_USER_ID is not configured"}), 500
    count = card_queue.get_pending_count()
    if count <= 0:
        return json.dumps({"status": "success", "sent": False, "pending_count": 0}), 200
    try:
        push_line(ADMIN_USER_ID, f"💳 ジャンル未選択のカード利用が {count} 件あります。\n「カード未処理」と送ると続けて処理できます。")
        return json.dumps({"status": "success", "sent": True, "pending_count": count}), 200
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}), 500


@app.route("/api/card-month-end-check", methods=["POST"])
def api_card_month_end_check():
    if not _scheduler_authorized():
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401
    if not ADMIN_USER_ID:
        return json.dumps({"status": "error", "message": "ADMIN_USER_ID is not configured"}), 500
    now = datetime.now(JST)
    tomorrow = now + timedelta(days=1)
    force = bool((request.get_json(silent=True) or {}).get("force"))
    if not force and tomorrow.month == now.month:
        return json.dumps({"status": "success", "sent": False, "reason": "not_month_end"}), 200
    count = card_queue.get_pending_count()
    text = (
        "✅ 月末カードチェック: 未処理は0件です。この月のカード分類は完了しています。"
        if count == 0 else
        f"⚠️ 月末カードチェック: ジャンル未選択が {count} 件残っています。\n「カード未処理」と送って月を締める前に処理してください。"
    )
    try:
        push_line(ADMIN_USER_ID, text)
        return json.dumps({"status": "success", "sent": True, "pending_count": count}), 200
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
    db_list = notion_helper.get_all_database_ids()
    if not db_list:
        reply_line(reply_token, "登録先データベースが設定されていません。RenderのNotion DB環境変数を確認してください。")
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
    user_states[user_id] = {"step": "MANUAL_KAKEIBO_GENRE", "amount": amount, "store": store_name, "date": date_str}
    categories = kakeibo.get_notion_select_options(NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=kakeibo.EXCLUDED_GENRES) or ["食費", "日用品", "交通費", "娯楽"]
    reply_line(reply_token, [ui.create_choice_flex("ジャンルを選択してください", categories, "manual_cat_select", include_cancel=True)])


def _card_category_flex(card, store, amount, date_str, pending_id=None, save_action="kakeibo_save"):
    categories = kakeibo.get_notion_select_options(NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=kakeibo.EXCLUDED_GENRES) or ["食費", "日用品", "交通費", "娯楽", "サブスク"]
    context = {"suggestion": None, "same_store_count": 1}
    if pending_id:
        item = card_queue.get_item(pending_id)
        if item:
            context = card_phase1.get_card_view_context(item)
    return ui.create_card_category_flex(
        card, store, amount, date_str, categories, pending_id=pending_id,
        suggestion=context.get("suggestion"), same_store_count=context.get("same_store_count", 1),
        save_action=save_action,
    )


def _next_pending_messages(exclude_id=None):
    next_item = card_queue.get_next_pending(exclude_id=exclude_id)
    if not next_item:
        return [TextMessage(text="✅ カードの未処理はすべて完了しました。")]
    count = card_queue.get_pending_count()
    return [
        TextMessage(text=f"次の未処理カードです。残り {count} 件あります。"),
        _card_category_flex(next_item["card"], next_item["store"], next_item["amount"], next_item["date"], next_item["id"]),
    ]


def _pending_is_active(pending_id):
    return True if not pending_id else card_queue.get_item(pending_id) is not None


def _reply_already_processed(reply_token, pending_id=None):
    messages = [TextMessage(text="このカード利用はすでに処理済みです。古い通知からの二重登録は行いませんでした。")]
    messages.extend(_next_pending_messages(exclude_id=pending_id))
    reply_line(reply_token, messages[:5])


def _pending_item_or_reply(reply_token, pending_id):
    if not pending_id:
        return None
    item = card_queue.get_item(pending_id)
    if not item:
        _reply_already_processed(reply_token, pending_id)
        return None
    return item


def _card_save_result_messages(result, pending_id, category):
    status = result.get("status")
    if status == "duplicate":
        return [ui.create_duplicate_confirm_flex(pending_id, category, result["duplicate"])]
    if status == "missing":
        return None
    if status == "error":
        return [TextMessage(text=result.get("message", "家計簿への保存に失敗しました。未処理は残っています。"))]

    messages = [TextMessage(text=f"📌「{category}」で保存しました。"), TextMessage(text=result["message"])]
    if not result.get("removed", True):
        messages[1] = TextMessage(text=result["message"] + "\n\n⚠️ 家計簿保存は成功しましたが、未処理キューの削除に失敗しました。")
    alerts = insights.get_budget_alerts()
    if alerts:
        messages.append(insights.create_budget_alert_flex())
    messages.extend(_next_pending_messages(exclude_id=pending_id))
    return messages[:5]


def _run_ai_search(user_id, reply_token, query):
    reply_line(reply_token, f"🤖 {ai_engine.get_selected_model_label()}で検索・回答を生成しています。完了後にLINEへ送信します。")

    def background_ai_search(uid, msg):
        result_container = {}
        def target_task():
            try:
                result_container["response"] = ai_engine.generate_response(msg)
            except Exception as e:
                result_container["response"] = f"AI検索でエラーが発生しました: {str(e)}"
        worker = threading.Thread(target=target_task)
        worker.start()
        worker.join(timeout=60)
        if worker.is_alive():
            answer = "AI検索が60秒の制限を超えました。もう一度試してください。"
            ai_feedback.remember_ai_interaction(uid, msg, answer)
            push_line(uid, answer)
        else:
            answer = result_container.get("response", "AIから応答を取得できませんでした。")
            ai_feedback.remember_ai_interaction(uid, msg, answer)
            push_line(uid, [TextMessage(text=answer), TextMessage(text="回答が期待と違う場合は「AI改善」と送ると改善ログに残せます。")])
    threading.Thread(target=background_ai_search, args=(user_id, query), daemon=True).start()


def _run_monthly_review(user_id, reply_token, month_str):
    reply_line(reply_token, f"🤖 {month_str} の月次レビューを{ai_engine.get_selected_model_label()}で生成しています。完了後にLINEへ送信します。")

    def task():
        result = finance_phase2.build_monthly_ai_review(month_str)
        push_line(user_id, result)
    threading.Thread(target=task, daemon=True).start()


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    params = dict(parse_qsl(event.postback.data))
    action = params.get("action")

    if action == "quick_input_kakeibo":
        reply_line(event.reply_token, "支出を入力します。\n【送信例】\n・支出 1200 ラーメン\n・支出 500 コンビニ")
        return
    if action == "quick_input_memo":
        reply_line(event.reply_token, "メモを追加します。\n「メモ 」に続けて内容を送ってください。\n例: メモ 牛乳を買う")
        return
    if action == "cancel_registration":
        user_states.pop(user_id, None)
        reply_line(event.reply_token, "操作をキャンセルしました。")
        return
    if action == "skip_card_pending":
        pending_id = params.get("pending_id")
        if pending_id and not _pending_is_active(pending_id):
            _reply_already_processed(event.reply_token, pending_id)
            return
        if pending_id:
            card_queue.skip(pending_id)
        messages = [TextMessage(text="このカード利用は登録せず、未処理キューから削除しました。")]
        messages.extend(_next_pending_messages(exclude_id=pending_id))
        reply_line(event.reply_token, messages[:5])
        return
    if action == "start_monthly_budget_input":
        user_states[user_id] = {"step": "WAITING_MONTHLY_BUDGET"}
        reply_line(event.reply_token, "📅 今月の全体予算を入力してください。例: 100000\nやめる場合は キャンセル")
        return
    if action in ["card_select_cat", "card_batch_select"]:
        pending_id = params.get("pending_id")
        item = _pending_item_or_reply(event.reply_token, pending_id) if pending_id else None
        if pending_id and not item:
            return
        if item:
            card, store, amount, date_str = item["card"], item["store"], item["amount"], item["date"]
        else:
            card, store, amount, date_str = params.get("card"), params.get("store"), params.get("amount"), params.get("date")
        save_action = "card_batch_save" if action == "card_batch_select" else "kakeibo_save"
        lead = "同じ店の未処理をまとめて分類します。" if action == "card_batch_select" else "ジャンル選択へ進みます。"
        reply_line(event.reply_token, [TextMessage(text=lead), _card_category_flex(card, store, amount, date_str, pending_id, save_action)])
        return
    if action == "card_change_store_start":
        pending_id = params.get("pending_id")
        if pending_id:
            item = _pending_item_or_reply(event.reply_token, pending_id)
            if not item:
                return
            card, old_store, amount, date_str = item["card"], item["store"], item["amount"], item["date"]
        else:
            card, old_store, amount, date_str = params.get("card"), params.get("store"), params.get("amount"), params.get("date")
        user_states[user_id] = {"step": "WAITING_STORE_NAME_CHANGE", "card": card, "old_store": old_store, "amount": amount, "date": date_str, "pending_id": pending_id}
        reply_line(event.reply_token, f"✏️ 新しい利用先・店名を入力してください。\n現在: {old_store}")
        return
    if action in ["card_auto_on", "card_auto_off"]:
        enabled = action == "card_auto_on"
        success, message = card_rules.set_auto_register_by_page_id(params.get("rule_id"), enabled)
        reply_line(event.reply_token, ("✅ " if success else "⚠️ ") + message)
        return
    if action == "card_reconcile_duplicate":
        pending_id = params.get("pending_id")
        if pending_id and card_queue.complete(pending_id):
            messages = [TextMessage(text="既存の家計簿データと同一取引として照合し、未処理から削除しました。")]
            messages.extend(_next_pending_messages(exclude_id=pending_id))
            reply_line(event.reply_token, messages[:5])
        else:
            reply_line(event.reply_token, "未処理カードの照合処理に失敗しました。")
        return
    if action in ["kakeibo_save", "kakeibo_save_force"]:
        pending_id = params.get("pending_id")
        category = params.get("cat")
        if pending_id:
            result = card_phase1.classify_one(pending_id, category, force_duplicate=(action == "kakeibo_save_force"))
            messages = _card_save_result_messages(result, pending_id, category)
            if messages is None:
                _reply_already_processed(event.reply_token, pending_id)
            else:
                reply_line(event.reply_token, messages)
            return
        res_msg = kakeibo.save_kakeibo_to_notion(params.get("card"), params.get("store"), params.get("amount"), params.get("date"), category)
        reply_line(event.reply_token, [TextMessage(text=f"📌「{category}」を選択しました。"), TextMessage(text=res_msg)])
        return
    if action == "card_batch_save":
        pending_id = params.get("pending_id")
        category = params.get("cat")
        result = card_phase1.classify_same_store(pending_id, category)
        if result.get("status") == "missing":
            _reply_already_processed(event.reply_token, pending_id)
            return
        text = (
            f"✅ 同じ店のカード利用をまとめて処理しました。\n対象: {result['total']}件\n保存: {result['saved']}件\n"
            f"既存家計簿と照合: {result['reconciled']}件\n失敗・未処理のまま: {result['failed']}件"
        )
        messages = [TextMessage(text=text)]
        messages.extend(_next_pending_messages())
        reply_line(event.reply_token, messages[:5])
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
    if action == "manual_cat_select" and user_id in user_states:
        selected_cat = params.get("val")
        user_states[user_id]["category"] = selected_cat
        user_states[user_id]["step"] = "MANUAL_KAKEIBO_CARD"
        cards = kakeibo.get_notion_select_options(NOTION_KAKEIBO_DATABASE_ID, "カード・支払方法") or ["現金", "JCB", "三井住友カード", "PayPay", "楽天カード"]
        reply_line(event.reply_token, [TextMessage(text=f"📌「{selected_cat}」を選択しました。"), ui.create_choice_flex("支払方法を選択してください", cards, "manual_card_select", include_cancel=True)])
        return
    if action == "manual_card_select" and user_id in user_states:
        selected_card = params.get("val")
        state_data = user_states[user_id]
        res_msg = kakeibo.save_kakeibo_to_notion(selected_card, state_data["store"], state_data["amount"], state_data["date"], state_data["category"])
        del user_states[user_id]
        messages = [TextMessage(text=f"💳「{selected_card}」を選択しました。"), TextMessage(text=res_msg)]
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

    if user_id in user_states and user_states[user_id].get("step") == "WAITING_AI_FEEDBACK":
        state = user_states.pop(user_id)
        if user_message == "キャンセル":
            reply_line(reply_token, "AI改善の登録をキャンセルしました。")
            return
        success, message = ai_feedback.save_feedback(state["question"], state["answer"], user_message)
        if success:
            ai_feedback.clear_last_ai_interaction(user_id)
            reply_line(reply_token, f"✅ {message}\n\n今後、似たAI質問ではこの改善例を自動で参考にします。")
        else:
            reply_line(reply_token, f"⚠️ {message}\n入力内容は保存されていません。")
        return

    if user_message in ["メニュー", "機能", "機能一覧", "menu", "Menu"]:
        reply_line(reply_token, [menu.create_main_menu_flex()])
        return

    review_month = phase2_commands.parse_monthly_review_command(user_message)
    if review_month is False:
        reply_line(reply_token, "月次レビューは「月次レビュー」または「月次レビュー 2026-08」の形式で送ってください。")
        return
    if review_month:
        _run_monthly_review(user_id, reply_token, review_month)
        return

    phase2_reply = phase2_commands.handle_text_command(user_message)
    if phase2_reply is not None:
        if user_message.startswith("月締め ") or user_message == "月締め":
            pending_count = card_queue.get_pending_count()
            if pending_count > 0:
                phase2_reply += f"\n\n⚠️ カード未処理が {pending_count} 件あります。月締め確定前に確認をおすすめします。"
        reply_line(reply_token, phase2_reply)
        return

    if user_message == "カードテスト":
        if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
            reply_line(reply_token, "カードテストは管理者のみ利用できます。")
            return
        now = datetime.now(JST)
        amount = 100 + (now.microsecond % 900)
        result = card_queue.enqueue_card(f"phase1-test-{uuid.uuid4()}", "JCB", "Phase1テストショップ", amount, now.strftime("%Y-%m-%d"))
        if not result.get("ok"):
            reply_line(reply_token, f"⚠️ テスト用カードを作成できませんでした。\n{result.get('error', 'unknown error')}")
            return
        if result.get("ignored_fixed"):
            reply_line(reply_token, "⚠️ Phase1テストショップが固定費/サブスク除外対象になっています。固定費DBの該当レコードを無効化してから再試行してください。")
            return
        item = result.get("item") or {}
        reply_line(reply_token, [TextMessage(text="🧪 Phase 1テスト用の未処理カードを1件作成しました。これは実際のカード利用ではありません。"), _card_category_flex(item.get("card"), item.get("store"), item.get("amount"), item.get("date"), item.get("id"))])
        return

    if user_message in ["AI改善", "AIフィードバック", "AI修正"]:
        last = ai_feedback.get_last_ai_interaction(user_id)
        if not last:
            reply_line(reply_token, "改善対象の直前AI回答がありません。先に「AI 質問内容」で質問してください。")
            return
        user_states[user_id] = {"step": "WAITING_AI_FEEDBACK", "question": last["question"], "answer": last["answer"]}
        reply_line(reply_token, f"🧠 AI改善を記録します。\n\n【質問】\n{last['question']}\n\n【AI回答】\n{last['answer'][:800]}\n\n本当はどのように答えてほしかったですか？")
        return

    if user_message in ["カード未処理", "カード保留", "カード未分類"]:
        count = card_queue.get_pending_count()
        if count <= 0:
            reply_line(reply_token, "✅ ジャンル未選択のカード利用はありません。\nテストしたい場合は「カードテスト」と送るとテスト用未処理を1件作れます。")
        else:
            item = card_queue.get_next_pending()
            reply_line(reply_token, [TextMessage(text=f"💳 ジャンル未選択が {count} 件あります。古いものから処理します。"), _card_category_flex(item["card"], item["store"], item["amount"], item["date"], item["id"])])
        return

    if user_message in ["カード自動登録", "カード学習", "カードルール"]:
        rules = card_rules.get_rules(limit=20)
        if not os.environ.get("NOTION_CARD_RULES_DATABASE_ID"):
            reply_line(reply_token, "カード学習ルールDBが未設定です。SETUP.mdの `NOTION_CARD_RULES_DATABASE_ID` を設定してください。")
        else:
            reply_line(reply_token, [ui.create_card_rules_flex(rules)])
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
                pending_id = state_data.get("pending_id")
                if pending_id and not _pending_is_active(pending_id):
                    del user_states[user_id]
                    _reply_already_processed(reply_token, pending_id)
                    return
                flex_msg = _card_category_flex(state_data["card"], state_data["old_store"], state_data["amount"], state_data["date"], pending_id)
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
        pending_id = state_data.get("pending_id")
        if pending_id and not _pending_is_active(pending_id):
            _reply_already_processed(reply_token, pending_id)
            return
        if pending_id:
            card_queue.update_store(pending_id, user_message)
        flex_msg = _card_category_flex(state_data["card"], user_message, state_data["amount"], state_data["date"], pending_id)
        reply_line(reply_token, [TextMessage(text=f"店名を「{user_message}」に変更しました。"), flex_msg])
        return

    if user_id in user_states and user_states[user_id].get("step") == "WAITING_MONTHLY_BUDGET":
        if user_message.isdigit():
            budget_amount = int(user_message)
            target_month = datetime.now(JST).strftime("%Y-%m")
            success = kakeibo.set_budget_in_notion(target_month, budget_amount, category=None)
            del user_states[user_id]
            reply_line(reply_token, f"設定完了！\n{target_month} の全体予算を ¥{budget_amount:,} に設定しました。" if success else "予算の保存に失敗しました。")
        else:
            reply_line(reply_token, "金額は半角の数字のみで入力してください。例: 100000")
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
            lines.append("\n※ メモ削除 と送信すると確認付きで削除できます。")
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
            reply_line(reply_token, "予算一覧の取得に失敗しました。")
        return

    if user_message in ["予算設定", "予算を設定"]:
        user_states[user_id] = {"step": "WAITING_MONTHLY_BUDGET"}
        reply_line(reply_token, "今月の全体予算を数字で送信してください。例: 100000\nジャンル別は「予算 食費 30000」")
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
            reply_text = f"予算設定完了\n{target_month} の{target_label}予算を ¥{int(budget_val):,} に設定しました" if success else "予算設定に失敗しました。"
        else:
            reply_text = "【予算設定】\n・予算 100000\n・予算 食費 30000\n・予算 2026-10 食費 35000"
        reply_line(reply_token, reply_text)
        return

    if user_message.startswith("固定費追加"):
        parts = user_message.replace("　", " ").split()
        if len(parts) >= 3 and parts[2].isdigit():
            store_name, amount = parts[1], float(parts[2])
            category = parts[3] if len(parts) >= 4 else "固定費"
            card_name = parts[4] if len(parts) >= 5 else "現金"
            success = kakeibo.add_fixed_expense_to_notion(store_name, amount, category, card_name)
            reply_text = f"【固定費マスタに追加しました】\n・内容: {store_name}\n・金額: ¥{int(amount):,}\n・ジャンル: {category}\n・支払方法: {card_name}" if success else "固定費マスタへの追加に失敗しました。"
        else:
            reply_text = "【固定費追加】\n固定費追加 店名 金額 [ジャンル] [支払方法]\n例: 固定費追加 Netflix 1490 サブスク JCB"
        reply_line(reply_token, reply_text)
        return

    if user_message in ["固定費", "固定費登録", "固定費 登録", "固定費　登録"]:
        count, total = kakeibo.register_monthly_fixed_expenses()
        today_month = datetime.now(JST).strftime("%Y-%m")
        reply_line(reply_token, f"今月分（{today_month}）の固定費・サブスクを一括登録しました！\n・件数: {count} 件\n・合計: ¥{total:,}" if count > 0 else "登録対象の固定費が見つかりませんでした。")
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
                        reply_line(reply_token, "プロパティの取得に失敗しました。")
                        del user_states[user_id]
                        return
                    state_data.update({"selected_db_id": selected_db_id, "properties": props, "current_prop_index": 0, "collected_data": {}, "step": "INPUT_PROPERTY"})
                    reply_line(reply_token, f"{props[0][0]} は何ですか？")
                    return
            reply_line(reply_token, "有効な番号を送信してください。")
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
                lines = ["【入力内容の確認】"] + [f"{k}: {v}" for k, v in state_data["collected_data"].items()]
                lines.append("\nこの内容で追加しますか？ (はい / いいえ)")
                reply_line(reply_token, "\n".join(lines))
            return
        if step == "CONFIRM":
            if user_message == "はい":
                success = notion_helper.create_notion_page(state_data["selected_db_id"], state_data["collected_data"], {p[0]: p[1] for p in state_data["properties"]})
                del user_states[user_id]
                reply_line(reply_token, "データベースに正常に追加しました！" if success else "登録に失敗しました。")
            elif user_message == "いいえ":
                reply_line(reply_token, "登録をキャンセルし、最初からやり直します。")
                start_db_selection(user_id, reply_token)
            else:
                reply_line(reply_token, "はい または いいえ で送信してください。")
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
            "【Notionアシスタント】\n\n◆ 家計簿・Phase 2\n・今月\n・今日使える\n・ペース\n・予算提案\n・異常支出\n・年間予測\n・月締め\n・月次レビュー\n・貯金目標\n"
            "・週次レポート\n・予算アラート\n・支出 1200 ラーメン\n・予算一覧\n・固定費一覧\n\n"
            "◆ カード\n・カード未処理\n・カードテスト\n・カード自動登録\n\n"
            "◆ メモ\n・メモ 卵を買う\n・メモ一覧\n・メモ削除\n\n"
            "◆ AI\n・AI 質問内容\n・AI Lite\n・AI Flash\n・AI Model\n・AI改善"
        )
        reply_line(reply_token, help_text)
        return

    lowered = user_message.lower()
    if lowered in ["ai lite", "ai ライト"]:
        success, label = ai_engine.set_selected_model("lite")
        reply_line(reply_token, f"✅ AIモデルを {label}（{ai_engine.get_selected_model()}）に切り替えました。" if success else "AIモデルの切替に失敗しました。")
        return
    if lowered in ["ai flash", "ai フラッシュ"]:
        success, label = ai_engine.set_selected_model("flash")
        reply_line(reply_token, f"✅ AIモデルを {label}（{ai_engine.get_selected_model()}）に切り替えました。" if success else "AIモデルの切替に失敗しました。")
        return
    if lowered in ["ai model", "ai モデル"]:
        reply_line(reply_token, f"現在のAIモデル: {ai_engine.get_selected_model_label()}\n{ai_engine.get_selected_model()}")
        return
    if lowered == "ai":
        reply_line(reply_token, f"【AI検索】\n現在: {ai_engine.get_selected_model_label()}（{ai_engine.get_selected_model()}）\n\nAIの後にスペースを入れて質問してください。\n例: AI 今月の食費について分析して\n\n切替: AI Lite / AI Flash\n確認: AI Model\n改善: AI改善")
        return

    ai_match = re.match(r"^AI[ \u3000]+(.+)$", user_message, flags=re.IGNORECASE)
    if ai_match:
        ai_query = ai_match.group(1).strip()
        if ai_query:
            _run_ai_search(user_id, reply_token, ai_query)
            return

    reply_line(reply_token, [TextMessage(text="そのコマンドはありません。メニューから機能を選んでください。\nAIを使う場合は「AI 質問内容」と送信してください。"), menu.create_main_menu_flex()])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
