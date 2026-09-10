# LINE Notion Bot

LINE を入口に、**家計簿・予算管理・クレジットカード利用通知・カード未処理キュー・メモ・Notion データ登録・AI検索・AI回答改善**をまとめて扱う個人向けアシスタントです。

現在は LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。通常機能はコマンドで実行し、Gemini は `AI 質問内容` と明示したときだけ使用します。

> 初期構築・環境変数・Notion DB の作成方法は [SETUP.md](./SETUP.md) を参照してください。
>
> Google Apps Script の詳細は [gas/README.md](./gas/README.md) も参照してください。

---

## 1. 基本方針

この Bot は次の機能群を分離して動かしています。

1. **通常コマンド**: 家計簿、予算、カード未処理、メモ、固定費、Notion 登録など。Gemini は使いません。
2. **AI検索**: `AI ` で始まる質問だけ Gemini を使用します。
3. **AI改善**: 直前のAI回答が期待と違った場合、`AI改善` で改善内容を Notion に蓄積します。
4. **定期処理**: GAS から Render の認証付きAPIを呼び、日次メモ・予算アラート・週次レポート・カード未処理件数を通知します。

未登録コマンドは Gemini に送らず、

```text
そのコマンドはありません。メニューから機能を選んでください。
```

と案内し、メニューを表示します。

---

## 2. 主な機能

### 家計簿

```text
支出 1200 ラーメン
支出 500 コンビニ
```

Notion の家計簿 DB に支出を保存します。ジャンルと支払方法は LINE 上で選択できます。

### クレジットカード利用通知

Gmail に届いたカード利用メールを GAS が定期確認します。

通常フロー:

```text
カード利用メール
  ↓
GAS
  ↓
Render /api/card-pending
  ↓
Notion カード未処理DBへ一時保存
  ↓
LINEへ利用通知
  ↓
ジャンル選択
  ↓
家計簿DBへ保存
  ↓
未処理DBの該当ページをアーカイブ
  ↓
次の未処理カードを自動表示
```

対応対象:

- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

推奨運用:

- GAS: 1時間ごと
- 実処理対象: 直近2時間
- Gmail Message ID で重複通知を抑止
- 本文に実利用日がある場合はメール受信日より優先

### カード未処理キュー

カード利用は検知時点で LINE 通知しますが、ジャンルをその場で選ばなくても未処理DBに残ります。

```text
カード未処理
```

と送ると、現在の未処理件数を表示し、古いものから1件ずつ処理できます。

1件のジャンル登録が成功すると、その項目は未処理DBからアーカイブされ、次の1件を自動表示します。

`登録しない` を選んだ場合も未処理DBからアーカイブされ、家計簿には保存せず次へ進みます。

未処理DBは履歴保存先ではなく、**処理待ちだけを置く一時キュー**です。

### カード未処理の日次通知

1日1回 `POST /api/card-pending-reminder` を呼び、未処理が残っている場合だけ件数を通知できます。

GAS 関数:

```text
sendDailyCardPendingReminder
```

未処理0件なら通知しません。

### 2026年9月のカード履歴バックフィル

`gas/Code.gs` に次の手動実行関数があります。

```text
backfillSeptember2026
```

2026年9月の利用メール候補をまとめて検索し、実利用日が9月のものだけをカード未処理DBへ追加します。

過去分を一括取り込みすると LINE 通知が大量に並ぶため、バックフィルでは1件ごとの通知は送らず、最後に追加件数だけ通知します。

その後 `カード未処理` から1件ずつジャンルを登録できます。

2026年9月10日時点で実行した場合、9月11日以降の未来の利用メールはまだ存在しないため、9月を完全に丸ごと取り込むには9月終了後にも再実行する必要があります。遅れて届くカード会社メールも考慮するなら10月上旬の再実行が安全です。

### 予算管理

```text
予算 100000
予算 食費 30000
予算一覧
```

全体予算・ジャンル別予算・支出・残額を管理します。

### 家計簿ダッシュボード

```text
今月
```

表示内容:

- 今月の総支出
- 全体予算
- 残予算
- 予算消化率
- 月末までの日数
- 1日あたり使える金額
- 支出上位ジャンル
- 支払方法別集計

