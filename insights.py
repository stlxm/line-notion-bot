import json
from datetime import datetime, timezone, timedelta, date
from urllib.parse import urlencode

from linebot.v3.messaging import FlexMessage, FlexContainer

import budget

JST = timezone(timedelta(hours=9), "JST")


def _money(value):
    return f"¥{int(value or 0):,}"


def _query_expenses(start_date, end_date):
    return budget._query_all(
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


def _aggregate(pages):
    result = {"total": 0, "categories": {}, "cards": {}, "count": 0}
    for page in pages:
        props = page.get("properties", {})
        amount = props.get("金額", {}).get("number") or 0
        cat_obj = props.get("ジャンル", {}).get("select")
        card_obj = props.get("カード・支払方法", {}).get("select")
        category = cat_obj.get("name") if cat_obj else "未分類"
        card = card_obj.get("name") if card_obj else "未設定"
        result["total"] += amount
        result["count"] += 1
        result["categories"][category] = result["categories"].get(category, 0) + amount
        result["cards"][card] = result["cards"].get(card, 0) + amount
    return result


def _progress_bar(rate, blocks=10):
    rate = max(0, rate)
    filled = min(blocks, int(round(min(rate, 1) * blocks)))
    return "█" * filled + "░" * (blocks - filled)


def get_dashboard_data(month_str=None):
    now = datetime.now(JST)
    month_str = month_str or now.strftime("%Y-%m")
    overview = budget.get_budget_overview(month_str)
    start = f"{month_str}-01"
    end = budget._next_month_first_day(month_str)
    agg = _aggregate(_query_expenses(start, end))

    year, month = map(int, month_str.split("-"))
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    if now.strftime("%Y-%m") == month_str:
        days_left = max(1, (next_month - now.date()).days)
    else:
        days_left = None

    total_budget = overview.get("total_budget")
    remaining = total_budget - agg["total"] if total_budget is not None else None
    per_day = remaining / days_left if remaining is not None and days_left else None

    return {
        "month": month_str,
        "overview": overview,
        "aggregate": agg,
        "total_budget": total_budget,
        "remaining": remaining,
        "days_left": days_left,
        "per_day": per_day,
    }


def create_dashboard_flex(month_str=None):
    data = get_dashboard_data(month_str)
    agg = data["aggregate"]
    budget_value = data["total_budget"]
    expense = agg["total"]

    if budget_value:
        rate = expense / budget_value
        headline = f"残り {_money(data['remaining'])}"
        detail = f"使用 {_money(expense)} / 予算 {_money(budget_value)}"
        progress = f"{_progress_bar(rate)}  {rate * 100:.0f}%"
    else:
        headline = f"支出 {_money(expense)}"
        detail = "全体予算は未設定"
        progress = ""

    body = [
        {"type": "text", "text": headline, "weight": "bold", "size": "xxl", "wrap": True},
        {"type": "text", "text": detail, "size": "sm", "color": "#666666", "margin": "xs", "wrap": True},
    ]
    if progress:
        body.append({"type": "text", "text": progress, "size": "sm", "margin": "md", "wrap": True})

    if data["days_left"] is not None:
        body.append({
            "type": "box", "layout": "vertical", "margin": "lg", "contents": [
                {"type": "text", "text": f"残り {data['days_left']} 日", "weight": "bold", "size": "md"},
                {"type": "text", "text": f"1日あたり使える額: {_money(data['per_day'])}" if data["per_day"] is not None else "1日あたり額は予算設定後に表示", "size": "sm", "color": "#666666", "wrap": True, "margin": "xs"},
            ]
        })

    body += [
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": "支出が多いジャンル", "weight": "bold", "size": "sm", "margin": "lg"},
    ]
    top_categories = sorted(agg["categories"].items(), key=lambda x: x[1], reverse=True)[:5]
    if top_categories:
        for name, value in top_categories:
            body.append({
                "type": "box", "layout": "horizontal", "margin": "sm", "contents": [
                    {"type": "text", "text": name, "size": "sm", "flex": 5, "wrap": True},
                    {"type": "text", "text": _money(value), "size": "sm", "flex": 3, "align": "end"},
                ]
            })
    else:
        body.append({"type": "text", "text": "まだ支出データがありません。", "size": "sm", "color": "#888888", "wrap": True, "margin": "sm"})

    body += [
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": "支払方法別", "weight": "bold", "size": "sm", "margin": "lg"},
    ]
    for name, value in sorted(agg["cards"].items(), key=lambda x: x[1], reverse=True)[:5]:
        body.append({
            "type": "box", "layout": "horizontal", "margin": "sm", "contents": [
                {"type": "text", "text": name, "size": "sm", "flex": 5, "wrap": True},
                {"type": "text", "text": _money(value), "size": "sm", "flex": 3, "align": "end"},
            ]
        })

    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "📊 家計簿ダッシュボード", "weight": "bold", "size": "lg", "wrap": True},
            {"type": "text", "text": data["month"], "size": "sm", "color": "#888888", "margin": "xs"},
        ]},
        "body": {"type": "box", "layout": "vertical", "contents": body},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "button", "style": "primary", "action": {"type": "message", "label": "予算一覧を見る", "text": "予算一覧"}},
            {"type": "button", "style": "secondary", "action": {"type": "message", "label": "週次レポートを見る", "text": "週次レポート"}},
        ]}
    }
    return FlexMessage(alt_text=f"{data['month']} 家計簿ダッシュボード", contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))


