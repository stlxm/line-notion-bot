import os
from datetime import datetime, timezone, timedelta

import requests

JST = timezone(timedelta(hours=9), "JST")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_LOAN_DATABASE_ID = os.environ.get("NOTION_LOAN_DATABASE_ID", "")


def _headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _query_all(payload=None):
    if not NOTION_API_KEY or not NOTION_LOAN_DATABASE_ID:
        return []
    url = f"https://api.notion.com/v1/databases/{NOTION_LOAN_DATABASE_ID}/query"
    body = dict(payload or {})
    rows = []
    while True:
        res = requests.post(url, headers=_headers(), json=body, timeout=12)
        if res.status_code != 200:
            raise RuntimeError(f"Notion query failed: {res.status_code} {res.text[:200]}")
        data = res.json()
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            return rows
        body["start_cursor"] = data.get("next_cursor")


def _title(prop):
    return "".join(x.get("plain_text", "") for x in (prop or {}).get("title", []))


def _rich(prop):
    return "".join(x.get("plain_text", "") for x in (prop or {}).get("rich_text", []))


def _row(page):
    props = page.get("properties", {})
    return {
        "id": page.get("id"),
        "person": _title(props.get("相手")),
        "kind": ((props.get("種類", {}).get("select") or {}).get("name") or ""),
        "amount": float(props.get("金額", {}).get("number") or 0),
        "date": ((props.get("日付", {}).get("date") or {}).get("start") or "")[:10],
        "status": ((props.get("状態", {}).get("select") or {}).get("name") or ""),
        "settled_date": ((props.get("精算日", {}).get("date") or {}).get("start") or "")[:10],
        "memo": _rich(props.get("メモ")),
    }


def _configured():
    return bool(NOTION_API_KEY and NOTION_LOAN_DATABASE_ID)


def add_entry(kind, person, amount, memo=""):
    if not _configured():
        return False, "貸し借りDBが未設定です。SETUP.mdの NOTION_LOAN_DATABASE_ID を設定してください。"
    if kind not in ["貸した", "借りた"]:
        return False, "種類は「貸した」または「借りた」にしてください。"
    person = (person or "").strip()
    if not person:
        return False, "相手を入力してください。"
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return False, "金額は数字で入力してください。"
    if amount <= 0:
        return False, "金額は1円以上にしてください。"

    today = datetime.now(JST).strftime("%Y-%m-%d")
    payload = {
        "parent": {"database_id": NOTION_LOAN_DATABASE_ID},
        "properties": {
            "相手": {"title": [{"text": {"content": person}}]},
            "種類": {"select": {"name": kind}},
            "金額": {"number": amount},
            "日付": {"date": {"start": today}},
            "状態": {"select": {"name": "未精算"}},
            "メモ": {"rich_text": [{"text": {"content": memo[:1900]}}]} if memo else {"rich_text": []},
        },
    }
    try:
        res = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json=payload, timeout=12)
    except Exception as e:
        return False, f"貸し借りの保存中にエラーが発生しました: {e}"
    if res.status_code != 200:
        return False, "貸し借りの保存に失敗しました。Notion DBとIntegration権限を確認してください。"
    return True, f"{kind}: {person} / ¥{int(amount):,} を記録しました。"


def outstanding_rows():
    if not _configured():
        return []
    pages = _query_all({
        "filter": {"property": "状態", "select": {"equals": "未精算"}},
        "sorts": [{"property": "日付", "direction": "descending"}],
    })
    return [_row(page) for page in pages]


def build_overview_text():
    if not _configured():
        return "【貸し借り】\n貸し借りDBが未設定です。SETUP.mdの NOTION_LOAN_DATABASE_ID を設定してください。"
    try:
        rows = outstanding_rows()
    except Exception as e:
        return f"貸し借り一覧の取得に失敗しました: {e}"
    if not rows:
        return "【貸し借り】\n未精算の貸し借りはありません。"

    lent = sum(x["amount"] for x in rows if x["kind"] == "貸した")
    borrowed = sum(x["amount"] for x in rows if x["kind"] == "借りた")
    lines = [
        "【未精算の貸し借り】",
        f"貸している: ¥{int(lent):,}",
        f"借りている: ¥{int(borrowed):,}",
        "",
    ]
    for item in rows[:20]:
        memo = f" / {item['memo']}" if item.get("memo") else ""
        lines.append(f"・{item['kind']} {item['person']} ¥{int(item['amount']):,} ({item['date']}){memo}")
    if len(rows) > 20:
        lines.append(f"ほか {len(rows) - 20} 件")
    lines.append("\n精算: 精算 相手 金額\n例: 精算 田中 3000")
    return "\n".join(lines)


def settle(person, amount):
    if not _configured():
        return "貸し借りDBが未設定です。SETUP.mdの NOTION_LOAN_DATABASE_ID を設定してください。"
    try:
        amount = float(str(amount).replace(",", ""))
    except ValueError:
        return "精算金額は数字で入力してください。"

    try:
        rows = outstanding_rows()
    except Exception as e:
        return f"精算対象の取得に失敗しました: {e}"
    matches = [x for x in rows if x["person"] == person and abs(x["amount"] - amount) < 0.01]
    if not matches:
        return f"未精算の「{person} / ¥{int(amount):,}」が見つかりませんでした。"
    if len(matches) > 1:
        return f"「{person} / ¥{int(amount):,}」が複数あります。誤更新防止のため、Notionで対象を確認してください。"

    today = datetime.now(JST).strftime("%Y-%m-%d")
    payload = {
        "properties": {
            "状態": {"select": {"name": "精算済み"}},
            "精算日": {"date": {"start": today}},
        }
    }
    try:
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{matches[0]['id']}",
            headers=_headers(), json=payload, timeout=12,
        )
    except Exception as e:
        return f"精算更新中にエラーが発生しました: {e}"
    if res.status_code != 200:
        return "精算状態の更新に失敗しました。"
    return f"✅ {person} / ¥{int(amount):,} を精算済みにしました。"


def handle_text_command(text):
    message = (text or "").strip().replace("　", " ")
    if message in ["貸し借り", "貸し借り一覧", "貸借", "立替一覧"]:
        return build_overview_text()

    for kind in ["貸した", "借りた"]:
        if message.startswith(kind + " "):
            parts = message.split()
            if len(parts) < 3:
                return f"{kind} 相手 金額 [メモ]\n例: {kind} 田中 3000 ランチ代"
            person = parts[1]
            amount_text = parts[2].replace(",", "")
            try:
                amount = float(amount_text)
            except ValueError:
                return f"金額は数字で入力してください。例: {kind} 田中 3000"
            memo = " ".join(parts[3:]) if len(parts) >= 4 else ""
            success, result = add_entry(kind, person, amount, memo)
            return ("✅ " if success else "⚠️ ") + result

    if message.startswith("精算 "):
        parts = message.split()
        if len(parts) != 3:
            return "精算 相手 金額\n例: 精算 田中 3000"
        return settle(parts[1], parts[2])

    return None
