import os
import json
import requests
from datetime import datetime
from linebot.v3.messaging import FlexMessage, FlexContainer

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")
NOTION_MONTHLY_DATABASE_ID = os.environ.get("NOTION_MONTHLY_DATABASE_ID", "")
NOTION_FIXED_DATABASE_ID = os.environ.get("NOTION_FIXED_DATABASE_ID", "")

# LINEのジャンルボタンから除外するプロパティ名
EXCLUDED_GENRES = ["固定費", "サブスク"]


def get_notion_select_options(database_id, prop_name, exclude_list=None):
    if not database_id:
        return []
    url = f"https://api.notion.com/v1/databases/{database_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            props = res.json().get("properties", {})
            target_prop = props.get(prop_name, {})
            if target_prop.get("type") == "select":
                options = target_prop.get("select", {}).get("options", [])
                names = [opt.get("name") for opt in options if opt.get("name")]
                if exclude_list:
                    names = [n for n in names if n not in exclude_list]
                return names
    except Exception as e:
        print(f"Notion選択肢取得エラー ({prop_name}): {e}")
    return []


def create_button_grid_flex(title, options, callback_action, include_cancel=False):
    buttons = []
    for opt in options:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": opt[:20],
                "data": f"action={callback_action}&val={opt}"
            }
        })
    if include_cancel:
        buttons.append({
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "登録しない",
                "data": "action=cancel_registration"
            }
        })

    rows = []
    for i in range(0, len(buttons), 2):
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": buttons[i:i+2]
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
            "contents": rows
        }
    }
    return FlexMessage(alt_text=title, contents=FlexContainer.from_json(json.dumps(flex_json)))


def create_card_notify_action_flex(card_name, store_name, amount, date_str):
    """カード利用検知時：そのままジャンル選択へ進むか、店名を変更するかを選択するメッセージ"""
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
                {"type": "text", "text": "店名を変更しますか？", "size": "xs", "color": "#888888", "margin": "lg", "align": "center"}
            ]
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
                    "action": {
                        "type": "postback",
                        "label": "そのままジャンル選択へ",
                        "data": f"action=card_select_cat&card={card_name}&store={store_name}&amount={amount}&date={date_str}"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "店名を変更する",
                        "data": f"action=card_change_store_start&card={card_name}&store={store_name}&amount={amount}&date={date_str}"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "登録しない",
                        "data": "action=cancel_registration"
                    }
                }
            ]
        }
    }
    return FlexMessage(alt_text=f"カード利用: {store_name} ¥{amount}", contents=FlexContainer.from_json(json.dumps(flex_json)))


def create_card_notify_flex(card_name, store_name, amount, date_str):
    """ジャンル選択ボタン画面を表示するメッセージ"""
    categories = get_notion_select_options(NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=EXCLUDED_GENRES)
    if not categories:
        categories = ["食費", "日用品", "交通費", "娯楽"]

    buttons = []
    for cat in categories:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": cat[:20],
                "data": f"action=kakeibo_save&card={card_name}&store={store_name}&amount={amount}&date={date_str}&cat={cat}"
            }
        })

    buttons.append({
        "type": "button",
        "style": "secondary",
        "height": "sm",
        "action": {
            "type": "postback",
            "label": "登録しない",
            "data": "action=cancel_registration"
        }
    })

    rows = []
    for i in range(0, len(buttons), 2):
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": buttons[i:i+2]
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
            "contents": rows
        }
    }
    return FlexMessage(alt_text=f"カード利用: {store_name} ¥{amount}", contents=FlexContainer.from_json(json.dumps(flex_json)))


def get_or_create_monthly_page(date_str):
    if not NOTION_MONTHLY_DATABASE_ID:
        return None
    month_str = date_str[:7]
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    query_url = f"https://api.notion.com/v1/databases/{NOTION_MONTHLY_DATABASE_ID}/query"
    payload = {"filter": {"property": "年月", "title": {"equals": month_str}}}

    res = requests.post(query_url, headers=headers, json=payload)
    if res.status_code == 200:
        results = res.json().get("results", [])
        if results:
            return results[0]["id"]

    create_url = "https://api.notion.com/v1/pages"
    create_payload = {
        "parent": {"database_id": NOTION_MONTHLY_DATABASE_ID},
        "properties": {"年月": {"title": [{"text": {"content": month_str}}]}}
    }
    res_create = requests.post(create_url, headers=headers, json=create_payload)
    if res_create.status_code == 200:
        return res_create.json().get("id")
    return None


def set_budget_in_notion(month_str, budget_amount, category=None):
    monthly_page_id = get_or_create_monthly_page(f"{month_str}-01")
    if not monthly_page_id:
        return False

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    prop_name = f"{category}予算" if category else "全体予算"
    update_url = f"https://api.notion.com/v1/pages/{monthly_page_id}"
    payload = {"properties": {prop_name: {"number": float(budget_amount)}}}
    res = requests.patch(update_url, headers=headers, json=payload)
    return res.status_code == 200


def get_next_month_first_day(month_str):
    year, month = map(int, month_str.split("-"))
    if month == 12:
        return f"{year + 1}-01-01"
    else:
        return f"{year}-{month + 1:02d}-01"


