import json
from linebot.v3.messaging import FlexMessage, FlexContainer


def _message_button(label, text, style="primary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {"type": "message", "label": label[:20], "text": text},
    }


def _postback_button(label, data, style="primary", display_text=None):
    action = {"type": "postback", "label": label[:20], "data": data}
    # Postbackは通常トーク画面に何も出ないため、押した瞬間に操作が見えるようdisplayTextを付ける。
    action["displayText"] = (display_text or f"▶ {label}")[:300]
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": action,
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
    """現在使える機能を大分類で見やすくまとめる。"""
    body = [{
        "type": "text",
        "text": "使いたい機能を選んでください。迷ったら「目的から探す」か「この機能ある？」を使えます。",
        "size": "sm", "color": "#666666", "wrap": True,
    }]

    body += _section(
        "✨ 迷ったら",
        "目的から探す・機能の有無を確認する・今やることを見る",
        [
            _message_button("目的から探す", "？"),
            _message_button("この機能ある？", "機能確認"),
            _message_button("今のおすすめ", "おすすめ"),
            _message_button("全コマンド一覧", "コマンド", "secondary"),
        ],
        "#1DB446",
    )

    body += _section(
        "📊 家計簿・予算",
        "記録、今月の状況、予算判断、月次レビュー",
        [
            _message_button("今月のダッシュボード", "今月"),
            _postback_button("支出を入力する", "action=quick_input_kakeibo", display_text="▶ 支出を入力する"),
            _message_button("家計判断メニュー", "家計判断"),
            _message_button("今日使える額", "今日使える"),
            _message_button("支出ペースを見る", "ペース"),
            _message_button("月次レビュー", "月次レビュー"),
            _message_button("予算一覧を見る", "予算一覧"),
            _message_button("週次レポートを見る", "週次レポート"),
            _message_button("固定費一覧を見る", "固定費一覧"),
        ],
        "#1DB446",
    )

    body += _section(
        "✏️ 修正・取り消し",
        "直前に登録した家計簿を確認して、安全に修正・取り消しできます",
        [
            _message_button("直前登録を確認・修正", "直前登録"),
            _message_button("直前登録を取り消す", "直前取り消し", "secondary"),
        ],
        "#D97706",
    )

    body += _section(
        "💸 貸し借り",
        "貸した・借りた記録と未精算の確認",
        [
            _message_button("貸し借り一覧", "貸し借り一覧"),
            _message_button("貸し借りの使い方", "機能確認 貸し借り", "secondary"),
        ],
        "#00897B",
    )

    body += _section(
        "💳 カード",
        "未処理、同じ店のまとめ処理、学習・自動登録",
        [
            _message_button("カード未処理を確認", "カード未処理"),
            _message_button("自動分類ルールを見る", "カード自動登録"),
        ],
        "#1DB446",
    )

    body += _section(
        "📝 メモ",
        "追加、一覧、確認付き削除",
        [
            _postback_button("メモを追加する", "action=quick_input_memo", display_text="▶ メモを追加する"),
            _message_button("メモ一覧を見る", "メモ一覧"),
            _message_button("メモを削除する", "メモ削除", "secondary"),
        ],
        "#0288D1",
    )

    body += _section(
        "🤖 AI検索・改善",
        "Lite / Flashを切替可能。明示した質問だけGeminiを使用",
        [
            _message_button("AI検索の使い方", "AI"),
            _message_button("AIモデルを確認", "AI Model"),
            _message_button("直前のAI回答を改善", "AI改善"),
        ],
        "#F57C00",
    )

    body += _section(
        "🗂 Notion・その他",
        "貯金目標、汎用データ登録、Notion",
        [
            _message_button("貯金目標を見る", "貯金目標"),
            _message_button("データを追加する", "データ追加"),
            _message_button("Notionを開く", "Notion"),
        ],
        "#7B1FA2",
    )

    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🏠 LINE Notion Bot", "weight": "bold", "size": "xl", "wrap": True},
            {"type": "text", "text": "機能一覧", "size": "sm", "color": "#888888", "margin": "xs"},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body},
    }
    return FlexMessage(
        alt_text="LINE Notion Bot 機能一覧",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
