import json
from urllib.parse import urlencode

from linebot.v3.messaging import FlexMessage, FlexContainer


def _postback_action(label, data, display_text=None):
    return {
        "type": "postback",
        "label": str(label)[:20],
        "data": data,
        "displayText": (display_text or f"▶ {label}")[:300],
    }


def create_choice_flex(title, options, callback_action, extra_params=None, include_cancel=False):
    extra_params = extra_params or {}
    buttons = []
    for option in options:
        params = {"action": callback_action, "val": option, **extra_params}
        buttons.append({
            "type": "button", "style": "primary", "height": "sm",
            "action": _postback_action(option, urlencode(params), f"▶ {option}"),
        })
    if include_cancel:
        buttons.append({
            "type": "button", "style": "secondary", "height": "sm",
            "action": _postback_action("キャンセル", "action=cancel_registration", "▶ キャンセル"),
        })
    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons or [
            {"type": "text", "text": "選択肢がありません。", "size": "sm", "color": "#888888"}
        ]},
    }
    return FlexMessage(alt_text=title, contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))


def create_card_category_flex(
    card, store, amount, date_str, categories, pending_id=None,
    suggestion=None, same_store_count=1, save_action="kakeibo_save",
):
    """カード分類UI。固定費は隠し、サブスクは必ず表示する。"""
    cleaned_categories = []
    for category in categories or []:
        category = str(category).strip()
        if not category or category == "固定費" or category in cleaned_categories:
            continue
        cleaned_categories.append(category)
    if "サブスク" not in cleaned_categories:
        cleaned_categories.append("サブスク")

    suggested_cat = (suggestion or {}).get("category")
    if suggested_cat in cleaned_categories:
        cleaned_categories.remove(suggested_cat)
        cleaned_categories.insert(0, suggested_cat)

    category_buttons = []
    for category in cleaned_categories:
        if pending_id:
            params = {"action": save_action, "pending_id": pending_id, "cat": category}
        else:
            params = {
                "action": save_action, "card": card, "store": store,
                "amount": amount, "date": date_str, "cat": category,
            }
        label = f"★{category}" if category == suggested_cat else category
        category_buttons.append({
            "type": "button", "style": "primary", "height": "sm", "flex": 1,
            "action": _postback_action(str(label)[:10], urlencode(params), f"▶ {category}"),
        })

    rows = []
    for i in range(0, len(category_buttons), 2):
        row_buttons = category_buttons[i:i + 2]
        if len(row_buttons) == 1:
            row_buttons.append({"type": "box", "layout": "vertical", "flex": 1, "contents": []})
        rows.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row_buttons})

    action_buttons = []
    if pending_id and save_action == "kakeibo_save" and same_store_count > 1:
        action_buttons.append({
            "type": "button", "style": "primary", "height": "sm",
            "action": _postback_action(
                f"同じ店 {same_store_count}件をまとめる",
                urlencode({"action": "card_batch_select", "pending_id": pending_id}),
                f"▶ 同じ店 {same_store_count}件をまとめる",
            ),
        })
    if pending_id and save_action == "kakeibo_save":
        action_buttons.append({
            "type": "button", "style": "primary", "height": "sm",
            "action": _postback_action(
                "店名を変更する",
                urlencode({"action": "card_change_store_start", "pending_id": pending_id}),
                "▶ 店名を変更する",
            ),
        })
    if pending_id and suggestion and suggestion.get("eligible_for_auto") and not suggestion.get("auto_register"):
        action_buttons.append({
            "type": "button", "style": "primary", "height": "sm",
            "action": _postback_action(
                "次回から自動登録ON",
                urlencode({"action": "card_auto_on", "rule_id": suggestion.get("page_id")}),
                "▶ 次回から自動登録ON",
            ),
        })

    if save_action == "kakeibo_save":
        skip_data = urlencode({"action": "skip_card_pending", "pending_id": pending_id}) if pending_id else "action=cancel_registration"
        action_buttons.append({
            "type": "button", "style": "secondary", "height": "sm",
            "action": _postback_action("登録しない", skip_data, "▶ 登録しない"),
        })
    else:
        action_buttons.append({
            "type": "button", "style": "secondary", "height": "sm",
            "action": _postback_action(
                "戻る",
                urlencode({"action": "card_select_cat", "pending_id": pending_id}),
                "▶ 戻る",
            ),
        })

    body_contents = [
        {"type": "text", "text": "利用先", "size": "xs", "color": "#aaaaaa"},
        {"type": "text", "text": store, "weight": "bold", "size": "md", "wrap": True, "margin": "xs"},
        {"type": "text", "text": f"カード: {card}", "size": "sm", "color": "#666666", "wrap": True, "margin": "md"},
        {"type": "text", "text": f"利用日: {date_str}", "size": "sm", "color": "#666666", "wrap": True, "margin": "xs"},
    ]
    if suggestion and suggestion.get("category"):
        body_contents.append({
            "type": "text",
            "text": f"おすすめ: {suggestion['category']}（{suggestion.get('match_count', 0)}/{suggestion.get('learn_count', 0)}回一致）",
            "size": "sm", "color": "#1DB446", "weight": "bold", "wrap": True, "margin": "md",
        })
    if same_store_count > 1:
        body_contents.append({
            "type": "text", "text": f"同じ店の未処理: {same_store_count}件", "size": "sm", "color": "#666666", "wrap": True, "margin": "xs",
        })
    body_contents.extend([
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": "ジャンルを選択してください", "size": "sm", "weight": "bold", "margin": "lg", "wrap": True},
    ])

    footer_contents = rows + ([{"type": "separator", "margin": "md"}] if rows and action_buttons else []) + action_buttons
    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "💳 カード利用検知", "weight": "bold", "size": "sm", "color": "#1DB446"},
            {"type": "text", "text": f"¥{int(float(amount)):,}", "weight": "bold", "size": "xxl", "margin": "md"},
        ]},
        "body": {"type": "box", "layout": "vertical", "contents": body_contents},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": footer_contents},
    }
    return FlexMessage(alt_text=f"カード利用: {store} ¥{amount}", contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))