def get_budget_alerts(month_str=None):
    overview = budget.get_budget_overview(month_str)
    alerts = []

    def add_alert(name, spent, limit):
        if limit is None or limit <= 0:
            return
        rate = spent / limit
        if rate >= 1:
            level = 100
        elif rate >= 0.9:
            level = 90
        elif rate >= 0.8:
            level = 80
        else:
            return
        alerts.append({"name": name, "spent": spent, "budget": limit, "rate": rate, "level": level})

    add_alert("全体予算", overview["total_expense"], overview["total_budget"])
    for category, values in overview["categories"].items():
        add_alert(category, values.get("expense", 0), values.get("budget"))

    return sorted(alerts, key=lambda x: x["rate"], reverse=True)


def create_budget_alert_flex(month_str=None):
    alerts = get_budget_alerts(month_str)
    month = month_str or datetime.now(JST).strftime("%Y-%m")
    contents = []
    if alerts:
        for item in alerts[:10]:
            remaining = item["budget"] - item["spent"]
            status = "予算超過" if item["rate"] >= 1 else f"{item['level']}%以上"
            contents.append({
                "type": "box", "layout": "vertical", "margin": "md", "contents": [
                    {"type": "text", "text": f"{item['name']}  —  {status}", "weight": "bold", "size": "sm", "wrap": True},
                    {"type": "text", "text": f"使用 {_money(item['spent'])} / 予算 {_money(item['budget'])}", "size": "xs", "color": "#666666", "wrap": True, "margin": "xs"},
                    {"type": "text", "text": f"残り {_money(remaining)}  ({item['rate']*100:.0f}%)", "size": "xs", "color": "#888888", "wrap": True, "margin": "xs"},
                ]
            })
    else:
        contents.append({"type": "text", "text": "現在、80%以上に達している予算はありません。", "size": "sm", "color": "#666666", "wrap": True})

    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🚨 予算アラート", "weight": "bold", "size": "lg"},
            {"type": "text", "text": month, "size": "sm", "color": "#888888", "margin": "xs"},
        ]},
        "body": {"type": "box", "layout": "vertical", "contents": contents},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "button", "style": "primary", "action": {"type": "message", "label": "ダッシュボードを見る", "text": "今月"}}
        ]}
    }
    return FlexMessage(alt_text=f"{month} 予算アラート", contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))


def get_weekly_report_data():
    today = datetime.now(JST).date()
    current_start = today - timedelta(days=6)
    current_end = today + timedelta(days=1)
    previous_start = current_start - timedelta(days=7)
    previous_end = current_start

    current = _aggregate(_query_expenses(current_start.isoformat(), current_end.isoformat()))
    previous = _aggregate(_query_expenses(previous_start.isoformat(), previous_end.isoformat()))
    diff = current["total"] - previous["total"]
    diff_rate = (diff / previous["total"] * 100) if previous["total"] else None
    return {
        "current_start": current_start.isoformat(), "current_end": today.isoformat(),
        "previous_start": previous_start.isoformat(), "previous_end": (previous_end - timedelta(days=1)).isoformat(),
        "current": current, "previous": previous, "diff": diff, "diff_rate": diff_rate,
    }


def create_weekly_report_flex():
    data = get_weekly_report_data()
    current = data["current"]
    previous = data["previous"]
    if data["diff_rate"] is None:
        comparison = "前の7日間に支出データなし"
    else:
        sign = "+" if data["diff_rate"] >= 0 else ""
        comparison = f"前の7日間比 {sign}{data['diff_rate']:.0f}% ({_money(data['diff'])})"

    body = [
        {"type": "text", "text": _money(current["total"]), "weight": "bold", "size": "xxl"},
        {"type": "text", "text": f"{data['current_start']} 〜 {data['current_end']} / {current['count']}件", "size": "xs", "color": "#888888", "wrap": True, "margin": "xs"},
        {"type": "text", "text": comparison, "size": "sm", "color": "#666666", "wrap": True, "margin": "md"},
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": "今週のジャンル上位", "weight": "bold", "size": "sm", "margin": "lg"},
    ]
    for name, value in sorted(current["categories"].items(), key=lambda x: x[1], reverse=True)[:5]:
        body.append({
            "type": "box", "layout": "horizontal", "margin": "sm", "contents": [
                {"type": "text", "text": name, "size": "sm", "flex": 5, "wrap": True},
                {"type": "text", "text": _money(value), "size": "sm", "flex": 3, "align": "end"},
            ]
        })
    if not current["categories"]:
        body.append({"type": "text", "text": "今週の支出データはありません。", "size": "sm", "color": "#888888", "wrap": True})

    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "📅 週次レポート", "weight": "bold", "size": "lg"},
            {"type": "text", "text": "直近7日間", "size": "sm", "color": "#888888", "margin": "xs"},
        ]},
        "body": {"type": "box", "layout": "vertical", "contents": body},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "button", "style": "primary", "action": {"type": "message", "label": "今月のダッシュボード", "text": "今月"}}
        ]}
    }
    return FlexMessage(alt_text="家計簿 週次レポート", contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))
