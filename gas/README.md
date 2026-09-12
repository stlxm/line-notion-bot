# GAS セットアップ

GASはカード監視・定期通知・サミットのチラシ取得を担当します。

主なファイル:

```text
gas/Code.gs                  カード利用メール監視
gas/FinanceReports.gs        家計簿定期通知
gas/DailyMemo.gs             メモ通知
gas/FlyerDeals.gs            チラシ取得・共通Notion/LINE処理
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

## 複数チラシの識別

チラシ名ではなく、Shufoo URLの配信IDを1チラシの識別子として使います。

```text
/t/asp_iframe/shop/264241/<配信ID>/
```

例:

```text
9783726841844
4441736841834
```

同じ店舗・同じ開始日・似た名前でも、配信IDが違えば別チラシです。

`FlyerLifeCalendar.gs`:

```text
Shufoo一覧HTMLを取得
↓
/shop/264241/<配信ID>/ を列挙
↓
各配信IDのページを別々に取得
↓
各配信IDの画像を別々に取得
↓
各配信IDを別々にGemini解析
↓
掲載期間から 月間 / 週次 / 日替わり / その他 に分類
↓
チラシ一覧DBへ 配信ID付き・確認待ち で保存
↓
生活カレンダーへ 元チラシID付き・種類=特売・有効=false で保存
↓
確認済みの配信ID由来だけ有効化
↓
今日対象の確認済み特売だけLINE通知
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

# 初回・再テスト

Apps Scriptの `FlyerLifeCalendar.gs` をGitHub最新版で上書き後:

```text
testSummitLifeFlyerParse
```

ログ先頭の:

```text
検出した配信ID: [...]
```

を確認します。

現在チラシが3種類なら配信IDも3件必要です。IDが3件出てから:

```text
testSummitLifeFlyerSync
```

を実行します。

詳細は `FLYER_TEST.md`。

---

# 最終日次トリガー

一度だけ:

```text
installDailySummitLifeCalendarTrigger
```

最終入口:

```text
runDailySummitLifeCalendarAutomation
```

を毎日6時台へ設定します。

---

# 通常カード監視

```text
checkCardEmails → 1時間ごと
```

---

# 定期通知

```text
runDailySummitLifeCalendarAutomation → 毎日6時台
sendDailyMemoReminder               → 毎日朝8時ごろ
sendDailyBudgetAlert               → 毎日20時ごろ
sendDailyCardPendingReminder       → 毎日20〜21時ごろ
sendMonthEndCardCheck              → 毎日21時ごろ
sendWeeklyFinanceReport            → 毎週日曜20時ごろ
```

---

# GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。

チラシ機能でコピーするのは:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

---

# トラブルシューティング

チラシが1件しか出ない:
- `testSummitLifeFlyerParse` の `検出した配信ID` を確認。
- 期待3件なのに1件ならID抽出側の問題。
- IDは3件あるのにflyersが減るなら各配信IDの画像/掲載期間解析を確認。

Notion同期失敗:
- `NOTION_API_KEY`
- `NOTION_FLYER_DATABASE_ID`
- `NOTION_FLYER_LIST_DATABASE_ID`
- Integrationが生活カレンダー/チラシ一覧の両DBへ接続されているか

LINE通知0件:
- チラシ一覧が `確認済み` か
- 生活カレンダーが `種類=特売 / 確認状態=確認済み / 有効=true` か
- 今日が `日付` の範囲内か
