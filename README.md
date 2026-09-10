# LINE Notion Bot

LINE を入口に、家計簿・予算・カード利用通知・カード未処理キュー・メモ・Notion・Gemini AI・AI回答改善をまとめて扱う個人向けBotです。

現在は LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。Gemini は `AI 質問内容` と明示した場合だけ起動し、通常コマンドや未登録メッセージでは消費しません。

> 初期構築・環境変数・Notion DB の作成方法は [SETUP.md](./SETUP.md) を参照してください。
>
> GAS の詳細は [gas/README.md](./gas/README.md) を参照してください。

---

## 1. 主な機能

### 家計簿

```text
支出 1200 ラーメン
```

金額・店名を入力後、ジャンルと支払方法を LINE Flex Message から選択し、Notion 家計簿DBへ保存します。

### 家計簿ダッシュボード

```text
今月
```

今月の総支出、予算、残予算、消化率、残り日数、1日あたり使える金額、上位ジャンル、支払方法別集計を表示します。

### 予算

```text
予算 100000
予算 食費 30000
予算一覧
予算アラート
```

予算アラートは全体・ジャンル別について 80% / 90% / 100% を判定します。

### 週次レポート

```text
週次レポート
今週
```

直近7日とその前7日を比較し、支出額・件数・増減・上位ジャンルを表示します。

### 固定費

```text
固定費一覧
固定費
固定費追加 Netflix 1490 サブスク JCB
```

固定費マスタから今月分を一括登録できます。

### メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

削除は「候補選択 → 内容確認 → 削除」の2段階です。

### AI検索

```text
AI 今月の食費を分析して
```

`AI ` で始まる質問だけ Gemini を使用します。未登録コマンドはAIへ自動転送せず、「そのコマンドはありません」と案内してメニューを表示します。

### AI改善

```text
AI改善
```

直前のAI回答が期待と違った場合、本当はどう答えてほしかったかを聞き、AI改善ログDBへ保存します。次回の似た質問では関連する改善例を最大3件だけ参考にします。

---

## 2. クレジットカード利用通知と未処理キュー

通常の新規カード利用は次の流れです。

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
ジャンル選択
  ↓
家計簿DBへ保存
  ↓
未処理ページをアーカイブ
  ↓
次の未処理カードを自動表示
```

対応対象は JCB、三井住友カード、楽天カード、PayPayカードです。

通常監視は1時間ごとのGASトリガーを推奨し、実処理対象は直近2時間です。Gmail Message ID で重複を抑止し、メール本文に利用日があれば受信日より実利用日を優先します。

### 未処理キューの考え方

カード未処理DBは履歴DBではなく、一時キューです。ジャンル登録が成功した項目、または `登録しない` を選んだ項目は `archived=true` でアーカイブされ、通常のDB一覧・未処理検索から消えます。

```text
カード未処理
```

と送ると、残件数と最も古い未処理カードを表示します。1件処理するたびに次の未処理カードを自動表示します。

### 古い通知の二重登録防止

新しいキュー方式で送られたLINE通知には `pending_id` が含まれます。すでに保存またはスキップ済みで、その pending_id がアーカイブされている通知を後から押した場合、Bot は家計簿への再登録を止めます。

```text
このカード利用はすでに処理済みです。
古い通知からの二重登録は行いませんでした。
```

と案内し、未処理が残っていれば次の項目を表示します。

### 日次未処理リマインダー

`POST /api/card-pending-reminder` を1日1回呼びます。未処理が0件なら通知せず、残っているときだけ件数をLINE通知します。

GAS関数:

```text
sendDailyCardPendingReminder
```

---

## 3. 2026年9月のカード履歴バックフィル

`gas/Code.gs` に次の手動実行関数があります。

```text
backfillSeptember2026
```

2026年9月前後のメールを広めに検索し、本文から解析した実利用日が `2026-09` のものだけを未処理キューへ追加します。

過去分を一括で取り込む際は1件ごとのLINE通知を送らず、最後に新規追加件数だけ通知します。その後 `カード未処理` から古い順にジャンルを付けます。

2026年9月10日時点では9月11日以降のメールはまだ存在しないため、9月を完全に丸ごと取り込みたい場合は9月30日以降に再実行してください。楽天カードなど通知が遅れる可能性も考慮し、10月上旬にもう一度実行するのが安全です。

バックフィルは Gmail Message ID の再取り込みを抑止します。ただし、過去に別経路で家計簿へ手動登録済みの支出との完全照合までは行っていないため、既に登録済みのものが未処理に現れた場合は `登録しない` を選んでください。

---

## 4. AI検索の設計

AI質問は次のように処理します。

```text
AI 質問
  ↓
