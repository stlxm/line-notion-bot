import json
from datetime import datetime, timezone, timedelta

from linebot.v3.messaging import FlexMessage, FlexContainer

import budget
import card_queue
import finance_phase2
import memo

JST = timezone(timedelta(hours=9), "JST")


PURPOSES = [
    ("💰 お金を確認したい", "help_money"),
    ("📝 記録したい", "help_record"),
    ("💳 カードを整理したい", "help_card"),
    ("🎯 予算・目標を考えたい", "help_plan"),
    ("🤖 AIに聞きたい", "help_ai"),
    ("⚙️ その他", "help_other"),
]


def _message_button(label, text, style="primary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {"type": "message", "label": label[:20], "text": text},
    }


def create_goal_help_flex():
    buttons = [_message_button(label, f"ヘルプ {key}") for label, key in PURPOSES]
    flex_json = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "❓ 何をしたいですか？", "weight": "bold", "size": "xl"},
                {"type": "text", "text": "目的から使える機能を案内します。", "size": "sm", "color": "#777777", "margin": "xs"},
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons + [
                {"type": "separator", "margin": "md"},
                _message_button("今のおすすめを見る", "おすすめ"),
                _message_button("全コマンドを見る", "コマンド", "secondary"),
            ],
        },
    }
    return FlexMessage(
        alt_text="目的から機能を探す",
        contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)),
    )


def purpose_help_text(key):
    mapping = {
        "help_money": (
            "【お金を確認したい】\n"
            "・今月いくら使った？ → 今月\n"
            "・今日あといくら使える？ → 今日使える\n"
            "・使いすぎていない？ → ペース\n"
            "・変な支出がない？ → 異常支出\n"
            "・今年いくら使いそう？ → 年間予測\n"
            "・今週の状況を見たい → 週次レポート"
        ),
        "help_record": (
            "【記録したい】\n"
            "・支出を登録 → 支出 1200 ラーメン\n"
            "・メモを保存 → メモ 牛乳を買う\n"
            "・URLを保存 → URLをそのまま送信\n"
            "・固定費を追加 → 固定費追加 Netflix 1490 サブスク JCB\n"
            "・Notionの任意DBへ追加 → データ追加"
        ),
        "help_card": (
            "【カードを整理したい】\n"
            "・未処理を確認 → カード未処理\n"
            "・自動分類ルール確認 → カード自動登録\n"
            "・テスト用カードを作る → カードテスト\n"
            "・同じ店をまとめて処理 → カード未処理から選択\n"
            "・サブスク化 → カード分類で サブスク を選択"
        ),
        "help_plan": (
            "【予算・目標を考えたい】\n"
            "・予算を見る → 予算一覧\n"
            "・予算を設定 → 予算設定\n"
            "・次の予算目安 → 予算提案\n"
            "・月を締める → 月締め\n"
            "・月をAIで振り返る → 月次レビュー\n"
            "・貯金目標を見る → 貯金目標\n"
            "・旅行などの目標追加 → 貯金目標追加 旅行 300000 50000 2027-03-31"
        ),
        "help_ai": (
            "【AIに聞きたい】\n"
            "・Notion/家計簿を質問 → AI 質問内容\n"
            "・軽量モデルへ → AI Lite\n"
            "・高性能モデルへ → AI Flash\n"
            "・今のモデル確認 → AI Model\n"
            "・回答を改善ログへ → AI改善"
        ),
        "help_other": (
            "【その他】\n"
            "・メモ一覧 → メモ一覧\n"
            "・メモ削除 → メモ削除\n"
            "・固定費一覧 → 固定費一覧\n"
            "・Notionを開く → Notion\n"
            "・機能一覧 → メニュー\n"
            "・全コマンド一覧 → コマンド"
        ),
    }
    return mapping.get(key)


def command_list_text():
    return (
        "【コマンド一覧】\n"
        "家計: 今月 / 今日使える / ペース / 予算一覧 / 予算設定 / 予算提案 / 異常支出 / 年間予測 / 月締め / 月次レビュー / 週次レポート\n\n"
        "カード: カード未処理 / カード自動登録 / カードテスト\n\n"
        "記録: 支出 金額 店名 / メモ 内容 / メモ一覧 / メモ削除 / 固定費一覧 / 固定費追加 / データ追加\n\n"
        "目標: 貯金目標 / 貯金目標追加 / 貯金更新\n\n"
        "AI: AI 質問 / AI Lite / AI Flash / AI Model / AI改善\n\n"
        "案内: ？ / おすすめ / 何したい ○○ / メニュー"
    )


