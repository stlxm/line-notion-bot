import calendar
import os
from datetime import datetime, date, timezone, timedelta
from statistics import median

import requests

import budget
import kakeibo
import ai_engine
import notion_helper

JST = timezone(timedelta(hours=9), "JST")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_SAVINGS_GOALS_DATABASE_ID = os.environ.get("NOTION_SAVINGS_GOALS_DATABASE_ID", "")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _money(value):
    return f"¥{int(round(value or 0)):,}"


def _month_bounds(month_str):
    year, month = map(int, month_str.split("-"))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _page_text(prop):
    if not prop:
        return ""
    kind = prop.get("type")
    if kind == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if kind == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    return ""


def _expense_rows(start_date, end_date):
    pages = budget._query_all(
        budget.NOTION_KAKEIBO_DATABASE_ID,
        {
            "filter": {
                "and": [
                    {"property": "日付", "date": {"on_or_after": start_date}},
                    {"property": "日付", "date": {"before": end_date}},
                ]
            }
        },
    )
    rows = []
    for page in pages:
        props = page.get("properties", {})
        date_obj = props.get("日付", {}).get("date") or {}
        cat_obj = props.get("ジャンル", {}).get("select") or {}
        card_obj = props.get("カード・支払方法", {}).get("select") or {}
        store = _page_text(props.get("内容・店名", {})) or "未入力"
        rows.append({
            "id": page.get("id"),
            "date": (date_obj.get("start") or "")[:10],
            "amount": float(props.get("金額", {}).get("number") or 0),
            "category": cat_obj.get("name") or "未分類",
            "card": card_obj.get("name") or "未設定",
            "store": store,
        })
    return rows


def get_month_summary(month_str=None):
    now = datetime.now(JST)
    month_str = month_str or now.strftime("%Y-%m")
    start, end = _month_bounds(month_str)
    rows = _expense_rows(start.isoformat(), end.isoformat())
    overview = budget.get_budget_overview(month_str)
    total = sum(x["amount"] for x in rows)
    categories = {}
    for row in rows:
        categories[row["category"]] = categories.get(row["category"], 0) + row["amount"]

    days_in_month = (end - start).days
    if month_str == now.strftime("%Y-%m"):
        elapsed_days = now.day
        remaining_days = max(0, days_in_month - now.day + 1)
    elif end <= now.date():
        elapsed_days = days_in_month
        remaining_days = 0
    else:
        elapsed_days = 0
        remaining_days = days_in_month

    total_budget = overview.get("total_budget")
    remaining_budget = total_budget - total if total_budget is not None else None
    daily_allowance = None
    if remaining_budget is not None and remaining_days > 0:
        daily_allowance = remaining_budget / remaining_days

    daily_avg = total / elapsed_days if elapsed_days > 0 else 0
    projected = daily_avg * days_in_month if elapsed_days > 0 else 0
    budget_rate = (total / total_budget) if total_budget else None
    time_rate = (elapsed_days / days_in_month) if days_in_month else 0
    pace_ratio = (budget_rate / time_rate) if budget_rate is not None and time_rate > 0 else None

    return {
        "month": month_str,
        "total": total,
        "count": len(rows),
        "categories": categories,
        "rows": rows,
        "total_budget": total_budget,
        "remaining_budget": remaining_budget,
        "daily_allowance": daily_allowance,
        "daily_avg": daily_avg,
        "projected": projected,
        "days_in_month": days_in_month,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "budget_rate": budget_rate,
        "time_rate": time_rate,
        "pace_ratio": pace_ratio,
    }


def build_daily_allowance_text(month_str=None):
    data = get_month_summary(month_str)
    if data["total_budget"] is None:
        return f"【{data['month']} 1日あたり使える額】\n全体予算が未設定です。先に「予算設定」で設定してください。"
    if data["remaining_days"] <= 0:
        return f"【{data['month']} 1日あたり使える額】\nこの月は終了しています。\n支出: {_money(data['total'])}\n予算: {_money(data['total_budget'])}"
    return (
        f"【{data['month']} 1日あたり使える額】\n"
        f"残り予算: {_money(data['remaining_budget'])}\n"
        f"残り日数: {data['remaining_days']}日\n"
        f"1日あたり: {_money(data['daily_allowance'])}\n"
        f"現在の1日平均: {_money(data['daily_avg'])}"
    )


