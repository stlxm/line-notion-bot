import json
import os
import re
from datetime import datetime, timezone, timedelta
from statistics import median

import requests
from linebot.v3.messaging import FlexMessage, FlexContainer

import card_queue
import finance_phase2
import kakeibo

JST = timezone(timedelta(hours=9), "JST")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_MONTHLY_DATABASE_ID = os.environ.get("NOTION_MONTHLY_DATABASE_ID", "")
NOTION_KAKEIBO_DATABASE_ID = os.environ.get("NOTION_KAKEIBO_DATABASE_ID", "")

# Personal bot向けの短時間の入力途中データ。Render再起動時は消えるが、
# まだNotionへ保存していない確認前データだけなのでデータ破損は起きない。
_pending_natural = None


def _money(value):
    return f"¥{int(round(float(value or 0))):,}"


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _message_button(label, text, style="primary"):
    return {
        "type": "button",
        "style": style,
        "height": "sm",
        "action": {"type": "message", "label": label[:20], "text": text[:300]},
    }


def _flex(title, body_lines, buttons=None, alt_text=None):
    contents = [
        {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True}
    ]
    for line in body_lines:
        contents.append({
            "type": "text", "text": str(line), "size": "sm", "wrap": True,
            "color": "#666666", "margin": "sm",
        })
    data = {
        "type": "bubble",
        "size": "mega",
        "body": {"type": "box", "layout": "vertical", "contents": contents},
    }
    if buttons:
        data["footer"] = {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons}
    return FlexMessage(
        alt_text=alt_text or title,
        contents=FlexContainer.from_json(json.dumps(data, ensure_ascii=False)),
    )


def _available_categories():
    return kakeibo.get_notion_select_options(
        NOTION_KAKEIBO_DATABASE_ID, "ジャンル", exclude_list=kakeibo.EXCLUDED_GENRES
    ) or ["食費", "日用品", "交通費", "娯楽", "お菓子", "サブスク"]


def _available_cards():
    return kakeibo.get_notion_select_options(
        NOTION_KAKEIBO_DATABASE_ID, "カード・支払方法"
    ) or ["現金", "JCB", "三井住友カード", "PayPay", "楽天カード"]


