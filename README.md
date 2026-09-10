# LINE Notion Bot

LINE を入口に、家計簿・予算・カード利用通知・カード未処理キュー・メモ・Notion・Gemini AI・AI回答改善をまとめて扱う個人向けBotです。

現在は LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。Gemini は `AI 質問内容` と明示した場合だけ起動し、通常コマンドや未登録メッセージでは消費しません。

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

GeminiのMarkdown記号はLINE送信前に除去します。

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

### LINE Postback 300文字対策

2026-09-11に、長い日本語店名を含むカードで次のエラーが発生しました。

```text
ValidationError: PostbackAction data
ensure this value has at most 300 characters
```

原因は、ジャンルボタンのPostbackにカード名・店名・金額・日付・ジャンル・pending_idをすべて埋め込んでいたことです。

現在は、未処理カードのボタンでは次のように最小限の値だけ送ります。

```text
ジャンル選択:
action + pending_id + category

店名変更:
action + pending_id
```

押された後に `app.py` が `card_queue.get_item(pending_id)` でNotionからカード名・店名・金額・日付を再取得します。これにより長い店名でもPostbackの300文字上限を超えにくくなっています。

この障害で未処理DBのデータ自体は壊れません。Render再デプロイ後に `カード未処理` から残りをそのまま続けられます。

### 二重登録防止

新方式の通知には `pending_id` が含まれます。保存済み・スキップ済みの古い通知を押した場合は、家計簿へ再登録せず次の未処理へ進みます。

### 日次未処理リマインダー

`sendDailyCardPendingReminder` を1日1回実行し、未処理がある場合だけ件数をLINE通知します。

---

## 2026年9月のカード履歴バックフィル

GASで次を手動実行します。

```text
backfillSeptember2026
```

2026年9月前後のメールを広めに検索し、本文から解析した利用日が `2026-09` のものだけを未処理キューへ追加します。過去分は1件ずつLINE通知せず、最後に追加件数だけ通知します。

途中まで処理済みでも、残った未処理だけ続けられます。

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

カード未処理DBの推奨プロパティ:

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

タイトル列はコードが自動検出できますが、管理上は `GmailMessageID` を推奨します。

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

秘密値はGitHubへ直接保存しません。

---

## GAS推奨トリガー

```text
checkCardEmails
→ 1時間ごと

sendDailyMemoReminder
→ 毎日 朝8時ごろ

sendDailyBudgetAlert
→ 毎日 20時ごろ

sendDailyCardPendingReminder
→ 毎日 20〜21時ごろ

sendWeeklyFinanceReport
→ 毎週日曜日 20時ごろ
```

---

## 開発中の大規模拡張

今後追加する48機能は `DEVELOPMENT.md` で7フェーズに分けて管理しています。現在はPhase 1「カード入力の自動化」を進行中です。

基盤として `card_rules.py` を追加済みですが、カード学習機能はまだLINEフローへ接続していないため現時点では利用できません。

次の開発再開位置も `DEVELOPMENT.md` に固定しています。

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
7. GASへGitHubの最新版をコピーしたか

LINE UIを変更するときは `UI_DESIGN.md` のPostback 300文字ルールも必ず確認してください。
