# FLYER_TEST.md

サミット ミナノ分倍河原店の通常チラシ・月間チラシ・Notion確認フロー・生活カレンダー・LINE日次通知の実機確認手順です。

状態: **2026-09-12 Phase 2.7 実機確認完了**

対象:

```text
公式:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufoo店舗ID:
264241
```

GitHubのGASファイルはApps Scriptへ自動反映されません。

---

# 1. Apps Scriptへコピーするファイル

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

`FlyerDeals.gs` は共通ヘルパー + LINE通知、`FlyerLifeCalendar.gs` は取得・解析・Notion同期本体です。

---

# 2. Notion DB

## 生活カレンダー

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

チラシ由来で使う主な項目:

```text
予定名
日付
種類
価格
容量・単位
店舗
備考
優先度
チラシURL
チラシ識別
識別キー
元チラシID
元チラシ名
元画像URL
確認状態
有効
更新日時
```

## チラシ一覧

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

---

# 3. Script Properties

必須:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

---

# 4. 実機確認済み項目

配信ID検出:

```text
3342326844037
9783726841844
3487936841840
4441736841834
2187006858976
```

解析・同期成功:

```text
detected=5
analyzed=5
missing=[]
flyers=5
deals=57
```

`2187006858976` は `2026-09-12〜2026-09-14` の3日間チラシとして同期済み。

---

# 5. LINE通知実機確認

テスト:

```text
testTodaySummitFlyerNotification
```

2026-09-12 実機ログ:

```text
[Notion今日分] 2026-09-12 / 元=114件 / 重複整理後=68件
```

確認済み:

```text
[x] 今日が対象日の特売だけ取得
[x] 確認済み / 有効=true を対象
[x] 1〜7日間の短期特売が先頭
[x] 8日以上の月間・長期特売は後ろ
[x] 「12日・13日限り」等の短期商品が通知される
[x] マルちゃんソースやきそばの表記揺れは1件へ整理
[x] 価格違い・明確な別容量は別件として残す
```

一部の強い言い換え、例:

```text
お刺身サーモン (切り落とし) / 999円
刺身用サーモン各種 / 999円
```

は複数残る場合があります。実用上問題ない軽微な表示揺れとして許容し、誤統合やNotion元データ削除のリスクを避けます。

---

# 6. 日次トリガー

一度だけ実行:

```text
installDailySummitLifeCalendarTrigger
```

最終日次入口:

```text
runDailySummitLifeCalendarAutomation
```

2026-09-12、Apps Scriptのトリガー画面で `runDailySummitLifeCalendarAutomation` が登録されていることを実機確認済みです。

---

# 7. 今後の保守時テスト

配信ID確認（Gemini不要）:

```text
testSummitShufooDeliveryIds
```

解析確認:

```text
testSummitLifeFlyerParse
```

同期確認:

```text
testSummitLifeFlyerSync
```

レビュー反映:

```text
applyLifeFlyerReviewsNow
```

通知確認:

```text
testTodaySummitFlyerNotification
```

Gemini無料枠を消費するため、同期・解析テストは必要時だけ行います。

---

# 8. Phase 2.7 完了条件

```text
[x] 5配信IDを正しく検出
[x] 5IDすべて解析成功
[x] 2187006858976 が 2026-09-12〜2026-09-14 で同期
[x] チラシ一覧と生活カレンダー連携
[x] 確認済みのみ有効化
[x] 短期特売を月間特価より先に通知
[x] 通知前の重複整理
[x] 日次トリガー登録確認
```

**Phase 2.7 実機確認完了。**
