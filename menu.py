import json
from linebot.v3.messaging import FlexMessage, FlexContainer


def _message_button(label, text, style="primary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {"type": "message", "label": label[:20], "text": text},
    }


def _postback_button(label, data, style="primary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {"type": "postback", "label": label[:20], "data": data},
    }


def _section(title, description, buttons, color):
    contents = [
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": title, "weight": "bold", "size": "md", "color": color, "margin": "lg", "wrap": True},
        {"type": "text", "text": description, "size": "xs", "color": "#888888", "margin": "xs", "wrap": True},
    ]
    contents.extend(buttons)
    return contents


def create_main_menu_flex():
    """主要機能を1枚・1列で表示します。

    通常の前向きな操作は primary（緑）、キャンセル・削除など
    ネガティブ/低頻度な操作だけ secondary にします。
    """
    body = [
        {
            "type": "text",
            "text": "使いたい機能を選んでください。AIは「AI 質問内容」と送ったときだけ呼び出します。",
            "size": "sm",
            "color": "#666666",
            "wrap": True,
        },
    ]

    body += _section(
        "📊 家計簿・予算",
        "記録、今月の状況、予算、定期レポート",
        [
            _message_button("今月のダッシュボード", "今月"),
            _postback_button("支出を入力する", "action=quick_input_kakeibo"),
            _message_button("カード未処理を確認", "カード未処理"),
            _message_button("予算一覧を見る", "予算一覧"),
            _message_button("予算アラートを見る", "予算アラート"),
            _message_button("週次レポートを見る", "週次レポート"),
            _message_button("予算を設定する", "予算設定"),
            _message_button("固定費一覧を見る", "固定費一覧"),
            _message_button("固定費を一括登録", "固定費"),
            _message_button("固定費を追加する", "固定費追加"),
        ],
        "#1DB446",
    )

    body += _section(
        "📝 メモ",
        "追加、一覧、確認付き削除",
        [
            _postback_button("メモを追加する", "action=quick_input_memo"),
            _message_button("メモ一覧を見る", "メモ一覧"),
            _message_button("メモを削除する", "メモ削除", "secondary"),
        ],
        "#0288D1",
    )

    body += _section(
        "🤖 AI検索・改善",
        "明示した質問だけGeminiを使用。変な回答は改善ログへ残せます",
        [
            _message_button("AI検索の使い方", "AI"),
            _message_button("直前のAI回答を改善", "AI改善"),
        ],
        "#F57C00",
    )

    body += _section(
        "🗂 Notion・その他",
        "汎用データ登録、Notion、ヘルプ",
        [
            _message_button("データを追加する", "データ追加"),
            _message_button("Notionを開く", "Notion"),
            _message_button("使い方を見る", "ヘルプ"),
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
                {"type": "text", "text": "🏠 LINE Notion Bot", "weight": "bold", "size": "xl", "wrap": True},
                {"type": "text", "text": "機能一覧", "size": "sm", "color": "#888888", "margin": "xs"},
            ],
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body},
    }
    return FlexMessage(
        alt_text="LINE Notion Bot 機能一覧",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
