# LINE Notion Bot

LINE を入口に、**家計簿・予算管理・クレジットカード利用通知・メモ・Notion データ登録・AI検索・AI回答改善**をまとめて扱う個人向けアシスタントです。

現在は LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。通常機能はコマンドで実行し、Gemini は `AI 質問内容` と明示したときだけ使用します。

> 初期構築・環境変数・Notion DB の作成方法は [SETUP.md](./SETUP.md) を参照してください。
>
> Google Apps Script の詳細は [gas/README.md](./gas/README.md) も参照してください。

---

## 1. 基本方針

この Bot は次の3系統を明確に分離しています。

1. **通常コマンド**: 家計簿、予算、メモ、固定費、Notion 登録など。Gemini は使いません。
2. **AI検索**: `AI ` で始まる質問だけ Gemini を使用します。
3. **AI改善**: 直前のAI回答が期待と違った場合、`AI改善` で改善内容を Notion に蓄積します。

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

Gmail に届いたカード利用メールを GAS が定期確認し、LINE へ Flex Message を直接 Push します。

対応対象:

- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

推奨運用:

- GAS: 1時間ごと
- 実処理対象: 直近2時間
- 既読・未読ではなく Gmail Message ID で重複防止
- 本文に実利用日がある場合はメール受信日より優先

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

AI質問を受けると、Python が Notion の DB タイトル・用途・プロパティ名・プロパティ型と質問文を比較し、**必要性が高い最大2DBだけ**を取得します。

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
LINE
```

これにより、旧構成の「DB選択でGemini 1回 + 回答でGemini 1回」から、原則 **1質問 = Gemini 1回** になっています。

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

60秒は Gemini / Notion の一時的な遅延やリトライに備える安全弁として残しています。

---

## 4. AI回答改善ループ

AI回答が期待と違った場合、ユーザー自身の修正内容を Notion に保存し、その後の似た質問で回答品質を改善できます。

### 使い方

まず通常どおりAIへ質問します。

```text
AI ○○について教えて
```

回答がおかしい、回答できなかった、観点が違う、説明方法が違う場合:

```text
AI改善
```

Bot は直前の質問とAI回答を表示し、

```text
本当はどのように答えてほしかったですか？
```

と尋ねます。

そこで例えば、

```text
家計簿DBだけではなく月別管理DBも見て、予算との差額まで出してほしかった。
金額は最後に表でまとめてほしい。
```

と送ると、専用の `AI改善ログ` DB に保存します。

### 保存内容

AI改善ログ DB:

| プロパティ | 型 | 内容 |
|---|---|---|
| `質問` | Title | ユーザーが最初に送ったAI質問 |
| `AI回答` | Rich text | 実際に返した回答 |
| `期待する回答` | Rich text | 本当はどう答えてほしかったか |
| `登録日時` | Date | 改善ログ登録日時 |

Render 環境変数:

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

### 次回以降の利用方法

次の AI 質問時に `ai_feedback.py` が改善ログ DB から最大100件を取得し、質問の文字列類似度を Python で計算します。

関連度の高い改善例を最大3件だけ Gemini の最終プロンプトへ追加します。

重要な点:

- 改善例の検索に Gemini は使わない
- Gemini API回数は増えない
- 過去の「期待する回答」を回答スタイル・観点・粒度の参考にする
- 過去例の事実そのものを今回の事実として流用しない
- 今回取得した Notion データを優先する

つまり、単純な会話履歴ではなく、**ユーザーが明示的に訂正した良質な教師データだけを使う**構成です。

### 注意点

直前のAI質問と回答は Render プロセスのメモリに一時保持しています。`AI改善` を実行して期待回答を保存した時点で Notion に永続化されます。

Render が「AI回答 → AI改善」の間に再起動した場合、直前回答を特定できないことがあります。この部分は将来 Redis / Notion 一時ログ等へ永続化する改善余地があります。

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
```

それ以外のAI検索・汎用登録対象DBは:

```text
NOTION_DATABASE_IDS
```

にカンマ区切りで指定します。

専用IDと追加IDはコード側で統合し、重複を除去します。

`NOTION_AI_FEEDBACK_DATABASE_ID` は特殊用途のため、通常のAIデータ検索候補には混ぜず、改善例として別ルートで利用します。

---

## 6. メインメニュー

```text
メニュー
機能
機能一覧
```

原則1列・全幅の Flex Message で表示します。

AI欄には:

- AI検索の使い方
- 直前のAI回答を改善

を表示します。

---

## 7. 定期実行API

| API | 用途 | 認証 |
|---|---|---|
| `POST /api/daily-memo` | 日次メモ一覧 | `X-API-KEY` |
| `POST /api/budget-alert` | 予算アラート | `X-API-KEY` |
| `POST /api/weekly-report` | 週次レポート | `X-API-KEY` |
| `POST /api/register-fixed` | 固定費一括登録 | 現状要改善 |
| `POST /api/monthly-notice` | 月初予算案内 | 現状要改善 |

認証付きAPIは Render の `SCHEDULER_SECRET` と GAS Script Properties の同名値を一致させます。

---

## 8. ファイル構成

```text
line-notion-bot/
├── app.py                 # Flask / LINEルーティング / コマンド処理
├── kakeibo.py             # 家計簿・予算・固定費
├── budget.py              # 月次予算集計
├── insights.py            # ダッシュボード・アラート・週次レポート
├── memo.py                # メモ
├── menu.py                # メインメニュー
├── ui.py                  # 読みやすいFlex UI
├── notion_helper.py       # Notionアクセス・DBルーター
├── ai_engine.py           # Notion + 改善例 + Gemini最終回答
├── ai_feedback.py         # AI改善ログ保存・類似例検索
├── prompt.txt
├── requirements.txt
├── README.md
├── SETUP.md
└── gas/
    ├── Code.gs
    ├── DailyMemo.gs
    ├── FinanceReports.gs
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
NOTION_DATABASE_IDS
NOTION_PAGE_URL
ADMIN_USER_ID
SCHEDULER_SECRET
```

秘密鍵・アクセストークンは GitHub に直接記載しないでください。

---

## 10. AI改善の動作確認

```text
AI 今月の食費を説明して
```

AI回答後:

```text
AI改善
```

Bot の質問に対して:

```text
予算と比較して、残額と今月あと1日いくら使えるかまで説明してほしかった
```

Notion の AI改善ログ DB に1件追加されれば成功です。

その後、似た質問を再度送ると関連する改善例が最終プロンプトに含まれます。

---

## 11. 今後の改善候補

- AI直前回答の永続化（Render再起動対策）
- AI改善ログの「良い / 不要」評価
- 改善ログ件数が増えた場合のベクトル検索
- 予算アラートを80/90/100%到達時に一度だけ通知
- 固定費の完全な重複登録防止
- 定期APIの認証統一
- `user_states` の Redis 等への永続化

この README は機能変更と同時に更新する方針です。
