# GAS セットアップ

GASはカード監視・定期通知・サミットのチラシ取得を担当します。

主なファイル:

```text
gas/Code.gs                  カード利用メール監視
gas/FinanceReports.gs        家計簿定期通知
gas/DailyMemo.gs             メモ通知
gas/FlyerDeals.gs            共通Web/Notion/LINE処理 + 今日の特売通知
gas/FlyerLifeCalendar.gs     Shufoo配信ID検出・個別解析・確認フロー・生活カレンダー同期
```

---

# Script Properties

共通:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

チラシ用:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

---

# サミットチラシ → 生活カレンダー

状態: **実装完了・実機確認済み・日次運用中**

対象店舗:

```text
サミット ミナノ分倍河原店
Shufoo店舗ID: 264241
```

## ファイルの役割

`FlyerLifeCalendar.gs` が取得・解析・Notion同期の本体です。

`FlyerDeals.gs` は次を担当します。

```text
HTML/iframe/画像URL処理
Notion API共通関数
生活カレンダーから今日の特売を読む
通知前の表記揺れ重複整理
短期特売優先のLINE通知
LINE push共通関数
```

---

# 複数チラシの識別

チラシ名ではなくShufoo配信IDを使います。

```text
/t/asp_iframe/shop/264241/<配信ID>/
```

画像URLにも配信IDがあります。

```text
.../c/YYYY/MM/DD/c/<配信ID>/img/image1_00.jpg
```

実機確認済み5ID:

```text
3342326844037
9783726841844
3487936841840
4441736841834
2187006858976
```

---

# LINE通知

通知対象:

```text
店舗 = サミット ミナノ分倍河原店
種類 = 特売
確認状態 = 確認済み
有効 = true
日付が今日を含む
```

表示順:

```text
🔥 今日・短期特売  = 1〜7日間
📅 月間・長期特売 = 8日以上
```

通知上限は20件です。

2026-09-12の実機では:

```text
元=114件
重複整理後=68件
```

短期商品が月間商品より先に通知されることを確認済みです。表記揺れ重複も通知時に整理します。

一部の強い言い換え重複は残る場合がありますが、誤統合防止を優先し、Notion元データは自動削除しません。

---

# Notion確認フロー

```text
新しい配信ID
↓
チラシ一覧 = 確認待ち
生活カレンダー = 確認待ち / 有効=false
↓
人が画像と抽出結果を確認
↓
確認済み
↓
applyLifeFlyerReviewsNow または日次処理
↓
確認済み配信ID由来だけ有効=true
```

---

# テスト関数

配信IDのみ:

```text
testSummitShufooDeliveryIds
```

解析:

```text
testSummitLifeFlyerParse
```

同期:

```text
testSummitLifeFlyerSync
```

通知:

```text
testTodaySummitFlyerNotification
```

レビュー反映:

```text
applyLifeFlyerReviewsNow
```

---

# 最終日次トリガー

インストール関数:

```text
installDailySummitLifeCalendarTrigger
```

日次入口:

```text
runDailySummitLifeCalendarAutomation
```

**2026-09-12、Apps Scriptのトリガー画面で `runDailySummitLifeCalendarAutomation` が登録済みであることを実機確認済みです。**

通常はこのトリガーをそのまま運用し、問題が起きたときだけ手動テストします。

---

# GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。

チラシ機能でコピーするのは:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

一部だけの手修正ではなく、原則GitHub最新版をファイル単位で丸ごと反映します。

---

# トラブルシューティング

LINE通知0件:
- チラシ一覧が `確認済み` か
- 生活カレンダーが `種類=特売 / 確認状態=確認済み / 有効=true` か
- 今日が `日付` の範囲内か

短期商品が通知されない:
- `testTodaySummitFlyerNotification` を実行
- `[Notion今日分]` の元件数/重複整理後件数を確認

配信ID・解析異常:
- まず `testSummitShufooDeliveryIds`
- 必要時だけ `testSummitLifeFlyerParse` / `testSummitLifeFlyerSync`
- Gemini無料枠を消費するため連続実行しない
