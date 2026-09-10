import json
from urllib.parse import urlencode

from linebot.v3.messaging import FlexMessage, FlexContainer


def create_choice_flex(title, options, callback_action, extra_params=None, include_cancel=False):
    """長い日本語ラベルが見切れにくい1列・全幅の選択UI。

    通常の選択肢は primary（緑）、キャンセルだけ secondary にします。
    """
    extra_params = extra_params or {}
    buttons = []

    for option in options:
        params = {"action": callback_action, "val": option, **extra_params}
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": str(option)[:20],
                "data": urlencode(params),
            },
        })

    if include_cancel:
        buttons.append({
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "キャンセル",
                "data": "action=cancel_registration",
            },
        })

    flex_json = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True},
                {"type": "text", "text": "通常操作は緑、キャンセルのみ控えめに表示します。", "size": "xs", "color": "#888888", "margin": "xs", "wrap": True},
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons or [
                {"type": "text", "text": "選択肢がありません。", "size": "sm", "color": "#888888"}
            ],
        },
    }

    return FlexMessage(
        alt_text=title,
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )


def create_card_category_flex(card, store, amount, date_str, categories, pending_id=None):
    """カード利用のジャンル選択UI。

    ジャンルは2列表示。未処理キューのボタンはLINEのPostback data
    300文字制限を超えないよう、pending_idと必要最小限の値だけ送ります。
    実データはPostback受信後にNotionキューから再取得します。
    """
    category_buttons = []
    for category in categories:
        if pending_id:
            params = {
                "action": "kakeibo_save",
                "pending_id": pending_id,
                "cat": category,
            }
        else:
            params = {
                "action": "kakeibo_save",
                "card": card,
                "store": store,
                "amount": amount,
                "date": date_str,
                "cat": category,
            }

        category_buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "flex": 1,
            "action": {
                "type": "postback",
                "label": str(category)[:10],
                "data": urlencode(params),
            },
        })

    rows = []
    for i in range(0, len(category_buttons), 2):
        row_buttons = category_buttons[i:i + 2]
        if len(row_buttons) == 1:
            row_buttons.append({"type": "box", "layout": "vertical", "flex": 1, "contents": []})
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row_buttons,
        })

    action_buttons = []
    if pending_id:
        action_buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "店名を変更する",
                "data": urlencode({
                    "action": "card_change_store_start",
                    "pending_id": pending_id,
                }),
            },
        })

    skip_data = "action=cancel_registration"
    if pending_id:
        skip_data = urlencode({"action": "skip_card_pending", "pending_id": pending_id})

    action_buttons.append({
        "type": "button",
        "style": "secondary",
        "height": "sm",
        "action": {"type": "postback", "label": "登録しない", "data": skip_data},
    })

    footer_contents = rows
    if rows and action_buttons:
        footer_contents = rows + [{"type": "separator", "margin": "md"}] + action_buttons
    else:
        footer_contents = rows + action_buttons

    flex_json = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "💳 カード利用検知", "weight": "bold", "size": "sm", "color": "#1DB446"},
                {"type": "text", "text": f"¥{int(float(amount)):,}", "weight": "bold", "size": "xxl", "margin": "md"},
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "利用先", "size": "xs", "color": "#aaaaaa"},
                {"type": "text", "text": store, "weight": "bold", "size": "md", "wrap": True, "margin": "xs"},
                {"type": "text", "text": f"カード: {card}", "size": "sm", "color": "#666666", "wrap": True, "margin": "md"},
                {"type": "text", "text": f"利用日: {date_str}", "size": "sm", "color": "#666666", "wrap": True, "margin": "xs"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "ジャンルを選択してください", "size": "sm", "weight": "bold", "margin": "lg", "wrap": True},
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": footer_contents,
        },
    }
    return FlexMessage(
        alt_text=f"カード利用: {store} ¥{amount}",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