def build_spending_pace_text(month_str=None):
    data = get_month_summary(month_str)
    if data["total_budget"] is None:
        return f"【{data['month']} 使いすぎペース】\n全体予算が未設定のため判定できません。"
    rate = (data["budget_rate"] or 0) * 100
    time_rate = data["time_rate"] * 100
    projected = data["projected"]
    diff = projected - data["total_budget"]
    if data["pace_ratio"] is None:
        status = "判定データ不足"
    elif data["pace_ratio"] >= 1.15:
        status = "⚠️ かなり速いペース"
    elif data["pace_ratio"] >= 1.05:
        status = "⚠️ やや速いペース"
    else:
        status = "✅ おおむね予算内ペース"
    projected_line = f"月末予測: {_money(projected)}"
    if diff > 0:
        projected_line += f"（予算より {_money(diff)} 多い予測）"
    else:
        projected_line += f"（予算より {_money(abs(diff))} 少ない予測）"
    return (
        f"【{data['month']} 使いすぎペース】\n{status}\n"
        f"月の経過: {time_rate:.0f}%\n"
        f"予算消化: {rate:.0f}%\n"
        f"現在支出: {_money(data['total'])}\n"
        f"{projected_line}"
    )


def get_budget_suggestion(reference_months=3):
    now = datetime.now(JST)
    current_first = date(now.year, now.month, 1)
    months = []
    cursor = current_first
    for _ in range(reference_months):
        prev_day = cursor - timedelta(days=1)
        month_str = prev_day.strftime("%Y-%m")
        months.append(month_str)
        cursor = date(prev_day.year, prev_day.month, 1)

    month_summaries = [get_month_summary(m) for m in months]
    valid = [x for x in month_summaries if x["count"] > 0]
    if not valid:
        return {"months": months, "total": None, "categories": {}}

    total_avg = sum(x["total"] for x in valid) / len(valid)
    suggested_total = int(round(total_avg * 1.05 / 1000.0) * 1000)
    cats = {}
    all_categories = set()
    for summary in valid:
        all_categories.update(summary["categories"].keys())
    for cat in sorted(all_categories):
        avg = sum(x["categories"].get(cat, 0) for x in valid) / len(valid)
        if avg <= 0:
            continue
        cats[cat] = int(round(avg * 1.05 / 500.0) * 500)
    return {"months": [x["month"] for x in valid], "total": suggested_total, "categories": cats}


def build_budget_suggestion_text():
    data = get_budget_suggestion()
    if data["total"] is None:
        return "【予算提案】\n過去3か月の支出データが不足しているため、まだ提案できません。"
    lines = [
        "【次回予算の提案】",
        f"参考: {', '.join(data['months'])}",
        f"全体予算の目安: {_money(data['total'])}",
        "",
        "ジャンル別の目安:",
    ]
    for cat, value in sorted(data["categories"].items(), key=lambda x: x[1], reverse=True)[:10]:
        lines.append(f"・{cat}: {_money(value)}")
    lines.append("\n過去平均に約5%の余裕を加えた提案です。自動では変更しません。")
    return "\n".join(lines)


def get_anomalies():
    now = datetime.now(JST).date()
    current_start = now.replace(day=1)
    history_start = current_start - timedelta(days=120)
    current_rows = _expense_rows(current_start.isoformat(), (now + timedelta(days=1)).isoformat())
    history_rows = _expense_rows(history_start.isoformat(), current_start.isoformat())

    by_category = {}
    all_history = []
    for row in history_rows:
        if row["amount"] <= 0:
            continue
        by_category.setdefault(row["category"], []).append(row["amount"])
        all_history.append(row["amount"])
    global_median = median(all_history) if all_history else 0

    anomalies = []
    for row in current_rows:
        samples = by_category.get(row["category"], [])
        base = median(samples) if len(samples) >= 3 else global_median
        if base <= 0:
            continue
        ratio = row["amount"] / base
        threshold = max(base * 3, base + 5000)
        if row["amount"] >= threshold and ratio >= 2:
            item = dict(row)
            item["baseline"] = base
            item["ratio"] = ratio
            anomalies.append(item)
    return sorted(anomalies, key=lambda x: x["ratio"], reverse=True)[:10]