def get_budget_status(date_str, current_category):
    month_str = date_str[:7]
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    monthly_page_id = get_or_create_monthly_page(date_str)
    total_budget = None
    category_budget = None

    if monthly_page_id:
        page_url = f"https://api.notion.com/v1/pages/{monthly_page_id}"
        res = requests.get(page_url, headers=headers)
        if res.status_code == 200:
            props = res.json().get("properties", {})
            if "全体予算" in props and props["全体予算"].get("number") is not None:
                total_budget = props["全体予算"]["number"]
            cat_prop_name = f"{current_category}予算"
            if cat_prop_name in props and props[cat_prop_name].get("number") is not None:
                category_budget = props[cat_prop_name]["number"]

    kakeibo_url = f"https://api.notion.com/v1/databases/{NOTION_KAKEIBO_DATABASE_ID}/query"
    query_payload = {
        "filter": {
            "and": [
                {"property": "日付", "date": {"on_or_after": f"{month_str}-01"}},
                {"property": "日付", "date": {"before": get_next_month_first_day(month_str)}}
            ]
        }
    }
    res_kakeibo = requests.post(kakeibo_url, headers=headers, json=query_payload)

    total_expense = 0
    category_expense = 0
    if res_kakeibo.status_code == 200:
        results = res_kakeibo.json().get("results", [])
        for page in results:
            p = page.get("properties", {})
            amt = p.get("金額", {}).get("number") or 0
            cat = p.get("ジャンル", {}).get("select", {})
            cat_name = cat.get("name") if cat else ""

            total_expense += amt
            if cat_name == current_category:
                category_expense += amt

    msg_lines = []
    if total_budget is not None:
        rem_total = total_budget - total_expense
        msg_lines.append(f"今月の全体予算残り: ¥{int(rem_total):,} (使用額: ¥{int(total_expense):,} / 予算: ¥{int(total_budget):,})")
    else:
        msg_lines.append(f"今月の全体支出合計: ¥{int(total_expense):,} (全体予算: なし)")

    if category_budget is not None:
        rem_cat = category_budget - category_expense
        msg_lines.append(f"{current_category} の予算残り: ¥{int(rem_cat):,} (使用額: ¥{int(category_expense):,} / 予算: ¥{int(category_budget):,})")
    else:
        msg_lines.append(f"{current_category} の今月合計: ¥{int(category_expense):,} (ジャンル予算: なし)")

    return "\n".join(msg_lines)


def save_kakeibo_to_notion(card_name, store_name, amount, date_str, category):
    if not NOTION_KAKEIBO_DATABASE_ID:
        return "家計簿DB IDが設定されていません。"

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties = {
        "内容・店名": {"title": [{"text": {"content": store_name}}]},
        "金額": {"number": float(amount)},
        "日付": {"date": {"start": date_str}},
        "ジャンル": {"select": {"name": category}},
        "カード・支払方法": {"select": {"name": card_name}}
    }

    monthly_page_id = get_or_create_monthly_page(date_str)
    if monthly_page_id:
        properties["月別管理"] = {"relation": [{"id": monthly_page_id}]}

    payload = {
        "parent": {"database_id": NOTION_KAKEIBO_DATABASE_ID},
        "properties": properties
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            budget_msg = get_budget_status(date_str, category)
            return (
                f"家計簿に記録しました！\n\n"
                f"【店名】{store_name}\n"
                f"【金額】¥{int(float(amount)):,}\n"
                f"【ジャンル】{category}\n"
                f"【支払方法】{card_name}\n"
                f"【日付】{date_str}\n\n"
                f"{budget_msg}"
            )
        else:
            print(f"Notion家計簿保存エラー ({res.status_code}): {res.text}")
            return f"家計簿の保存に失敗しました (エラーコード: {res.status_code})"
    except Exception as e:
        print(f"家計簿保存通信エラー: {e}")
        return f"エラーが発生しました: {str(e)}"


def get_fixed_expenses_from_notion():
    if not NOTION_FIXED_DATABASE_ID:
        return []
    url = f"https://api.notion.com/v1/databases/{NOTION_FIXED_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {"filter": {"property": "有効", "checkbox": {"equals": True}}}
    res = requests.post(url, headers=headers, json=payload)
    fixed_list = []

    if res.status_code == 200:
        results = res.json().get("results", [])
        for page in results:
            props = page.get("properties", {})
            title_list = props.get("内容・店名", {}).get("title", [])
            store_name = title_list[0]["text"]["content"] if title_list else "固定費"
            amount = props.get("金額", {}).get("number") or 0

            cat_obj = props.get("ジャンル", {}).get("select")
            category = cat_obj.get("name") if cat_obj else "固定費"

            card_obj = props.get("カード・支払方法", {}).get("select")
            card_name = card_obj.get("name") if card_obj else "現金"

            fixed_list.append({
                "store_name": store_name,
                "amount": amount,
                "category": category,
                "card_name": card_name
            })
    return fixed_list


def register_monthly_fixed_expenses():
    today_month = datetime.now().strftime("%Y-%m")
    target_date = f"{today_month}-01"
    fixed_items = get_fixed_expenses_from_notion()
    if not fixed_items:
        return 0, 0

    success_count = 0
    total_amount = 0
    for item in fixed_items:
        res = save_kakeibo_to_notion(
            card_name=item["card_name"],
            store_name=item["store_name"],
            amount=item["amount"],
            date_str=target_date,
            category=item["category"]
        )
        if "家計簿に記録しました" in res:
            success_count += 1
            total_amount += item["amount"]

    return success_count, total_amount


def add_fixed_expense_to_notion(store_name, amount, category="固定費", card_name="現金"):
    """Notionの固定費マスタDBへ新しい固定費を1件追加します"""
    if not NOTION_FIXED_DATABASE_ID:
        return False

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": NOTION_FIXED_DATABASE_ID},
        "properties": {
            "内容・店名": {"title": [{"text": {"content": store_name}}]},
            "金額": {"number": float(amount)},
            "ジャンル": {"select": {"name": category}},
            "カード・支払方法": {"select": {"name": card_name}},
            "有効": {"checkbox": True}
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"固定費マスタ追加エラー: {e}")
        return False
