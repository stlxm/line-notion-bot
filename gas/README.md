# GAS セットアップ

`gas/Code.gs` はGmailのカード利用通知を検出し、Render経由でカード自動化を実行します。`gas/FinanceReports.gs` は未処理通知・月末チェック・予算/週次通知を担当します。`gas/FlyerDeals.gs` と `gas/FlyerNotion.gs` はサミットのチラシ取得・Notion特売カレンダー同期・LINE日次通知を担当します。

## 共通 Script Properties

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

チラシ機能では追加で:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密情報はソースコードへ直接書かないでください。

---

## 通常カード監視

```text
checkCardEmails → 1時間ごと
```

Gmail Message IDで同一メールの再処理を抑止します。

対応カード:
- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

---

## サミット特売Notionカレンダー

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

必要ファイル:

```text
gas/FlyerDeals.gs
gas/FlyerNotion.gs
```

役割:

```text
FlyerDeals.gs
  → 公式ページ/チラシ画像取得
  → 必要時トクバイへフォールバック
  → Geminiで商品・価格・対象日を抽出

FlyerNotion.gs
  → 期限切れページをアーカイブ
  → Notion特売カレンダーDBへ同期
  → 今日の特売をLINE通知
```

### 初回テスト

```text
testSummitFlyerParse
```

解析のみ。

```text
testSummitFlyerNotionSyncOnly
```

Notion同期のみ。

```text
testSummitFlyerNotionAutomation
```

Notion同期 + LINE通知。

### 毎日自動実行

一度だけ:

```text
installDailySummitFlyerNotionTrigger
```

旧Googleカレンダー版の `runDailySummitFlyerAutomation` トリガーが残っていれば削除し、Notion版 `runDailySummitFlyerNotionAutomation` を毎日6時台に作成します。

### 期限切れ整理

日次処理の最初に自動で行います。手動実行も可能です。

```text
cleanupExpiredSummitFlyerPages
```

`特売日`の終了日が今日より前ならNotionページを`archived=true`へ変更します。通常のDB/カレンダービューからは消えます。

---

## 日次未処理通知

```text
sendDailyCardPendingReminder → 毎日20〜21時ごろ
```

未処理0件なら通知しません。

## 月末未処理チェック

```text
sendMonthEndCardCheck → 毎日21時ごろ
```

Render側で月末か判定します。

## その他のFinanceReportsトリガー

```text
sendDailyBudgetAlert    → 毎日20時ごろ
sendWeeklyFinanceReport → 毎週日曜20時ごろ
```

---

## GASとGitHubの同期

GitHubの`.gs`を更新しても通常のApps Scriptプロジェクトへ自動反映されません。

今回チラシ機能でコピーするファイル:

```text
gas/FlyerDeals.gs
gas/FlyerNotion.gs
```

カード関連変更時は`gas/Code.gs`、定期通知変更時は`gas/FinanceReports.gs`もコピーします。

---

## トラブルシューティング

チラシNotion同期が失敗:
- `NOTION_API_KEY`を確認
- `NOTION_FLYER_DATABASE_ID`を確認
- Integrationを特売DBへ接続
- DBのプロパティ名/型を`SETUP.md`と照合

チラシ解析0件:
- `testSummitFlyerParse`のログを確認
- `GEMINI_API_KEY` / `FLYER_GEMINI_MODEL`を確認

LINE通知失敗:
- `LINE_USER_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`

Phase 1全体は`PHASE1_TEST.md`、チラシは`FLYER_TEST.md`を参照してください。
