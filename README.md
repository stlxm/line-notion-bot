# LINE Notion Bot

LINE を入口に、家計簿・予算・カード利用通知・カード未処理キュー・固定費/サブスク・メモ・Notion・Gemini AI をまとめて扱う個人向けBotです。

現在は LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。Gemini は `AI 質問内容` と明示した場合だけ起動します。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: AIなしでも行える日常保守、障害切り分け、復旧手順
- `DEVELOPMENT.md`: 長期開発ロードマップ、完了状況、次回の再開位置
- `UI_DESIGN.md`: LINEメニュー、ボタン色、画面構成、Postback設計ルール
- `gas/README.md`: GAS固有の設定とカード通知

機能変更時は README.md / SETUP.md / DEVELOPMENT.md を同時更新し、UI変更時は UI_DESIGN.md も更新します。

---

## 現在の主な機能

### 家計簿

```text
支出 1200 ラーメン
```

金額・店名を入力後、ジャンルと支払方法をLINE上で選び、Notion家計簿DBへ保存します。

### 家計簿ダッシュボード / 予算

```text
今月
予算一覧
予算アラート
週次レポート
予算 100000
予算 食費 30000
```

今月の総支出、予算、残額、消化率、1日あたり使える額、ジャンル別集計などを確認できます。

### 固定費

```text
固定費一覧
固定費
固定費追加 Netflix 1490 サブスク JCB
```

### メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

### AI検索 / AI改善

```text
AI 今月の食費を分析して
AI改善
```

AI検索は明示的に `AI ` を付けた場合だけGeminiを使います。回答が期待と違った場合は `AI改善` で質問・実回答・期待回答をNotionへ保存し、似た質問の改善に利用します。

---

## クレジットカード利用通知と未処理キュー

通常の流れ:

```text
カード会社メール
↓
Gmail
↓
GAS / checkCardEmails
↓
Render /api/card-pending
↓
Notion カード未処理DBへ一時保存
↓
LINEへ即時通知
↓
ジャンル選択 / 店名変更 / 登録しない
↓
家計簿保存 または スキップ
↓
未処理ページをアーカイブ
↓
次の未処理を自動表示
```

対応対象は JCB、三井住友カード、楽天カード、PayPayカードです。

`カード未処理` と送ると古いものから1件ずつ処理できます。途中でやめても未処理だけNotionに残るため、後から続きから再開できます。

カードのジャンルは2列、通常操作は緑、`登録しない` は控えめな表示です。店名変更も未処理画面から利用できます。

### サブスク登録

カード未処理のジャンルには `サブスク` を表示します。`固定費` はカード未処理のジャンル一覧には表示しません。

`サブスク` を選んだ場合:

```text
サブスクを選択
↓
固定費DBへ登録または更新
↓
今回分を家計簿DBへ保存
↓
未処理キューからアーカイブ
↓
次回以降、同じカード + 同じ正規化店名はカード検出から除外
```

固定費DBに同じカード・同じ店が既にある場合は重複作成せず、既存レコードの金額・ジャンル・有効状態を更新します。

除外条件は `カード名 + 正規化した店名` です。金額が同じだけでは除外しません。

除外を解除したい場合はNotion固定費DBで該当レコードの `有効` をOFFにしてください。次回以降、通常のカード検出対象へ戻ります。

既にカード未処理DBへ入っている過去分は自動削除しません。必要ならそのまま処理してください。

### LINE Postback 300文字対策

未処理カードのボタンでは、長い店名をPostbackへ埋め込まず `pending_id` と必要最小限の値だけ送信します。押された後にRenderがNotion未処理DBから実データを再取得します。

### 二重登録防止

保存済み・スキップ済みの古い通知を押した場合は、`pending_id` を確認して家計簿へ再登録しません。

### 日次未処理リマインダー

`sendDailyCardPendingReminder` を1日1回実行し、未処理がある場合だけ件数をLINE通知します。

---

## 2026年9月カード履歴バックフィル

GASで次を手動実行します。

```text
backfillSeptember2026
```

2026年9月前後のメールを広めに検索し、本文から解析した利用日が `2026-09` のものだけを未処理キューへ追加します。過去分は1件ずつLINE通知せず、最後に追加件数だけ通知します。

---

## Notion DB

主な専用DB:

```text
家計簿
月別管理
固定費
メモ
URL保存
AI改善ログ
カード未処理
```

### 固定費DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

サブスクをカード未処理から登録すると、このDBへ `ジャンル=サブスク`、`有効=true` で保存されます。

### カード未処理DB

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

環境変数:

```text
NOTION_CARD_PENDING_DATABASE_ID
```

---

## 主なRender環境変数

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
NOTION_API_KEY
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
NOTION_DATABASE_IDS
NOTION_PAGE_URL
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
```

---

## GAS推奨トリガー

```text
checkCardEmails              → 1時間ごと
sendDailyMemoReminder        → 毎日 朝8時ごろ
sendDailyBudgetAlert         → 毎日 20時ごろ
sendDailyCardPendingReminder → 毎日 20〜21時ごろ
sendWeeklyFinanceReport      → 毎週日曜日 20時ごろ
```

---

## 開発中の大規模拡張

今後追加する機能は `DEVELOPMENT.md` でフェーズ管理しています。現在はPhase 1「カード入力の自動化」を進行中です。

---

## 保守

不具合時は `MAINTENANCE.md` を参照してください。

最短確認順:

1. Renderの最新デプロイが成功しているか
2. Render Logsに例外がないか
3. GAS実行履歴にエラーがないか
4. Notion DB列名・型がSETUP.mdと一致しているか
5. Notion Integrationが対象DBへ接続されているか
6. GASとRenderの `SCHEDULER_SECRET` が一致しているか
7. GASへGitHub最新版をコピーしたか
