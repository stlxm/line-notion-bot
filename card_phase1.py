import card_queue
import card_rules
import kakeibo
import ledger_guard


def get_card_view_context(item):
    """未処理カードUI向けのおすすめ・同一店件数を返す。"""
    if not item:
        return {"suggestion": None, "same_store_count": 0}
    suggestion = card_rules.suggest_category(item.get("store"))
    same_items = card_queue.get_matching_pending_items(item.get("card"), item.get("store"))
    return {"suggestion": suggestion, "same_store_count": len(same_items)}


def classify_one(pending_id, category, force_duplicate=False):
    """未処理カードを1件保存。重複候補は通常止め、明示的force時のみ保存する。"""
    item = card_queue.get_item(pending_id)
    if not item:
        return {"status": "missing"}

    duplicate = None if force_duplicate else ledger_guard.find_duplicate(
        item["card"], item["store"], item["amount"], item["date"]
    )
    if duplicate:
        return {"status": "duplicate", "item": item, "duplicate": duplicate}

    message = kakeibo.save_kakeibo_to_notion(
        item["card"], item["store"], item["amount"], item["date"], category
    )
    if not message.startswith("家計簿に記録しました！"):
        return {"status": "error", "item": item, "message": message}

    learned = card_rules.learn_category(item["store"], category, display_name=item["store"])
    removed = card_queue.complete(pending_id)
    return {
        "status": "saved",
        "item": item,
        "message": message,
        "learned": learned,
        "removed": removed,
    }


def classify_same_store(pending_id, category):
    """同じカード＋正規化店名の未処理をまとめて同ジャンルへ分類する。

    家計簿にすでに同一取引があれば、そのキュー項目は再保存せず照合済みとして消す。
    保存失敗した項目はキューに残す。
    """
    origin = card_queue.get_item(pending_id)
    if not origin:
        return {"status": "missing", "saved": 0, "reconciled": 0, "failed": 0}

    targets = card_queue.get_matching_pending_items(origin["card"], origin["store"])
    saved = 0
    reconciled = 0
    failed = 0
    total = len(targets)

    for item in targets:
        duplicate = ledger_guard.find_duplicate(
            item["card"], item["store"], item["amount"], item["date"]
        )
        if duplicate:
            if card_queue.complete(item["id"]):
                reconciled += 1
            else:
                failed += 1
            continue

        message = kakeibo.save_kakeibo_to_notion(
            item["card"], item["store"], item["amount"], item["date"], category
        )
        if message.startswith("家計簿に記録しました!") or message.startswith("家計簿に記録しました！"):
            card_rules.learn_category(item["store"], category, display_name=item["store"])
            if card_queue.complete(item["id"]):
                saved += 1
            else:
                failed += 1
        else:
            failed += 1

    return {
        "status": "done",
        "total": total,
        "saved": saved,
        "reconciled": reconciled,
        "failed": failed,
    }


def try_auto_register(pending_id):
    """明示ONかつ3回以上100%一致の店だけ自動登録する。"""
    item = card_queue.get_item(pending_id)
    if not item:
        return {"status": "missing"}
    suggestion = card_rules.suggest_category(item["store"])
    if not suggestion or not suggestion.get("can_auto_register"):
        return {"status": "manual", "item": item, "suggestion": suggestion}

    duplicate = ledger_guard.find_duplicate(item["card"], item["store"], item["amount"], item["date"])
    if duplicate:
        removed = card_queue.complete(pending_id)
        return {"status": "reconciled", "item": item, "duplicate": duplicate, "removed": removed}

    category = suggestion["category"]
    message = kakeibo.save_kakeibo_to_notion(
        item["card"], item["store"], item["amount"], item["date"], category
    )
    if not message.startswith("家計簿に記録しました！"):
        return {"status": "error", "item": item, "message": message}

    removed = card_queue.complete(pending_id)
    # 自動結果は自己強化しない。学習回数はユーザーが手動確定した時だけ増やす。
    return {"status": "saved", "item": item, "category": category, "message": message, "removed": removed}
