# GAS セットアップ

GASはカード監視・定期通知・サミットのチラシ取得を担当します。

主なファイル:

```text
gas/Code.gs                  カード利用メール監視
gas/FinanceReports.gs        家計簿定期通知 + 毎月1日の予算設定案内
gas/DailyMemo.gs             メモ通知
gas/FlyerDeals.gs            共通Web/Notion/LINE処理 + 今日の特売通知
gas/FlyerLifeCalendar.gs     Shufoo配信ID検出・個別解析・生活カレンダー同期
gas/FlyerAutoMode.gs         チラシの手動確認廃止・自動有効化・新日次入口
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

旧 `3d90efb323d080b5999bed1820a6665e` は削除済みDBです。使用しません。

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密値は `.gs` ファイルへ直書きしません。

---

# 毎月1日の予算設定案内

実装:

```text
gas/FinanceReports.gs
```

通知本体:

```text
sendMonthlyBudgetNotice
```

毎月1日朝6時台に予算設定FlexをLINEへ送ります。Postbackには `displayText` を付けています。

手動テスト:

```text
testMonthlyBudgetNotice
```

トリガー作成:

```text
installMonthlyBudgetNoticeTrigger
```

Apps Scriptプロジェクトのタイムゾーンは `Asia/Tokyo` にしてください。

---

# サミットチラシ → 生活カレンダー

対象店舗:

```text
サミット ミナノ分倍河原店
Shufoo店舗ID: 264241
```

実運用DB:

```text
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

`FlyerLifeCalendar.gs` が取得・解析・Notion同期の本体です。

`FlyerDeals.gs` はHTML/iframe/画像URL処理、Notion API共通関数、重複整理、短期特売優先通知、LINE push共通処理を担当します。

`FlyerAutoMode.gs` は、旧仕様の「確認待ちをNotionで確認済みにする」手作業をなくします。

---

# チラシ手動確認は不要

新仕様:

```text
Shufooから新しいチラシを検出
↓
配信IDごとにGemini解析
↓
全配信IDの解析成功を確認
↓
Notionへ同期
↓
自動で 確認済み / 有効=true
↓
生活カレンダー / LINE通知へ反映
```

Notionでユーザーが `確認待ち → 確認済み` に変更する必要はありません。

既存の掲載中データが `確認待ち` のまま残っている場合も、自動反映モードが `確認済み / 有効=true` に更新します。

期限切れ特売は従来どおり無効化します。

---

# 日次トリガー

Apps Scriptへ次の3ファイルを丸ごと反映してください。

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
gas/FlyerAutoMode.gs
```

その後、1回だけ:

```text
installDailySummitLifeCalendarAutoTrigger
```

この関数は旧チラシ日次トリガーを削除し、次を毎日6時台に登録します。

```text
runDailySummitLifeCalendarAutoAutomation
```

旧 `runDailySummitLifeCalendarAutomation` は互換用として残りますが、日次運用では自動反映版を使います。

---

# 軽量テスト

Geminiを再実行せず、現在Notionにあるデータだけで自動有効化と通知を確認:

```text
testSummitLifeCalendarAutoMode
```

確認項目:

```text
・掲載中の確認待ちデータが自動で確認済みになる
・生活カレンダーの掲載中特売が有効=trueになる
・今日の特売がLINEへ通知される
・手動の確認操作が不要
```

---

# 複数チラシの識別

チラシ名ではなくShufoo配信IDを使います。

```text
/t/asp_iframe/shop/264241/<配信ID>/
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

自動反映モードの日次通知対象:

```text
店舗 = サミット ミナノ分倍河原店
種類 = 特売
有効 = true
日付が今日を含む
```

手動の確認状態変更は不要です。

表示順:

```text
🔥 今日・短期特売  = 1〜7日間
📅 月間・長期特売 = 8日以上
```

通知上限は20件です。Notion元データは自動削除しません。

---

# チラシテスト関数

```text
testSummitShufooDeliveryIds
testSummitLifeFlyerParse
testSummitLifeFlyerSync
testSummitLifeCalendarAutoMode
```

解析・同期テストはGemini無料枠を使うため、必要時だけ行います。

---

# 推奨トリガー

```text
checkCardEmails                               1時間ごと
sendMonthlyBudgetNotice                       毎月1日6時台
runDailySummitLifeCalendarAutoAutomation      毎日6時台
sendDailyMemoReminder                         毎日8時ごろ
sendDailyBudgetAlert                          毎日20時ごろ
sendDailyCardPendingReminder                  毎日20〜21時ごろ
sendMonthEndCardCheck                         毎日21時ごろ
sendWeeklyFinanceReport                       毎週日曜20時ごろ
```

---

# GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。

チラシ自動反映を使う場合は、GitHub最新版の:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
gas/FlyerAutoMode.gs
```

をApps Scriptへ反映してください。

---

# トラブルシューティング

チラシが自動反映されない:
- `FlyerAutoMode.gs` がApps Scriptにあるか確認
- `installDailySummitLifeCalendarAutoTrigger` を1回実行
- トリガー画面で `runDailySummitLifeCalendarAutoAutomation` を確認
- `testSummitLifeCalendarAutoMode` を実行
- Script Properties の `NOTION_FLYER_DATABASE_ID` が `684f959e451047389505a95ed368a7d6` か確認

特売コマンドだけ動かない:
- RenderをGitHub最新版へ再デプロイ
- `NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6` を確認
- 生活カレンダーが `LINE bot Access` Integrationへ共有されているか確認