def suggest_for_intent(text):
    query = (text or "").strip().lower()
    if not query:
        return "「何したい 節約したい」のように送ってください。"

    groups = [
        (["節約", "使いすぎ", "お金を減らしたい", "出費"], [
            ("ペース", "今月の支出ペースを確認"),
            ("今日使える", "今日使える上限の目安を確認"),
            ("異常支出", "大きく外れた支出候補を確認"),
            ("予算提案", "次回予算の目安を見る"),
        ]),
        (["旅行", "貯金", "目標", "ためたい", "貯めたい"], [
            ("貯金目標", "目標と進捗を確認"),
            ("年間予測", "現在ペースの年間支出を確認"),
            ("予算提案", "予算の目安を作る"),
        ]),
        (["カード", "クレカ", "明細", "未処理"], [
            ("カード未処理", "未分類カードを整理"),
            ("カード自動登録", "自動分類ルールを確認"),
        ]),
        (["メモ", "忘れ", "todo", "やること"], [
            ("メモ 内容", "新しいメモを保存"),
            ("メモ一覧", "保存中のメモを確認"),
        ]),
        (["予算", "月末", "振り返", "レビュー"], [
            ("予算一覧", "今月の予算状況を確認"),
            ("予算提案", "次回予算の候補を確認"),
            ("月次レビュー", "今月をAIで振り返る"),
            ("月締め", "前月を締める前に確認"),
        ]),
        (["ai", "分析", "質問", "聞きたい"], [
            ("AI 質問内容", "Notionや家計簿の内容をAIに質問"),
            ("AI Model", "使用中モデルを確認"),
        ]),
    ]

    for keywords, items in groups:
        if any(keyword in query for keyword in keywords):
            lines = [f"【『{text}』ならおすすめ】"]
            for idx, (command, reason) in enumerate(items[:4], start=1):
                lines.append(f"{idx}. {command}\n   {reason}")
            return "\n".join(lines)

    return (
        f"【『{text}』に近い機能】\n"
        "うまく絞れませんでした。\n"
        "「？」で目的別に探すか、「コマンド」で一覧を確認できます。"
    )


def build_smart_recommendations():
    """現在の状態を軽く確認し、優先度の高い操作を最大3件返す。"""
    candidates = []

    try:
        pending = card_queue.get_pending_count()
        if pending > 0:
            candidates.append((100, "カード未処理", f"カード未処理が {pending} 件あります"))
    except Exception:
        pass

    try:
        summary = finance_phase2.get_month_summary()
        if summary.get("total_budget") is None:
            candidates.append((90, "予算設定", "今月の全体予算が未設定です"))
        else:
            pace = summary.get("pace_ratio")
            if pace is not None and pace >= 1.05:
                candidates.append((85, "ペース", "今月の支出ペースが予算より速めです"))
            if summary.get("remaining_days", 99) <= 7:
                candidates.append((65, "今日使える", "月末が近いので残り予算を確認できます"))
    except Exception:
        pass

    try:
        anomalies = finance_phase2.get_anomalies()
        if anomalies:
            candidates.append((80, "異常支出", f"大きく外れた支出候補が {len(anomalies)} 件あります"))
    except Exception:
        pass

    try:
        memos = memo.get_memos_from_notion()
        if memos:
            candidates.append((45, "メモ一覧", f"保存中のメモが {len(memos)} 件あります"))
    except Exception:
        pass

    now = datetime.now(JST)
    if now.day <= 5:
        candidates.append((40, "予算提案", "月初なので今月・次回の予算目安を確認できます"))

    if not candidates:
        candidates = [
            (30, "今月", "今月の家計状況を確認"),
            (20, "今日使える", "今日使える金額の目安を確認"),
            (10, "メモ一覧", "忘れているメモがないか確認"),
        ]

    # 同じコマンドは1つにまとめる
    seen = set()
    selected = []
    for _, command, reason in sorted(candidates, key=lambda x: x[0], reverse=True):
        if command in seen:
            continue
        selected.append((command, reason))
        seen.add(command)
        if len(selected) >= 3:
            break

    lines = ["【今のおすすめ】"]
    for idx, (command, reason) in enumerate(selected, start=1):
        lines.append(f"{idx}. {command}\n   {reason}")
    lines.append("\nそのままコマンド名を送れば実行できます。")
    return "\n".join(lines)
