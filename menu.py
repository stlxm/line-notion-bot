import inspect
import json
from linebot.v3.messaging import FlexMessage, FlexContainer, TextMessage


MENU_ALIASES = {"メニュー", "機能", "機能一覧", "menu", "Menu"}


def _message_button(label, text, style="primary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {"type": "message", "label": label[:20], "text": text},
    }


def _postback_button(label, data, style="primary", display_text=None):
    action = {"type": "postback", "label": label[:20], "data": data}
    action["displayText"] = (display_text or f"▶ {label}")[:300]
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": action,
    }


def _bubble(title, description, buttons, icon=""):
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": f"{icon} {title}".strip(), "weight": "bold", "size": "xl", "wrap": True},
                {"type": "text", "text": description, "size": "sm", "color": "#777777", "margin": "xs", "wrap": True},
            ],
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
    }


def _called_from_unknown_fallback():
    """app.pyの既存フォールバックから呼ばれた場合だけメニューを展開しない。"""
    frame = inspect.currentframe()
    try:
        caller = frame.f_back.f_back if frame and frame.f_back else None
        if not caller or caller.f_code.co_name != "handle_message":
            return False
        user_message = str(caller.f_locals.get("user_message") or "").strip()
        return bool(user_message) and user_message not in MENU_ALIASES
    finally:
        del frame


def create_main_menu_flex():
    if _called_from_unknown_fallback():
        return TextMessage(text="「ヘルプ」か「メニュー」と送ってください。")

    bubbles = [
        _bubble(
            "案内・入口",
            "迷ったとき、機能を探したいとき",
            [
                _message_button("目的から探す", "？"),
                _message_button("この機能ある？", "機能確認"),
                _message_button("今のおすすめ", "おすすめ"),
                _message_button("全コマンド一覧", "コマンド"),
                _message_button("Notionを開く", "Notion", "secondary"),
            ],
            "✨",
        ),
        _bubble(
            "家計簿・入力",
            "支出入力と今日・今月の確認",
            [
                _postback_button("支出を入力", "action=quick_input_kakeibo"),
                _message_button("自然文で支出入力", "自然文入力"),
                _message_button("よく使う支出", "支出テンプレート"),
                _message_button("本日のレポート", "本日のレポート"),
                _message_button("今月の状況", "今月"),
            ],
            "🧾",
        ),
        _bubble(
            "予算・分析",
            "予算、使いすぎ、将来予測",
            [
                _message_button("予算一覧", "予算一覧"),
                _message_button("予算を設定", "予算設定"),
                _message_button("今日使える額", "今日使える"),
                _message_button("支出ペース", "ペース"),
                _message_button("予算提案", "予算提案"),
                _message_button("異常支出", "異常支出"),
                _message_button("年間支出予測", "年間予測"),
                _message_button("週次レポート", "週次レポート"),
            ],
            "📊",
        ),
        _bubble(
            "月次・固定費・貯金",
            "月次処理と定期支出、目標管理",
            [
                _message_button("月締め", "月締め"),
                _message_button("月次レビュー", "月次レビュー"),
                _message_button("固定費一覧", "固定費一覧"),
                _message_button("固定費を追加", "固定費追加"),
                _message_button("固定費を今月登録", "固定費"),
                _message_button("貯金目標", "貯金目標"),
                _message_button("貯金目標を追加", "貯金目標追加"),
                _message_button("貯金額を更新", "貯金更新"),
            ],
            "🎯",
        ),
        _bubble(
            "修正・取り消し",
            "直前の家計簿を安全に直す",
            [
                _message_button("直前登録を確認", "直前登録"),
                _message_button("直前登録を修正", "直前修正"),
                _message_button("直前登録を取り消す", "直前取り消し", "secondary"),
            ],
            "✏️",
        ),
        _bubble(
            "カード",
            "未処理・自動分類・店名の小書き文字補正を学習",
            [
                _message_button("カード未処理", "カード未処理"),
                _message_button("自動登録ルール", "カード自動登録"),
                _message_button("カードテスト", "カードテスト", "secondary"),
            ],
            "💳",
        ),
        _bubble(
            "貸し借り",
            "貸した・借りた・精算を管理",
            [
                _message_button("貸した記録を追加", "貸した"),
                _message_button("借りた記録を追加", "借りた"),
                _message_button("貸し借り一覧", "貸し借り一覧"),
                _message_button("精算する", "精算"),
            ],
            "💸",
        ),
        _bubble(
            "メモ・買い物",
            "期限付きメモと買い物リスト",
            [
                _postback_button("メモを追加", "action=quick_input_memo"),
                _message_button("メモ一覧", "メモ一覧"),
                _message_button("メモを削除", "メモ削除", "secondary"),
                _message_button("買い物を追加", "機能確認 買い物リスト"),
                _message_button("買い物リスト", "買い物リスト"),
                _message_button("購入済みにする", "機能確認 買い物リスト", "secondary"),
            ],
            "📝",
        ),
        _bubble(
            "特売・あとで見る",
            "今日の特売とURL保存",
            [
                _message_button("今日の特売", "特売情報"),
                _message_button("URLを保存", "機能確認 URL保存"),
            ],
            "🛒",
        ),
        _bubble(
            "AI",
            "検索・モデル・評価・改善",
            [
                _message_button("AI検索の使い方", "AI"),
                _message_button("AI Lite", "AI Lite"),
                _message_button("AI Flash", "AI Flash"),
                _message_button("現在のAIモデル", "AI Model"),
                _message_button("👍 直前回答を評価", "AI評価 👍"),
                _message_button("👎 直前回答を評価", "AI評価 👎", "secondary"),
                _message_button("直前回答を改善", "AI改善", "secondary"),
                _message_button("DBヘルスチェック", "DBヘルスチェック"),
            ],
            "🤖",
        ),
        _bubble(
            "Notion・データ",
            "汎用Notion操作",
            [
                _message_button("データを追加", "データ追加"),
                _message_button("Notionを開く", "Notion"),
                _message_button("機能確認", "機能確認"),
                _message_button("全コマンド一覧", "コマンド"),
            ],
            "🗂",
        ),
    ]

    flex_json = {"type": "carousel", "contents": bubbles}
    return FlexMessage(
        alt_text="LINE Notion Bot 全機能メニュー",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )
