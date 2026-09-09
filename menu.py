import json
from linebot.v3.messaging import FlexMessage, FlexContainer

def create_main_menu_flex():
    """LINEで「メニュー」と送られたときに返すカード型UI（カルーセル）を作成します"""
    flex_json = {
        "type": "carousel",
        "contents": [
            # 1枚目: 家計簿カード
            {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "💳 家計簿機能", "weight": "bold", "color": "#1DB446", "size": "md"},
                        {"type": "text", "text": "支出記録・予算確認", "size": "xs", "color": "#aaaaaa", "margin": "xs"}
                    ]
                },
                "body": {
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
                                "label": "支出を入力",
                                "data": "action=quick_input_kakeibo"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "固定費一括登録",
                                "text": "固定費"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "固定費一覧確認",
                                "text": "固定費一覧"
                            }
                        }
                    ]
                }
            },
            # 2枚目: メモカード
            {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "📝 メモ機能", "weight": "bold", "color": "#0288D1", "size": "md"},
                        {"type": "text", "text": "アイデアや買い物の記録", "size": "xs", "color": "#aaaaaa", "margin": "xs"}
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "メモ一覧を見る",
                                "text": "メモ一覧"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "メモを削除する",
                                "text": "メモ削除"
                            }
                        }
                    ]
                }
            },
            # 3枚目: その他・データ追加カード
            {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "⚙️ 共通・設定機能", "weight": "bold", "color": "#7B1FA2", "size": "md"},
                        {"type": "text", "text": "Notion連携・データ登録", "size": "xs", "color": "#aaaaaa", "margin": "xs"}
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "汎用データ追加",
                                "text": "データ追加"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "Notionリンク表示",
                                "text": "Notion"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "使い方ヘルプ",
                                "text": "ヘルプ"
                            }
                        }
                    ]
                }
            }
        ]
    }
    return FlexMessage(alt_text="機能選択メニュー", contents=FlexContainer.from_json(json.dumps(flex_json)))