def _extract_amount(text):
    match = re.search(r"(?:[¥￥]\s*)?([0-9][0-9,]*)\s*円", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_date(text):
    today = datetime.now(JST).date()
    if "一昨日" in text:
        return (today - timedelta(days=2)).isoformat()
    if "昨日" in text:
        return (today - timedelta(days=1)).isoformat()
    if "今日" in text or "本日" in text:
        return today.isoformat()

    match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", text)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date().isoformat()
        except ValueError:
            pass

    match = re.search(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", text)
    if match:
        year = int(match.group(1)) if match.group(1) else today.year
        try:
            return datetime(year, int(match.group(2)), int(match.group(3))).date().isoformat()
        except ValueError:
            pass
    return today.isoformat()


def _extract_store(text, amount):
    amount_text = re.escape(str(int(amount))) if float(amount).is_integer() else re.escape(str(amount))
    normalized = text.replace(",", "")
    patterns = [
        rf"(?:今日|本日|昨日|一昨日)?\s*(?:\d{{1,2}}月\d{{1,2}}日に)?\s*(.+?)で\s*(?:[¥￥]\s*)?{amount_text}\s*円",
        rf"(?:今日|本日|昨日|一昨日)?\s*(.+?)に\s*(?:[¥￥]\s*)?{amount_text}\s*円(?:払|使)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            store = match.group(1).strip(" 、,。.!！?？")
            store = re.sub(r"^(?:で|に|は)", "", store).strip()
            if store and len(store) <= 80:
                return store
    return None


def _explicit_option(text, options):
    lowered = text.lower()
    for option in sorted(options, key=len, reverse=True):
        if option and option.lower() in lowered:
            return option
    return None


def _guess_category(text, store, categories):
    hay = f"{text} {store or ''}".lower()
    groups = [
        (["お菓子", "菓子", "チョコ", "アイス", "スイーツ"], ["お菓子", "食費"]),
        (["スーパー", "サミット", "西友", "ライフ", "食料", "ランチ", "昼食", "夕食", "ご飯", "カフェ", "スタバ", "コンビニ"], ["食費"]),
        (["電車", "バス", "タクシー", "suica", "pasmo", "交通"], ["交通費"]),
        (["薬", "ドラッグ", "洗剤", "ティッシュ", "日用品"], ["日用品"]),
        (["映画", "ゲーム", "カラオケ", "娯楽"], ["娯楽"]),
        (["netflix", "spotify", "youtube premium", "サブスク"], ["サブスク"]),
    ]
    for keywords, preferred in groups:
        if any(word in hay for word in keywords):
            for category in preferred:
                if category in categories:
                    return category
    return None


def _looks_like_natural_expense(text):
    if text.startswith(("予算", "機能確認", "貸した", "借りた", "精算", "貯金", "AI ", "直前")):
        return False
    if _extract_amount(text) is None:
        return False
    signals = ["使った", "使いました", "買った", "買いました", "払った", "払いました", "購入", "かかった", "食べた", "飲んだ"]
    return any(signal in text for signal in signals) or bool(re.search(r".+で\s*(?:[¥￥]\s*)?[0-9][0-9,]*\s*円", text))


def _category_choice_flex(item):
    buttons = [_message_button(cat, f"自然ジャンル {cat}") for cat in _available_categories()[:12]]
    buttons.append(_message_button("キャンセル", "自然入力キャンセル", "secondary"))
    return _flex(
        "🧾 ジャンルを選択",
        [f"{item['date']} / {item['store']} / {_money(item['amount'])}"],
        buttons,
        "自然文家計簿: ジャンル選択",
    )


def _card_choice_flex(item):
    buttons = [_message_button(card, f"自然支払 {card}") for card in _available_cards()[:10]]
    buttons.append(_message_button("キャンセル", "自然入力キャンセル", "secondary"))
    return _flex(
        "💳 支払方法を選択",
        [f"{item['date']} / {item['store']} / {_money(item['amount'])} / {item['category']}"],
        buttons,
        "自然文家計簿: 支払方法選択",
    )


def _confirm_flex(item, template=False):
    title = "⚡ テンプレート登録" if template else "🧾 自然文家計簿"
    return _flex(
        title,
        [
            f"日付: {item['date']}",
            f"店名: {item['store']}",
            f"金額: {_money(item['amount'])}",
            f"ジャンル: {item['category']}",
            f"支払方法: {item['card']}",
            "内容を確認してから登録します。",
        ],
        [
            _message_button("この内容で登録", "自然登録する"),
            _message_button("キャンセル", "自然入力キャンセル", "secondary"),
        ],
        "家計簿登録の確認",
    )


def _begin_natural(text):
    global _pending_natural
    amount = _extract_amount(text)
    if amount is None or amount <= 0:
        return None
    store = _extract_store(text, amount)
    if not store:
        return (
            "金額は読み取れましたが、店名を特定できませんでした。\n"
            "例: 今日サミットで2380円使った"
        )
    categories = _available_categories()
    cards = _available_cards()
    category = _explicit_option(text, categories) or _guess_category(text, store, categories)
    card = _explicit_option(text, cards)
    _pending_natural = {
        "amount": amount,
        "store": store,
        "date": _extract_date(text),
        "category": category,
        "card": card,
    }
    if not category:
        return _category_choice_flex(_pending_natural)
    if not card:
        return _card_choice_flex(_pending_natural)
    return _confirm_flex(_pending_natural)


def _recent_rows(days=90):
    end = datetime.now(JST).date() + timedelta(days=1)
    start = end - timedelta(days=days)
    return finance_phase2._expense_rows(start.isoformat(), end.isoformat())


def _template_candidates():
    rows = _recent_rows(90)
    grouped = {}
    for row in rows:
        key = (row["store"], row["category"], row["card"])
        grouped.setdefault(key, []).append(row)
    candidates = []
    for (store, category, card), items in grouped.items():
        if not store or store == "未入力":
            continue
        amounts = [x["amount"] for x in items if x["amount"] > 0]
        if not amounts:
            continue
        candidates.append({
            "store": store,
            "category": category,
            "card": card,
            "amount": median(amounts),
            "count": len(items),
            "latest": max((x["date"] for x in items), default=""),
        })
    return sorted(candidates, key=lambda x: (x["count"], x["latest"]), reverse=True)


def create_templates_flex():
    candidates = _template_candidates()[:6]
    if not candidates:
        return "【支出テンプレート】\n直近90日間の家計簿から、まだテンプレート候補を作れませんでした。"
    buttons = []
    lines = ["直近90日から、よく使う店・分類・支払方法を自動で候補化しています。"]
    for item in candidates:
        label = f"{item['store']} {_money(item['amount'])}"
        buttons.append(_message_button(label[:20], f"テンプレ {item['store']}"))
    return _flex("⚡ よく使う支出", lines, buttons, "よく使う支出テンプレート")


def _start_template(store):
    global _pending_natural
    candidates = [x for x in _template_candidates() if x["store"] == store]
    if not candidates:
        return f"テンプレート「{store}」が見つかりませんでした。もう一度「支出テンプレート」を開いてください。"
    item = candidates[0]
    _pending_natural = {
        "amount": item["amount"],
        "store": item["store"],
        "date": datetime.now(JST).strftime("%Y-%m-%d"),
        "category": item["category"],
        "card": item["card"],
    }
    return _confirm_flex(_pending_natural, template=True)


def build_today_report_text():
    today = datetime.now(JST).date()
    rows = finance_phase2._expense_rows(today.isoformat(), (today + timedelta(days=1)).isoformat())
    total = sum(x["amount"] for x in rows)
    categories = {}
    for row in rows:
        categories[row["category"]] = categories.get(row["category"], 0) + row["amount"]
    largest = max(rows, key=lambda x: x["amount"]) if rows else None
    month = finance_phase2.get_month_summary(today.strftime("%Y-%m"))
    pending = card_queue.get_pending_count()

    lines = [
        f"【本日のレポート {today.isoformat()}】",
        f"本日の支出: {_money(total)} / {len(rows)}件",
    ]
    if categories:
        category_text = " / ".join(
            f"{name} {_money(value)}"
            for name, value in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:4]
        )
        lines.append(f"内訳: {category_text}")
    if largest:
        lines.append(f"最大支出: {largest['store']} {_money(largest['amount'])}")

    lines.append("")
    lines.append(f"今月累計: {_money(month['total'])}")
    if month.get("total_budget") is not None:
        lines.append(f"今月残り予算: {_money(month['remaining_budget'])}")
        if month.get("daily_allowance") is not None:
            lines.append(f"今日以降の1日目安: {_money(month['daily_allowance'])}")
    else:
        lines.append("今月の全体予算: 未設定")
    lines.append(f"カード未処理: {pending}件")
    if not rows:
        lines.append("\n今日は家計簿への支出登録がまだありません。")
    return "\n".join(lines)


def _ensure_budget_property(category):
    if not category:
        return True, None
    if not NOTION_MONTHLY_DATABASE_ID:
        return False, "月別管理DB IDが未設定です。"
    prop_name = f"{category}予算"
    try:
        res = requests.get(
            f"https://api.notion.com/v1/databases/{NOTION_MONTHLY_DATABASE_ID}",
            headers=_headers(), timeout=10,
        )
        if res.status_code != 200:
            return False, f"月別管理DBの確認に失敗しました ({res.status_code})"
        if prop_name in res.json().get("properties", {}):
            return True, None
        patch = requests.patch(
            f"https://api.notion.com/v1/databases/{NOTION_MONTHLY_DATABASE_ID}",
            headers=_headers(), json={"properties": {prop_name: {"number": {}}}}, timeout=10,
        )
        if patch.status_code != 200:
            return False, f"{prop_name} の列を作成できませんでした ({patch.status_code})"
        return True, f"月別管理DBに「{prop_name}」を自動追加しました。"
    except Exception as e:
        return False, f"月別管理DBの更新中にエラーが発生しました: {e}"


def handle_budget_command(text):
    message = (text or "").replace("　", " ").strip()
    if not message.startswith("予算 "):
        return None
    parts = message.split()
    target_month = datetime.now(JST).strftime("%Y-%m")
    category = None
    amount_text = None

    if len(parts) == 2:
        amount_text = parts[1]
    elif len(parts) == 3:
        if re.fullmatch(r"\d{4}-\d{2}", parts[1]):
            target_month, amount_text = parts[1], parts[2]
        else:
            category, amount_text = parts[1], parts[2]
    elif len(parts) == 4 and re.fullmatch(r"\d{4}-\d{2}", parts[1]):
        target_month, category, amount_text = parts[1], parts[2], parts[3]
    else:
        return "【予算設定】\n・予算 100000\n・予算 お菓子 3000\n・予算 2026-10 食費 35000"

    cleaned = (amount_text or "").replace(",", "").replace("円", "")
    if not cleaned.isdigit() or int(cleaned) < 0:
        return "予算額は0以上の数字で入力してください。例: 予算 お菓子 3000"
    try:
        datetime.strptime(target_month, "%Y-%m")
    except ValueError:
        return "年月は YYYY-MM 形式で入力してください。"

    ok, note = _ensure_budget_property(category)
    if not ok:
        return f"⚠️ 予算設定に失敗しました。\n{note}"
    amount = int(cleaned)
    success = kakeibo.set_budget_in_notion(target_month, amount, category)
    if not success:
        return "⚠️ 予算設定に失敗しました。月別管理DBのIntegration権限とプロパティを確認してください。"
    label = f"{category}の予算" if category else "全体予算"
    result = f"✅ {target_month} の{label}を {_money(amount)} に設定しました。"
    if note:
        result += f"\n{note}"
    return result


def handle_text_command(text):
    global _pending_natural
    message = (text or "").strip()

    budget_reply = handle_budget_command(message)
    if budget_reply is not None:
        return budget_reply

    if message in ["本日のレポート", "今日のレポート", "日次レポート", "本日レポート"]:
        return build_today_report_text()

    if message in ["自然文入力", "自然文家計簿", "自然文家計簿入力"]:
        return (
            "【自然文家計簿入力】\n"
            "普通の文章から金額・店名・日付を読み取ります。\n"
            "例: 今日サミットで2380円使った\n"
            "例: 昨日コンビニで540円買った\n"
            "ジャンルや支払方法が文中になければボタンで確認します。"
        )

    if message in ["支出テンプレート", "支出テンプレ", "よく使う支出", "テンプレート"]:
        return create_templates_flex()

    if message.startswith("テンプレ "):
        return _start_template(message[5:].strip())

    if message == "自然入力キャンセル":
        _pending_natural = None
        return "自然文家計簿の登録をキャンセルしました。"

    if message.startswith("自然ジャンル "):
        if not _pending_natural:
            return "入力途中の家計簿がありません。もう一度自然文から入力してください。"
        category = message[7:].strip()
        if category not in _available_categories():
            return "そのジャンルは現在の家計簿DBにありません。"
        _pending_natural["category"] = category
        if not _pending_natural.get("card"):
            return _card_choice_flex(_pending_natural)
        return _confirm_flex(_pending_natural)

    if message.startswith("自然支払 "):
        if not _pending_natural:
            return "入力途中の家計簿がありません。もう一度自然文から入力してください。"
        card = message[5:].strip()
        if card not in _available_cards():
            return "その支払方法は現在の家計簿DBにありません。"
        _pending_natural["card"] = card
        if not _pending_natural.get("category"):
            return _category_choice_flex(_pending_natural)
        return _confirm_flex(_pending_natural)

    if message == "自然登録する":
        if not _pending_natural:
            return "登録待ちの家計簿がありません。"
        item = dict(_pending_natural)
        if not item.get("category") or not item.get("card"):
            return "ジャンルまたは支払方法が未選択です。もう一度自然文から入力してください。"
        result = kakeibo.save_kakeibo_to_notion(
            item["card"], item["store"], item["amount"], item["date"], item["category"]
        )
        _pending_natural = None
        return result

    if _looks_like_natural_expense(message):
        return _begin_natural(message)

    return None