def create_duplicate_confirm_flex(pending_id, category, duplicate):
    text = f"{duplicate.get('date', '')[:10]} / ¥{int(float(duplicate.get('amount', 0))):,} / {duplicate.get('store', '')}"
    flex_json = {
        "type": "bubble", "size": "mega",
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "⚠️ 重複候補があります", "weight": "bold", "size": "lg", "wrap": True},
            {"type": "text", "text": text, "size": "sm", "color": "#666666", "wrap": True, "margin": "md"},
            {"type": "text", "text": "同日・同額・同カード・同じ店名の家計簿データがあります。", "size": "sm", "wrap": True, "margin": "md"},
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "button", "style": "primary", "height": "sm",
             "action": _postback_action("それでも保存する", urlencode({"action": "kakeibo_save_force", "pending_id": pending_id, "cat": category}), "▶ それでも保存する")},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": _postback_action("重複として処理済みにする", urlencode({"action": "card_reconcile_duplicate", "pending_id": pending_id}), "▶ 重複として処理済みにする")},
        ]},
    }
    return FlexMessage(alt_text="家計簿の重複候補があります", contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))


def create_card_rules_flex(rules):
    contents = []
    for rule in rules[:10]:
        status = "ON" if rule.get("auto_register") else "OFF"
        eligible = "自動登録可" if rule.get("eligible_for_auto") else f"{rule.get('match_count', 0)}/{rule.get('learn_count', 0)}回一致"
        contents.append({"type": "text", "text": f"{rule.get('display_name') or rule.get('store_key')} → {rule.get('category')} / {status} / {eligible}", "size": "sm", "wrap": True})
        if rule.get("auto_register"):
            contents.append({
                "type": "button", "style": "secondary", "height": "sm",
                "action": _postback_action("自動登録OFF", urlencode({"action": "card_auto_off", "rule_id": rule.get("page_id")}), "▶ 自動登録OFF"),
            })
        elif rule.get("eligible_for_auto"):
            contents.append({
                "type": "button", "style": "primary", "height": "sm",
                "action": _postback_action("自動登録ON", urlencode({"action": "card_auto_on", "rule_id": rule.get("page_id")}), "▶ 自動登録ON"),
            })
        contents.append({"type": "separator", "margin": "sm"})
    if not contents:
        contents = [{"type": "text", "text": "学習済みのカード分類ルールはありません。", "size": "sm", "wrap": True}]
    flex_json = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "💳 カード自動分類ルール", "weight": "bold", "size": "lg"},
            {"type": "text", "text": "同じジャンルで3回以上100%一致した店だけ自動登録をONにできます。", "size": "xs", "color": "#888888", "wrap": True, "margin": "xs"},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": contents},
    }
    return FlexMessage(alt_text="カード自動分類ルール", contents=FlexContainer.from_json(json.dumps(flex_json, ensure_ascii=False)))