def build_anomaly_text():
    anomalies = get_anomalies()
    if not anomalies:
        return "【異常支出チェック】\n今月、過去の支出傾向から大きく外れた支出は見つかりませんでした。"
    lines = ["【異常支出チェック】", "過去約4か月の支出中央値と比較しています。"]
    for item in anomalies[:5]:
        lines.append(
            f"・{item['date']} {item['store']} {_money(item['amount'])}\n"
            f"  {item['category']}の基準 {_money(item['baseline'])} の約{item['ratio']:.1f}倍"
        )
    lines.append("\n誤登録とは限りません。高額な予定支出も候補に出ます。")
    return "\n".join(lines)


def get_annual_forecast(year=None):
    now = datetime.now(JST).date()
    year = year or now.year
    start = date(year, 1, 1)
    if year == now.year:
        through = now + timedelta(days=1)
        elapsed = (through - start).days
        days_in_year = 366 if calendar.isleap(year) else 365
    elif year < now.year:
        through = date(year + 1, 1, 1)
        elapsed = (through - start).days
        days_in_year = elapsed
    else:
        through = date(year + 1, 1, 1)
        elapsed = 0
        days_in_year = 366 if calendar.isleap(year) else 365
    rows = _expense_rows(start.isoformat(), through.isoformat()) if elapsed else []
    total = sum(x["amount"] for x in rows)
    projected = (total / elapsed * days_in_year) if elapsed else 0
    return {"year": year, "total": total, "elapsed_days": elapsed, "days_in_year": days_in_year, "projected": projected}


def build_annual_forecast_text(year=None):
    data = get_annual_forecast(year)
    if data["elapsed_days"] <= 0:
        return f"【{data['year']} 年間予測】\nまだ予測に使える支出データがありません。"
    if data["elapsed_days"] == data["days_in_year"]:
        return f"【{data['year']} 年間実績】\n年間支出: {_money(data['total'])}"
    return (
        f"【{data['year']} 年間支出予測】\n"
        f"現在まで: {_money(data['total'])}\n"
        f"現在ペースの年間予測: {_money(data['projected'])}\n"
        f"経過日数: {data['elapsed_days']} / {data['days_in_year']}日"
    )


def close_month(month_str):
    summary = get_month_summary(month_str)
    page_id = kakeibo.get_or_create_monthly_page(f"{month_str}-01")
    if not page_id:
        return False, "月別管理ページを取得できませんでした。", summary
    payload = {
        "properties": {
            "締め済み": {"checkbox": True},
            "締め日時": {"date": {"start": datetime.now(JST).isoformat()}},
            "確定支出": {"number": float(summary["total"])},
        }
    }
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers(), json=payload, timeout=10,
        )
    except Exception as e:
        return False, f"月締め通信エラー: {e}", summary
    if res.status_code != 200:
        return False, "月別管理DBに `締め済み`(Checkbox) / `締め日時`(Date) / `確定支出`(Number) を追加してください。", summary
    return True, f"{month_str} を締めました。確定支出 {_money(summary['total'])} / {summary['count']}件", summary


def build_month_close_preview(month_str):
    summary = get_month_summary(month_str)
    top = sorted(summary["categories"].items(), key=lambda x: x[1], reverse=True)[:5]
    lines = [
        f"【{month_str} 月締め確認】",
        f"支出: {_money(summary['total'])}",
        f"件数: {summary['count']}件",
    ]
    if summary["total_budget"] is not None:
        lines.append(f"予算: {_money(summary['total_budget'])}")
        lines.append(f"差額: {_money(summary['total_budget'] - summary['total'])}")
    if top:
        lines.append("\n上位ジャンル:")
        for cat, value in top:
            lines.append(f"・{cat}: {_money(value)}")
    lines.append(f"\n確定する場合は「月締め確定 {month_str}」と送ってください。")
    return "\n".join(lines)


