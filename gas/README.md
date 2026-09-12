# GAS セットアップ

`gas/Code.gs` はGmailのカード利用通知、`gas/FinanceReports.gs` は家計簿の定期通知、`gas/DailyMemo.gs` はメモ通知、`gas/FlyerDeals.gs` はサミットのチラシ取得・Notion特売カレンダー同期・LINE日次通知を担当します。

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

## サミット特売Notionカレンダー

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

必要ファイルは1つです。

```text
gas/FlyerDeals.gs
```

処理:

```text
公式ページ / iframe / 公開フォールバックからチラシ候補を取得
↓
新しいチラシの時だけGeminiで画像認識
↓
商品名 / 価格 / 容量 / 特売期間を抽出
↓
Notion特売カレンダーDBへ同期
↓
Notionから今日の特売を読み直す
↓
LINEへ毎朝通知
```

Googleカレンダーは使いません。Notion DBが正本です。

### Notion DBプロパティ

| 名前 | 型 |
|---|---|
| `商品名` | Title |
| `特売日` | Date |
| `価格` | Rich text |
| `容量・単位` | Rich text |
| `店舗` | Select |
| `備考` | Rich text |
| `優先度` | Number |
| `チラシURL` | URL |
| `チラシ識別` | Rich text |
| `識別キー` | Rich text |
| `有効` | Checkbox |
| `更新日時` | Date |

`特売日`を使ったカレンダービューを追加してください。

### 初回テスト

解析だけ:

```text
testSummitFlyerParse
```

Notion同期 + LINE通知:

```text
testSummitFlyerAutomation
```

Notion登録済みデータだけで通知:

```text
testTodaySummitFlyerNotification
```

### 毎日自動実行

一度だけ:

```text
installDailySummitFlyerTrigger
```

毎日6時台に `runDailySummitFlyerAutomation` を実行します。

### 重複と古いチラシ

同じ `店舗 + 商品 + 価格 + 容量 + 特売期間` は `識別キー` で更新扱いにします。

新しいチラシへ切り替わった場合、今日以降に残る旧チラシ行は `有効=false` にします。過去の行は履歴として残します。

同じチラシの間はキャッシュを再利用し、毎朝同じ画像をGeminiへ送り直しません。

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

## 定期通知

```text
runDailySummitFlyerAutomation → 毎日6時台
sendDailyMemoReminder         → 毎日朝8時ごろ
sendDailyBudgetAlert          → 毎日20時ごろ
sendDailyCardPendingReminder  → 毎日20〜21時ごろ
sendMonthEndCardCheck         → 毎日21時ごろ
sendWeeklyFinanceReport       → 毎週日曜20時ごろ
```

---

## GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。今回コピーするのは:

```text
gas/FlyerDeals.gs
```

---

## トラブルシューティング

チラシ解析0件:
- `testSummitFlyerParse`のログを確認
- `GEMINI_API_KEY` / `FLYER_GEMINI_MODEL`を確認

Notion同期失敗:
- `NOTION_API_KEY`
- `NOTION_FLYER_DATABASE_ID`
- Integrationが特売DBへ接続済みか
- DBプロパティ名・型が上表と完全一致しているか

LINE通知失敗:
- `LINE_USER_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`

詳細は`FLYER_TEST.md`を参照してください。