### 予算アラート

```text
予算アラート
```

全体予算・ジャンル別予算について 80% / 90% / 100% を判定します。

### 週次レポート

```text
週次レポート
今週
```

直近7日間とその前7日間を比較します。

### 固定費

```text
固定費一覧
固定費
固定費追加 Netflix 1490 サブスク JCB
```

Notion の固定費マスタから一括登録できます。

### メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

削除は「候補選択 → 確認 → 削除」の2段階です。

### 日次メモ通知

`gas/DailyMemo.gs` から `/api/daily-memo` を呼び、1日1回メモ一覧を LINE に送れます。

### Notion 汎用データ追加

```text
データ追加
```

専用 DB ID と `NOTION_DATABASE_IDS` を統合した一覧から登録先を選び、対話形式でページを作成します。

### URL保存

http / https から始まる URL を送ると `NOTION_URL_DATABASE_ID` の DB へ保存します。

---

## 3. AI検索

### 起動方法

Gemini を使うのは次の形式だけです。

```text
AI 今月の食費を分析して
AI メモの内容を整理して
AI 最近の支出傾向を教えて
```

`AI` だけ送ると使い方だけ表示し、Gemini API は消費しません。

### AIルーティング

AI質問を受けると、Python が Notion の DB タイトル・用途・プロパティ名・プロパティ型と質問文を比較し、必要性が高い最大2DBだけを取得します。

DB選択には Gemini を使いません。

```text
AI 質問
  ↓
Python DB Router
  ↓
必要な最大2DBだけNotionから取得
  ↓
関連する過去のAI改善例を最大3件取得
  ↓
Gemini 最終回答 1回
  ↓
LINE向けプレーンテキスト整形
  ↓
LINE
```

原則 **1質問 = Gemini 1回** です。

### 日付フィルター

以下の表現を質問から認識し、Notion 側で期間を絞ります。

- 今日
- 昨日
- 今週
- 先週
- 今月
- 先月
- 今年

### キャッシュ・制限

- DBスキーマキャッシュ: 10分
- 最大参照DB: 2
- 1DBあたり最大取得件数: 40
- Geminiへ渡す通常Notionコンテキスト: 最大約18,000文字
- AI処理タイムアウト: 60秒

60秒は Gemini / Notion の一時的な遅延やリトライに備える安全弁として維持しています。

### LINE向けプレーンテキスト出力

Gemini の Markdown 記法は LINE 上では装飾されず、そのまま `**` や `##` と表示されるため、回答はプレーンテキストへ正規化します。

対策:

1. Geminiへのプロンプトで Markdown を使わないよう指示
2. `ai_engine.py` の `sanitize_for_line()` で返答後にも記号を除去

主な変換:

- `#` / `##` / `###` → 見出し記号を除去
- `**` / `__` → 装飾記号を除去
- バッククォート / コードフェンス → 除去
- `>` → 引用記号を除去
- `~~` → 取り消し線記号を除去
- Markdownリンク → 通常テキスト表記
- `-` / `*` / `+` の箇条書き → `・`

---

## 4. AI回答改善ループ

AI回答が期待と違った場合、ユーザー自身の修正内容を Notion に保存し、その後の似た質問で回答品質を改善できます。

```text
AI ○○について教えて
  ↓
AI回答
  ↓
AI改善
  ↓
「本当はどのように答えてほしかったですか？」
  ↓
期待する回答を入力
  ↓
AI改善ログDBへ保存
```

AI改善ログ DB:

| プロパティ | 型 | 内容 |
|---|---|---|
| `質問` | Title | 元のAI質問 |
| `AI回答` | Rich text | 実際に返した回答 |
| `期待する回答` | Rich text | 本当はどう答えてほしかったか |
| `登録日時` | Date | 改善ログ登録日時 |

Render 環境変数:

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

次回のAI質問時は最大100件の改善ログから Python で類似度を計算し、関連度の高い最大3件だけを最終プロンプトへ追加します。改善例検索には Gemini を使わないため、API回数は増えません。

過去改善例は回答の構成・観点・粒度の参考として使い、過去の数字や事実を現在の事実として流用しないよう Gemini に指示しています。

