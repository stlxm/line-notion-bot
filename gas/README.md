# GAS カード利用通知セットアップ

`gas/Code.gs` はGmailのカード利用通知を検出し、Render経由でカード自動化を実行します。`gas/FinanceReports.gs` は未処理通知・月末チェック・予算/週次通知を担当します。

## Script Properties

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

秘密情報はソースコードへ直接書かないでください。

## 通常カード監視

```text
checkCardEmails → 1時間ごと
```

Gmail検索は広めに行い、コード内部で直近2時間を処理します。Gmail Message IDで同一メールの再処理を抑止します。

対応カード:
- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

カード会社メール本文に利用日があれば受信日より利用日を優先します。

## Render側で行うPhase 1処理

GASはカード情報を`/api/card-pending`へ送ります。その後の判断はRender側です。

```text
固定費/サブスク除外
↓
重複候補・既存未処理の照合
↓
自動登録条件を満たせば家計簿へ自動保存
↓
それ以外はカード未処理DBへ保存
↓
LINE通知
```

Phase 1の学習・自動登録にはRender側の`NOTION_CARD_RULES_DATABASE_ID`が必要です。これはGAS Script Propertyではありません。

## 日次未処理通知

```text
sendDailyCardPendingReminder → 毎日20〜21時ごろ
```

未処理0件なら通知しません。

## 月末未処理チェック

最新版`gas/FinanceReports.gs`には次があります。

```text
sendMonthEndCardCheck
```

推奨:

```text
時間主導型
1日1回
21時ごろ
```

毎日実行して構いません。Renderの`/api/card-month-end-check`が月末か判定し、月末以外は何も通知しません。

月末だけ:

```text
未処理0件 → カード分類完了通知
未処理あり → 残件数警告
```

## その他のFinanceReportsトリガー

```text
sendDailyBudgetAlert    → 毎日20時ごろ
sendWeeklyFinanceReport → 毎週日曜20時ごろ
```

## 2026年9月バックフィル

Apps Scriptで一度だけ:

```text
backfillSeptember2026
```

利用日が2026年9月のカードメールを未処理へ追加します。過去取り込みでは個別LINE通知を大量送信せず、最後に追加件数のみ通知します。

Phase 1導入後はRender側でも重複・固定費・自動分類ルールが働きます。

## GASとGitHubの同期

GitHubの`.gs`を更新しても通常のApps Scriptプロジェクトへ自動反映されません。

今回必ずApps Scriptへコピーするファイル:

```text
gas/FinanceReports.gs
```

カードメール解析ロジックを更新した場合は`gas/Code.gs`もコピーします。

## トラブルシューティング

GASログで正常時:

```text
[解析成功]
[Render] /api/card-pending: 200
LINEレスポンス: 200
```

401:
- GASとRenderの`SCHEDULER_SECRET`が一致しているか確認。

500:
- Render Logsの最初のTracebackを確認。
- Notion DBのプロパティ名・型を`SETUP.md`と照合。

カード学習が動かない:
- Renderの`NOTION_CARD_RULES_DATABASE_ID`を確認。
- Notion Integrationがカード学習ルールDBへ接続されているか確認。

Phase 1全体の確認手順は`PHASE1_TEST.md`を参照してください。
