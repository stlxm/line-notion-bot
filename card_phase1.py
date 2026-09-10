import card_queue
import card_rules
import kakeibo
import ledger_guard


def get_card_view_context(item):
    if not item:
        return {"suggestion": None, "same_store_count": 0}
    suggestion = card_rules.suggest_category(item.get("store"))
    same_items = card_queue.get_matching_pending_items(item.get("card"), item.get("store"))
    return {"suggestion": suggestion, "same_store_count": len(same_items)}


def classify_one(pending_id, category, force_duplicate=False):
    """未処理カードを1件保存。重複候補は本人確認まで保存しない。"""
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
    return {"status": "saved", "item": item, "message": message, "learned": learned, "removed": removed}


def classify_same_store(pending_id, category):
    """同じカード＋正規化店名をまとめて分類する。

    重複候補は勝手に消さず未処理に残し、個別確認へ回す。
    """
    origin = card_queue.get_item(pending_id)
    if not origin:
        return {"status": "missing", "saved": 0, "reconciled": 0, "needs_review": 0, "failed": 0}

    targets = card_queue.get_matching_pending_items(origin["card"], origin["store"])
    saved = 0
    needs_review = 0
    failed = 0

    for item in targets:
        duplicate = ledger_guard.find_duplicate(item["card"], item["store"], item["amount"], item["date"])
        if duplicate:
            needs_review += 1
            continue

        message = kakeibo.save_kakeibo_to_notion(
            item["card"], item["store"], item["amount"], item["date"], category
        )
        if message.startswith("家計簿に記録しました！"):
            card_rules.learn_category(item["store"], category, display_name=item["store"])
            if card_queue.complete(item["id"]):
                saved += 1
            else:
                failed += 1
        else:
            failed += 1

    return {
        "status": "done",
        "total": len(targets),
        "saved": saved,
        "reconciled": 0,
        "needs_review": needs_review,
        # 現行UIでは「失敗・未処理のまま」にまとめて表示するため、要確認も含める。
        "failed": failed + needs_review,
    }


def try_auto_register(pending_id):
    """明示ONかつ十分学習済みの店だけ自動登録する。

    家計簿に重複候補がある場合は自動処理せず、通常の未処理確認へ戻す。
    """
    item = card_queue.get_item(pending_id)
    if not item:
        return {"status": "missing"}
    suggestion = card_rules.suggest_category(item["store"])
    if not suggestion or not suggestion.get("can_auto_register"):
        return {"status": "manual", "item": item, "suggestion": suggestion}

    duplicate = ledger_guard.find_duplicate(item["card"], item["store"], item["amount"], item["date"])
    if duplicate:
        return {"status": "manual_duplicate", "item": item, "duplicate": duplicate, "suggestion": suggestion}

    category = suggestion["category"]
    message = kakeibo.save_kakeibo_to_notion(
        item["card"], item["store"], item["amount"], item["date"], category
    )
    if not message.startswith("家計簿に記録しました！"):
        return {"status": "error", "item": item, "message": message}

    removed = card_queue.complete(pending_id)
    return {"status": "saved", "item": item, "category": category, "message": message, "removed": removed}