---

## 5. Notion DB の管理方針

専用DBは専用環境変数で設定します。

```text
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
```

それ以外のAI検索・汎用登録対象DBは:

```text
NOTION_DATABASE_IDS
```

にカンマ区切りで指定します。

`NOTION_AI_FEEDBACK_DATABASE_ID` と `NOTION_CARD_PENDING_DATABASE_ID` は特殊用途なので、通常のAI検索候補として `NOTION_DATABASE_IDS` に重複登録する必要はありません。

カード未処理DBは処理待ちデータだけを一時保存し、保存またはスキップ後はアーカイブします。

---

## 6. メインメニューと選択UI

```text
メニュー
機能
機能一覧
```

原則1列・全幅の Flex Message で表示します。

### ボタン色のルール

色は順番ではなく、操作の意味で決めます。

- 通常の実行・選択・次へ進む操作: `primary` / 緑
- ジャンル選択: 緑
- 支払方法選択: 緑
- 店名変更: 緑
- メインメニューの通常機能: 緑
- キャンセル: `secondary` / 色なし
- 登録しない: `secondary` / 色なし
- 削除系などネガティブな操作: 控えめな色なし表示

以前の「先頭1〜2個だけ緑」というルールは廃止しました。

メニューには `カード未処理を確認` も追加しています。

---

## 7. 定期実行API

| API | 用途 | 認証 |
|---|---|---|
| `POST /api/daily-memo` | 日次メモ一覧 | `X-API-KEY` |
| `POST /api/budget-alert` | 予算アラート | `X-API-KEY` |
| `POST /api/weekly-report` | 週次レポート | `X-API-KEY` |
| `POST /api/card-pending` | カード未処理キューへ登録 | `X-API-KEY` |
| `POST /api/card-pending-notified` | カード即時通知済み更新 | `X-API-KEY` |
| `POST /api/card-pending-reminder` | 未処理件数の日次通知 | `X-API-KEY` |
| `POST /api/register-fixed` | 固定費一括登録 | 現状要改善 |
| `POST /api/monthly-notice` | 月初予算案内 | 現状要改善 |

認証付きAPIは Render の `SCHEDULER_SECRET` と GAS Script Properties の同名値を一致させます。

---

## 8. ファイル構成

```text
line-notion-bot/
├── app.py                 # Flask / LINEルーティング / コマンド処理 / カードキューAPI
├── kakeibo.py             # 家計簿・予算・固定費
├── budget.py              # 月次予算集計
├── insights.py            # ダッシュボード・アラート・週次レポート
├── memo.py                # メモ
├── menu.py                # メインメニュー
├── ui.py                  # Flex UI / カードジャンル選択
├── card_queue.py          # カード未処理キュー / アーカイブ処理
├── notion_helper.py       # Notionアクセス・DBルーター
├── ai_engine.py           # Notion + 改善例 + Gemini最終回答 + LINE向け整形
├── ai_feedback.py         # AI改善ログ保存・類似例検索
├── prompt.txt
├── requirements.txt
├── README.md
├── SETUP.md
└── gas/
    ├── Code.gs            # カード監視・即時通知・月次バックフィル
    ├── DailyMemo.gs
    ├── FinanceReports.gs  # 予算・週次・カード未処理件数通知
    └── README.md
```

---

## 9. 主要環境変数

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GEMINI_API_KEY
GEMINI_MODEL
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
ADMIN_USER_ID
SCHEDULER_SECRET
```

秘密鍵・アクセストークンは GitHub に直接記載しないでください。

---

## 10. 推奨トリガー

例:

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

カード未処理件数通知は、未処理が0件なら送信しません。

---

## 11. 今後の改善候補

- 過去カードバックフィル時の家計簿DB完全重複チェック
- AI直前回答の永続化（Render再起動対策）
- AI改善ログの「良い / 不要」評価
- 改善ログ件数が増えた場合のベクトル検索
- 予算アラートを80/90/100%到達時に一度だけ通知
- 固定費の完全な重複登録防止
- 定期APIの認証統一
- `user_states` の Redis 等への永続化

この README は機能変更と同時に更新する方針です。
