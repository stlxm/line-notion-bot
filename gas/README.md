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

`NOTION_FLYER_DATABASE_ID` は現在Notionの `生活カレンダー` を指します。

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

未設定でも `gemini-3.5-flash-lite` を使用します。

---

# サミットチラシ → 生活カレンダー

対象店舗:

```text
サミット ミナノ分倍河原店
Shufoo店舗ID: 264241
```

## ファイルの役割

`FlyerLifeCalendar.gs` が取得・解析・Notion同期の本体です。

`FlyerDeals.gs` は現在、次の共通処理と通知だけを担当します。

```text
HTML/iframe/画像URL処理
Notion API共通関数
生活カレンダーから今日の特売を読む
通知前の表記揺れ重複整理
短期特売優先のLINE通知
LINE push共通関数
```

旧 `runDailySummitFlyerAutomation` 等は互換ラッパーとして残してあり、新しい生活カレンダー処理へ転送します。

---

# 複数チラシの識別

チラシ名ではなく、Shufoo URLの配信IDを1チラシの識別子として使います。

```text
/t/asp_iframe/shop/264241/<配信ID>/
```

画像URLにも配信IDがあります。

```text
.../c/YYYY/MM/DD/c/<配信ID>/img/image1_00.jpg
```

実機で確認済みの5ID:

```text
3342326844037
9783726841844
3487936841840
4441736841834
2187006858976
```

---

# Notion確認フロー

```text
新しい配信ID
↓
チラシ一覧 = 配信IDごとに確認待ち
生活カレンダー = 元チラシID付き / 種類=特売 / 確認待ち / 有効=false
↓
Notion「チラシ一覧 > 確認待ち」で画像と抽出内容を照合
↓
正しい → 確認済み
誤り   → 要修正
```

手動反映:

```text
applyLifeFlyerReviewsNow
```

---

# LINE通知

生活カレンダーの現在のプロパティ名を使います。

```text
予定名
日付
種類
価格
容量・単位
店舗
備考
優先度
確認状態
有効
元画像URL
チラシURL
```

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

## 重複判定

2026-09-12の実機では、通知対象114件が段階的な整理で83件、次に67件まで減少しました。第2段階ではさらに次を正規化します。

```text
3食入 / 3食
6切入、1パック / 6切入 1パック
産地付き/なし
空白・括弧・区切り記号
切りおとし / 切り落とし
実機で確認したOCR誤字
```

完全正規化後の商品名が一致する場合は統合候補です。

曖昧な商品ファミリー一致を統合する場合は、誤統合防止のため次をすべて要求します。

```text
同じ価格
容量/個数に矛盾なし
同じ元画像
同じ対象期間
```

価格違い・明確な別容量は別商品として残します。Notion元データは削除しません。

テスト:

```text
testTodaySummitFlyerNotification
```

確認例:

```text
マルちゃん ソースやきそば / 3食入
マルちゃんソースやきそば / 3食
→ 1件

お刺身サーモン (切り落とし) / 999円 / 6切入、1パック
刺身用サーモン各種 / 999円 / 6切入 1パック
→ 1件
```

---

# 初回・再テスト

Apps Scriptの次の2ファイルをGitHub最新版で丸ごと上書きします。

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

診断用の `FlyerRecovery.gs` / `FlyerParseDebug.gs` / `FlyerStrictSync.gs` が残っていれば削除します。

配信ID検出:

```text
testSummitShufooDeliveryIds
```

同期:

```text
testSummitLifeFlyerSync
```

LINE通知だけ再テストする場合はGeminiを回さず:

```text
testTodaySummitFlyerNotification
```

詳細は `FLYER_TEST.md`。

---

# 最終日次トリガー

全テスト正常後、一度だけ:

```text
installDailySummitLifeCalendarTrigger
```

最終入口:

```text
runDailySummitLifeCalendarAutomation
```

を毎日6時台へ設定します。

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

LINE通知の重複が多い:
- `FlyerDeals.gs` をGitHub最新版で丸ごと上書き
- `testTodaySummitFlyerNotification` を実行
- `[Notion今日分] 元=N件 / 重複整理後=M件` を比較
- 価格違い・別容量が別件で残るのは正常

短期商品が通知されない:
- `testTodaySummitFlyerNotification` を実行
- `日付` が今日を含んでいるか確認
- `確認状態=確認済み / 有効=true` を確認
