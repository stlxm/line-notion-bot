import os
import json
import requests
from datetime import datetime, timezone, timedelta
from linebot.v3.messaging import FlexMessage, FlexContainer

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")
NOTION_MONTHLY_DATABASE_ID = os.environ.get("NOTION_MONTHLY_DATABASE_ID", "")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _current_month_jst():
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m")


def _next_month_first_day(month_str):
    year, month = map(int, month_str.split("-"))
    if month == 12:
        return f"{year + 1}-01-01"
    return f"{year}-{month + 1:02d}-01"


def _query_all(database_id, payload):
    if not database_id:
        return []

    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    results = []
    next_cursor = None

    while True:
        body = dict(payload)
        if next_cursor:
            body["start_cursor"] = next_cursor

        try:
            res = requests.post(url, headers=NOTION_HEADERS, json=body, timeout=10)
        except Exception as e:
            print(f"Notion query error: {e}")
            break

        if res.status_code != 200:
            print(f"Notion query error ({res.status_code}): {res.text}")
            break

        data = res.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break

    return results


def get_budget_overview(month_str=None):
    """指定月の予算・支出・残額を一覧用データとして返します。"""
    month_str = month_str or _current_month_jst()

    overview = {
        "month": month_str,
        "total_budget": None,
        "total_expense": 0,
        "categories": {},
    }

    # 月別管理DBから「全体予算」「○○予算」を取得
    monthly_results = _query_all(
        NOTION_MONTHLY_DATABASE_ID,
        {"filter": {"property": "年月", "title": {"equals": month_str}}},
    )

    if monthly_results:
        props = monthly_results[0].get("properties", {})
        for prop_name, prop in props.items():
            if not prop_name.endswith("予算"):
                continue
            value = prop.get("number")
            if value is None:
                continue

            if prop_name == "全体予算":
                overview["total_budget"] = value
            else:
                category = prop_name[:-2]
                overview["categories"].setdefault(category, {"budget": None, "expense": 0})
                overview["categories"][category]["budget"] = value

    # 家計簿DBから月内の支出を集計
    expense_results = _query_all(
        NOTION_KAKEIBO_DATABASE_ID,
        {
            "filter": {
                "and": [
                    {"property": "日付", "date": {"on_or_after": f"{month_str}-01"}},
                    {"property": "日付", "date": {"before": _next_month_first_day(month_str)}},
                ]
            }
        },
    )

    for page in expense_results:
        props = page.get("properties", {})
        amount = props.get("金額", {}).get("number") or 0
        select_obj = props.get("ジャンル", {}).get("select")
        category = select_obj.get("name") if select_obj else "未分類"

        overview["total_expense"] += amount
        overview["categories"].setdefault(category, {"budget": None, "expense": 0})
        overview["categories"][category]["expense"] += amount

    return overview


def create_budget_overview_flex(month_str=None):
    """今月の予算一覧をLINE Flex Messageで返します。"""
    overview = get_budget_overview(month_str)
    month = overview["month"]
    total_budget = overview["total_budget"]
    total_expense = overview["total_expense"]

    if total_budget is not None:
        remaining = total_budget - total_expense
        total_summary = f"残り ¥{int(remaining):,}"
        total_detail = f"使用 ¥{int(total_expense):,} / 予算 ¥{int(total_budget):,}"
    else:
        total_summary = f"支出 ¥{int(total_expense):,}"
        total_detail = "全体予算は未設定"

    category_rows = []
    categories = overview["categories"]

    # 予算設定済みを優先し、その後に予算未設定のジャンルを表示
    sorted_items = sorted(
        categories.items(),
        key=lambda item: (item[1]["budget"] is None, item[0]),
    )

    for category, values in sorted_items[:12]:
        budget_value = values["budget"]
        expense_value = values["expense"]
        if budget_value is not None:
            remaining_value = budget_value - expense_value
            right_text = f"¥{int(remaining_value):,} 残"
            detail_text = f"¥{int(expense_value):,} / ¥{int(budget_value):,}"
        else:
            right_text = f"¥{int(expense_value):,}"
            detail_text = "予算未設定"

        category_rows.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": category, "size": "sm", "weight": "bold", "flex": 5, "wrap": True},
                        {"type": "text", "text": right_text, "size": "sm", "align": "end", "flex": 3},
                    ],
                },
                {"type": "text", "text": detail_text, "size": "xs", "color": "#888888", "margin": "xs"},
            ],
        })

    if not category_rows:
        category_rows.append({
            "type": "text",
            "text": "ジャンル別の予算・支出データはまだありません。",
            "size": "sm",
            "color": "#888888",
            "wrap": True,
            "margin": "md",
        })

    flex_json = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "💰 予算一覧", "weight": "bold", "size": "md", "color": "#1DB446"},
                {"type": "text", "text": month, "size": "sm", "color": "#888888", "margin": "xs"},
                {"type": "text", "text": total_summary, "weight": "bold", "size": "xxl", "margin": "md"},
                {"type": "text", "text": total_detail, "size": "xs", "color": "#666666", "margin": "xs"},
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "ジャンル別", "weight": "bold", "size": "sm"},
                {"type": "separator", "margin": "md"},
                *category_rows,
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {"type": "message", "label": "予算を設定する", "text": "予算設定"},
                }
            ],
        },
    }

    return FlexMessage(
        alt_text=f"{month} の予算一覧",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
