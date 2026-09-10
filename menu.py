import json
from linebot.v3.messaging import FlexMessage, FlexContainer


def _button(label, text, style="secondary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {
            "type": "message",
            "label": label,
            "text": text,
        },
    }


def _postback_button(label, data, style="secondary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {
            "type": "postback",
            "label": label,
            "data": data,
        },
    }


def _section(title, buttons, color="#666666"):
    rows = []
    for i in range(0, len(buttons), 2):
        row_buttons = buttons[i:i + 2]
        if len(row_buttons) == 1:
            row_buttons.append({"type": "filler"})
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row_buttons,
        })

    return [
        {"type": "text", "text": title, "weight": "bold", "size": "sm", "color": color, "margin": "lg"},
        *rows,
    ]


def create_main_menu_flex():
    """主要機能を1枚で見渡せるLINEメニューを作成します。"""
    body_contents = [
        {
            "type": "text",
            "text": "使いたい機能を選んでください",
            "size": "sm",
            "color": "#777777",
            "wrap": True,
        },
    ]

    body_contents += _section(
        "💳 家計簿・予算",
        [
            _postback_button("支出を入力", "action=quick_input_kakeibo", "primary"),
            _button("予算一覧", "予算一覧", "primary"),
            _button("予算を設定", "予算設定"),
            _button("固定費一覧", "固定費一覧"),
            _button("固定費を一括登録", "固定費"),
            _button("固定費を追加", "固定費追加"),
        ],
        "#1DB446",
    )

    body_contents += _section(
        "📝 メモ",
        [
            _postback_button("メモを追加", "action=quick_input_memo", "primary"),
            _button("メモ一覧", "メモ一覧", "primary"),
            _button("メモ削除", "メモ削除"),
        ],
        "#0288D1",
    )

    body_contents += _section(
        "🗂 Notion・その他",
        [
            _button("データ追加", "データ追加"),
            _button("Notionを開く", "Notion"),
            _button("ヘルプ", "ヘルプ"),
        ],
        "#7B1FA2",
    )

    flex_json = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🏠 LINE Notion Bot", "weight": "bold", "size": "xl"},
                {"type": "text", "text": "機能一覧", "size": "sm", "color": "#888888", "margin": "xs"},
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
    }

    return FlexMessage(
        alt_text="LINE Notion Bot 機能一覧",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
