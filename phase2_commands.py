import re
from datetime import datetime, timezone, timedelta

import requests

import card_queue
import finance_phase2

JST = timezone(timedelta(hours=9), "JST")


def _valid_month(value):
    if not re.fullmatch(r"\d{4}-\d{2}", value or ""):
        return False
    try:
        datetime.strptime(value, "%Y-%m")
        return True
    except ValueError:
        return False


def _valid_date(value):
    if not value:
        return True
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _is_past_month(month_str):
    try:
        target = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
    except ValueError:
        return False
    now = datetime.now(JST).date().replace(day=1)
    return target < now


def _update_goal_current(name, current):
    db_id = finance_phase2.NOTION_SAVINGS_GOALS_DATABASE_ID
    if not db_id:
        return "【貯金目標】\n貯金目標DBが未設定です。SETUP.mdを確認してください。"

    pages = finance_phase2.budget._query_all(
        db_id,
        {"filter": {"property": "目標名", "title": {"equals": name}}},
    )
    active = [page for page in pages if page.get("properties", {}).get("有効", {}).get("checkbox", True)]
    if not active:
        return f"貯金目標「{name}」が見つかりませんでした。"

    page_id = active[0].get("id")
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=finance_phase2._headers(),
            json={"properties": {"現在額": {"number": float(current)}}},
            timeout=10,
        )
    except Exception as e:
        return f"貯金目標の更新中にエラーが発生しました: {e}"
    if res.status_code != 200:
        return "貯金目標の更新に失敗しました。Notion DBのプロパティ名とIntegration権限を確認してください。"
    return f"✅ 貯金目標「{name}」の現在額を ¥{int(current):,} に更新しました。"


def build_phase2_help():
    return (
        "【家計判断 / Phase 2】\n"
        "2A 日々の判断\n"
        "・今日使える\n"
        "・ペース\n"
        "・異常支出\n\n"
        "2B 月次判断\n"
        "・予算提案\n"
        "・月締め\n"
        "・月次レビュー\n\n"
        "2C 将来予測・目標\n"
        "・年間予測\n"
        "・貯金目標\n\n"
        "詳しい形式は「ヘルプ」またはPHASE2_TEST.mdを確認してください。"
    )


def handle_text_command(text):
    """Phase 2の同期コマンドを処理。該当しない場合はNoneを返す。"""
    message = (text or "").strip()

    if message in ["家計判断", "Phase2", "phase2", "フェーズ2"]:
        return build_phase2_help()

    if message in ["今日使える", "1日予算", "今日の予算"]:
        return finance_phase2.build_daily_allowance_text()

    if message in ["ペース", "使いすぎ", "支出ペース"]:
        return finance_phase2.build_spending_pace_text()

    if message in ["予算提案", "予算おすすめ"]:
        return finance_phase2.build_budget_suggestion_text()

    if message in ["異常支出", "異常チェック"]:
        return finance_phase2.build_anomaly_text()

    if message.startswith("年間予測"):
        parts = message.replace("　", " ").split()
        year = None
        if len(parts) >= 2:
            if not re.fullmatch(r"\d{4}", parts[1]):
                return "年間予測は「年間予測」または「年間予測 2026」の形式で送ってください。"
            year = int(parts[1])
        return finance_phase2.build_annual_forecast_text(year)

    if message == "月締め":
        now = datetime.now(JST)
        first = now.replace(day=1)
        previous = first - timedelta(days=1)
        return finance_phase2.build_month_close_preview(previous.strftime("%Y-%m"))

    if message.startswith("月締め ") or message.startswith("月締め　"):
        parts = message.replace("　", " ").split()
        if len(parts) != 2 or not _valid_month(parts[1]):
            return "月締めは「月締め 2026-08」の形式で送ってください。引数なしなら前月を表示します。"
        if not _is_past_month(parts[1]):
            return "月締めは終了済みの月だけ実行できます。今月や未来月は締められません。"
        return finance_phase2.build_month_close_preview(parts[1])

    if message.startswith("月締め確定強制 ") or message.startswith("月締め確定強制　"):
        parts = message.replace("　", " ").split()
        if len(parts) != 2 or not _valid_month(parts[1]):
            return "月締め確定強制は「月締め確定強制 2026-08」の形式で送ってください。"
        if not _is_past_month(parts[1]):
            return "月締めは終了済みの月だけ実行できます。今月や未来月は締められません。"
        success, result, _ = finance_phase2.close_month(parts[1])
        return ("✅ " if success else "⚠️ ") + result

    if message.startswith("月締め確定 ") or message.startswith("月締め確定　"):
        parts = message.replace("　", " ").split()
        if len(parts) != 2 or not _valid_month(parts[1]):
            return "月締め確定は「月締め確定 2026-08」の形式で送ってください。"
        if not _is_past_month(parts[1]):
            return "月締めは終了済みの月だけ実行できます。今月や未来月は締められません。"
        pending_count = card_queue.get_pending_count()
        if pending_count > 0:
            return (
                f"⚠️ カード未処理が {pending_count} 件あるため月締めを停止しました。\n"
                "先に「カード未処理」で処理してください。\n"
                "内容を確認済みで意図的に締める場合だけ、"
                f"「月締め確定強制 {parts[1]}」と送ってください。"
            )
        success, result, _ = finance_phase2.close_month(parts[1])
        return ("✅ " if success else "⚠️ ") + result

    if message == "貯金目標":
        return finance_phase2.build_savings_goals_text()

    if message.startswith("貯金目標追加 ") or message.startswith("貯金目標追加　"):
        parts = message.replace("　", " ").split()
        if len(parts) < 3:
            return "【貯金目標追加】\n貯金目標追加 目標名 目標額 [現在額] [期限]\n例: 貯金目標追加 旅行 300000 50000 2027-03-31"
        name = parts[1]
        try:
            target = float(parts[2].replace(",", ""))
            current = float(parts[3].replace(",", "")) if len(parts) >= 4 else 0
        except ValueError:
            return "目標額・現在額は数字で入力してください。"
        due = parts[4] if len(parts) >= 5 else None
        if target <= 0 or current < 0:
            return "目標額は1以上、現在額は0以上にしてください。"
        if due and not _valid_date(due):
            return "期限は YYYY-MM-DD 形式で入力してください。"
        success, result = finance_phase2.add_savings_goal(name, target, current, due)
        return ("✅ " if success else "⚠️ ") + result

    if message.startswith("貯金更新 ") or message.startswith("貯金更新　"):
        parts = message.replace("　", " ").split()
        if len(parts) != 3:
            return "【貯金更新】\n貯金更新 目標名 現在額\n例: 貯金更新 旅行 80000"
        try:
            current = float(parts[2].replace(",", ""))
        except ValueError:
            return "現在額は数字で入力してください。"
        if current < 0:
            return "現在額は0以上にしてください。"
        return _update_goal_current(parts[1], current)

    return None


def parse_monthly_review_command(text):
    """月次レビューなら対象月を返す。非該当はNone、形式不正はFalse。"""
    message = (text or "").strip()
    if message == "月次レビュー":
        return datetime.now(JST).strftime("%Y-%m")
    if message.startswith("月次レビュー ") or message.startswith("月次レビュー　"):
        parts = message.replace("　", " ").split()
        if len(parts) == 2 and _valid_month(parts[1]):
            return parts[1]
        return False
    return None
