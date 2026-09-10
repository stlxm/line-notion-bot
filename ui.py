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
                {"type": "text", "text": "選択肢は1列表示です。通常操作は緑、キャンセルのみ控えめに表示します。", "size": "xs", "color": "#888888", "margin": "xs", "wrap": True},
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
    buttons = []
    for category in categories:
        params = {
            "action": "kakeibo_save",
            "card": card,
            "store": store,
            "amount": amount,
            "date": date_str,
            "cat": category,
        }
        if pending_id:
            params["pending_id"] = pending_id
        data = urlencode(params)
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {"type": "postback", "label": category[:20], "data": data},
        })

    skip_data = "action=cancel_registration"
    if pending_id:
        skip_data = urlencode({"action": "skip_card_pending", "pending_id": pending_id})

    buttons.append({
        "type": "button",
        "style": "secondary",
        "height": "sm",
        "action": {"type": "postback", "label": "登録しない", "data": skip_data},
    })

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
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "ジャンルを選択してください", "size": "sm", "weight": "bold", "margin": "lg", "wrap": True},
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons,
        },
    }
    return FlexMessage(
        alt_text=f"カード利用: {store} ¥{amount}",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