Python DB Router
  ↓
関連度の高い最大2DBだけNotionから取得
  ↓
AI改善ログから関連例をPythonで最大3件選択
  ↓
Gemini 最終回答 1回
  ↓
LINE向けプレーンテキスト整形
  ↓
LINE
```

DB選択と改善例検索には Gemini を使わないため、原則 `1 AI質問 = Gemini 1回` です。

DBルーターはDB用途、DBタイトル、プロパティ名、プロパティ型、質問文、日付表現を利用します。DBスキーマは約10分キャッシュします。

制限値:

```text
最大参照DB: 2
1DBあたり最大取得件数: 40
通常Notionコンテキスト: 約18,000文字まで
AIタイムアウト: 60秒
```

日付表現 `今日 / 昨日 / 今週 / 先週 / 今月 / 先月 / 今年` を認識し、日付プロパティがあるDBではNotion側で期間を絞ります。

### LINE向け整形

GeminiにはMarkdown禁止を指示し、返答後も `sanitize_for_line()` で `**`、`##`、コードフェンス、引用記号などを除去します。箇条書きは `・`、見出しは `【見出し】` を基本とします。

---

## 5. AI改善ログDB

推奨プロパティ:

| 名前 | 型 |
|---|---|
| `質問` | Title |
| `AI回答` | Rich text |
| `期待する回答` | Rich text |
| `登録日時` | Date |

Render:

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

このDBは通常のAI検索候補として `NOTION_DATABASE_IDS` に入れる必要はありません。

---

## 6. カード未処理DB

推奨プロパティ:

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

Render:

```text
NOTION_CARD_PENDING_DATABASE_ID
```

このDBも特殊用途のため `NOTION_DATABASE_IDS` へ重複登録する必要はありません。

---

## 7. UIの色ルール

Flex Message の色はボタンの順番ではなく操作の意味で決めます。

通常の前向きな操作・選択は `primary`（緑）です。メインメニュー、ジャンル選択、支払方法選択、店名変更などは緑にします。

キャンセル、登録しない、削除などのネガティブ・低頻度操作は `secondary`（色なし / 控えめ）にします。以前の「先頭1〜2個だけ緑」というルールは廃止しています。

ボタンは原則1列・全幅表示です。

---

## 8. 定期実行API

| API | 用途 | 認証 |
|---|---|---|
| `POST /api/daily-memo` | 日次メモ一覧 | `X-API-KEY` |
| `POST /api/budget-alert` | 予算アラート | `X-API-KEY` |
| `POST /api/weekly-report` | 週次レポート | `X-API-KEY` |
| `POST /api/card-pending` | カード未処理登録 | `X-API-KEY` |
| `POST /api/card-pending-notified` | 即時通知済み更新 | `X-API-KEY` |
| `POST /api/card-pending-reminder` | 未処理件数の日次通知 | `X-API-KEY` |
| `POST /api/register-fixed` | 固定費一括登録 | 現状要改善 |
| `POST /api/monthly-notice` | 月初予算案内 | 現状要改善 |

認証付きAPIは Render の `SCHEDULER_SECRET` と GAS Script Properties の同じ値を使います。

---

## 9. 主要環境変数

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

秘密鍵やアクセストークンはGitHubへ直接保存しないでください。

---

## 10. 推奨GASトリガー

```text
checkCardEmails
→ 1時間ごと

sendDailyMemoReminder
→ 毎日 朝8時ごろ

sendDailyBudgetAlert
→ 毎日 20時ごろ

sendDailyCardPendingReminder
→ 毎日 20時〜21時ごろ

sendWeeklyFinanceReport
→ 毎週日曜日 20時ごろ
```

---

## 11. ファイル構成

```text
line-notion-bot/
├── app.py
├── kakeibo.py
├── budget.py
├── insights.py
├── memo.py
├── menu.py
├── ui.py
├── card_queue.py
├── notion_helper.py
├── ai_engine.py
├── ai_feedback.py
├── README.md
├── SETUP.md
└── gas/
    ├── Code.gs
    ├── DailyMemo.gs
    ├── FinanceReports.gs
    └── README.md
```

---

## 12. 今後の改善候補

- 過去カードバックフィル時の家計簿DB完全重複チェック
- 固定費の二重登録防止
- 予算アラートの到達段階ごとの一度だけ通知
- `/api/register-fixed` と `/api/monthly-notice` の認証統一
- AI直前回答・`user_states` の永続化
- AI改善ログが増えた場合のベクトル検索

このREADMEは機能変更と同時に更新する方針です。
