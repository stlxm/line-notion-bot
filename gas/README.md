# GAS セットアップ

GASはカード監視・定期通知・サミットのチラシ取得を担当します。

主なファイル:

```text
gas/Code.gs                  カード利用メール監視
gas/FinanceReports.gs        家計簿定期通知 + 毎月1日の予算設定案内
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

毎月1日朝6時台に次のFlexをLINEへ送ります。

```text
📅 毎月の予算設定
今月の全体予算を設定しますか？

[設定する]
[後でする]
```

`設定する` のPostback:

```text
action=start_monthly_budget_input
```

Render側の既存予算入力処理へ接続します。

手動テスト:

```text
testMonthlyBudgetNotice
```

旧名互換:

```text
triggerMonthlyBudgetNotice
testMonthlyNotice
```

トリガー作成:

```text
installMonthlyBudgetNoticeTrigger
```

この関数は `sendMonthlyBudgetNotice` の既存トリガーを削除してから、毎月1日6時台のトリガーを1つだけ作成します。

Apps Scriptプロジェクトのタイムゾーンは `Asia/Tokyo` にしてください。

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

チラシ通知対象:

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

通知上限は20件です。Notion元データは自動削除しません。

---

# チラシテスト関数

```text
testSummitShufooDeliveryIds
testSummitLifeFlyerParse
testSummitLifeFlyerSync
testTodaySummitFlyerNotification
applyLifeFlyerReviewsNow
```

---

# 推奨トリガー

```text
checkCardEmails                         1時間ごと
sendMonthlyBudgetNotice                 毎月1日6時台
runDailySummitLifeCalendarAutomation    毎日6時台
sendDailyMemoReminder                   毎日8時ごろ
sendDailyBudgetAlert                    毎日20時ごろ
sendDailyCardPendingReminder            毎日20〜21時ごろ
sendMonthEndCardCheck                   毎日21時ごろ
sendWeeklyFinanceReport                 毎週日曜20時ごろ
```

---

# GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。

今回の毎月予算通知を使う場合は、GitHub最新版の:

```text
gas/FinanceReports.gs
```

をApps Scriptへ丸ごと反映してください。

チラシ機能は:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

を反映します。

---

# トラブルシューティング

毎月予算通知が届かない:
- `testMonthlyBudgetNotice` を実行
- `LINE_USER_ID` / `LINE_CHANNEL_ACCESS_TOKEN` がScript Propertiesにあるか確認
- Apps Scriptのタイムゾーンを確認
- トリガー画面で `sendMonthlyBudgetNotice` を確認

`設定する` を押しても進まない:
- LINE WebhookがRender `/callback` へ届いているか確認
- Renderが起動しているか確認
- `action=start_monthly_budget_input` のPostback処理が動作しているか確認

チラシ異常:
- まず `testSummitShufooDeliveryIds`
- 必要時だけGemini解析テストを実行