def build_monthly_ai_review(month_str=None):
    month_str = month_str or datetime.now(JST).strftime("%Y-%m")
    summary = get_month_summary(month_str)
    if summary["count"] <= 0:
        return f"【{month_str} 月次AIレビュー】\n支出データがないためレビューできません。"
    top = sorted(summary["categories"].items(), key=lambda x: x[1], reverse=True)[:8]
    context = "\n".join(f"・{cat}: {_money(value)}" for cat, value in top)
    prompt = (
        "以下の家計簿集計だけを根拠に、月次レビューを日本語で簡潔に作成してください。"
        "断定できないことは推測しないでください。Markdownは使わず、【見出し】と・の箇条書きを使ってください。"
        "改善点は最大3つ、良かった点があれば最大2つ。\n\n"
        f"対象月: {month_str}\n支出合計: {_money(summary['total'])}\n件数: {summary['count']}\n"
        f"予算: {_money(summary['total_budget']) if summary['total_budget'] is not None else '未設定'}\n"
        f"ジャンル別:\n{context}"
    )
    try:
        response = notion_helper.call_gemini_with_retry(ai_engine.get_selected_model(), prompt)
        return f"【{month_str} 月次AIレビュー / {ai_engine.get_selected_model_label()}】\n" + ai_engine.sanitize_for_line(response.text)
    except Exception as e:
        return f"月次AIレビュー生成中にエラーが発生しました: {e}"


def _goal_to_dict(page):
    props = page.get("properties", {})
    title = _page_text(props.get("目標名", {})) or "貯金目標"
    due = (props.get("期限", {}).get("date") or {}).get("start")
    return {
        "id": page.get("id"),
        "name": title,
        "target": float(props.get("目標額", {}).get("number") or 0),
        "current": float(props.get("現在額", {}).get("number") or 0),
        "due": due,
        "active": bool(props.get("有効", {}).get("checkbox", True)),
    }


def get_savings_goals():
    if not NOTION_SAVINGS_GOALS_DATABASE_ID:
        return []
    pages = budget._query_all(
        NOTION_SAVINGS_GOALS_DATABASE_ID,
        {"filter": {"property": "有効", "checkbox": {"equals": True}}},
    )
    return [_goal_to_dict(page) for page in pages]


def add_savings_goal(name, target, current=0, due=None):
    if not NOTION_SAVINGS_GOALS_DATABASE_ID:
        return False, "NOTION_SAVINGS_GOALS_DATABASE_ID が未設定です。"
    properties = {
        "目標名": {"title": [{"text": {"content": str(name)}}]},
        "目標額": {"number": float(target)},
        "現在額": {"number": float(current)},
        "有効": {"checkbox": True},
    }
    if due:
        properties["期限"] = {"date": {"start": due}}
    try:
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_headers(),
            json={"parent": {"database_id": NOTION_SAVINGS_GOALS_DATABASE_ID}, "properties": properties},
            timeout=10,
        )
    except Exception as e:
        return False, f"貯金目標登録エラー: {e}"
    if res.status_code != 200:
        return False, f"貯金目標DBへの登録に失敗しました: {res.text[:300]}"
    return True, f"貯金目標「{name}」を {_money(target)} で登録しました。"


def build_savings_goals_text():
    if not NOTION_SAVINGS_GOALS_DATABASE_ID:
        return "【貯金目標】\n貯金目標DBが未設定です。SETUP.mdを確認してください。"
    goals = get_savings_goals()
    if not goals:
        return "【貯金目標】\n有効な目標はありません。\n例: 貯金目標追加 旅行 300000 50000 2027-03-31"
    lines = ["【貯金目標】"]
    today = datetime.now(JST).date()
    for goal in goals[:10]:
        remaining = max(0, goal["target"] - goal["current"])
        rate = (goal["current"] / goal["target"] * 100) if goal["target"] > 0 else 0
        line = f"・{goal['name']}: {_money(goal['current'])} / {_money(goal['target'])} ({rate:.0f}%)"
        if goal["due"]:
            try:
                due_date = date.fromisoformat(goal["due"][:10])
                days = (due_date - today).days
                months = max(1, days / 30.44)
                monthly_needed = remaining / months if days > 0 else remaining
                line += f"\n  期限 {goal['due'][:10]} / 月あたり目安 {_money(monthly_needed)}"
            except Exception:
                pass
        lines.append(line)
    return "\n".join(lines)
