# LINE Notion Bot

LINE を入口に、**家計簿・予算管理・クレジットカード利用通知・メモ・Notion データ登録・AI検索**をまとめて扱う個人向けアシスタントです。

現在の構成では LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。通常機能はコマンドで動作し、AI は `AI 質問内容` と明示したときだけ起動します。

> 初期構築・環境変数・GAS設定は [SETUP.md](./SETUP.md) を参照してください。
>
> GAS の詳細は [gas/README.md](./gas/README.md) を参照してください。

---

## 1. 重要な操作ルール

### 通常機能

家計簿、予算、固定費、メモ、Notion登録などは決められたコマンドで実行します。

```text
メニュー
今月
週次レポート
予算一覧
メモ一覧
固定費一覧
```

### AI検索

Gemini API は通常メッセージでは呼び出しません。

```text
AI 今月の食費を分析して
AI 最近の支出傾向を説明して
AI メモの内容を整理して
```

`AI` だけ送ると使い方を表示し、APIは消費しません。

### 未登録コマンド

登録されていない文字列は AI に自動転送しません。

```text
そのコマンドはありません。メニューから機能を選んでください。
```

と返し、メインメニューを表示します。

---

## 2. AI検索の現在の設計

AI検索は、Gemini無料枠・応答速度・Notion API負荷を抑えるために最適化しています。

### 以前の方式

```text
AI質問
  ↓
Geminiで「どのDBを読むか」を判定  ← Gemini 1回
  ↓
Notion検索
  ↓
Geminiで回答生成                 ← Gemini 1回
```

1質問で最大2回Geminiを使うため、API回数を消費しやすい構成でした。

### 現在の方式

```text
AI質問
  ↓
Pythonルーターで関連DBを判定     ← Gemini不使用
  ↓
必要な最大2DBだけNotionから取得
  ↓
Geminiで最終回答                 ← 原則1回だけ
```

### DBルーターが見る情報

- 専用DBの用途
- NotionのDBタイトル
- プロパティ名
- プロパティ型
- 質問中のキーワード
- 日付表現

例:

```text
AI 今月の食費はいくら？
```

→ 家計簿DBを優先

```text
AI 予算あとどれくらい？
```

→ 月別管理DBと家計簿DBを優先

```text
AI 保存してあるメモを整理して
```

→ メモDBを優先

ルーターは最大2DBまで選択します。これにより、9個以上DBがあっても毎回全部の内容をGeminiへ送る必要がありません。

---

## 3. AI検索の効率化

### Gemini呼び出し回数

原則として **1質問 = 1回のGemini呼び出し** です。

### Notion DBスキーマのキャッシュ

DBタイトルやプロパティ構造はRenderプロセス内で約10分キャッシュします。

そのためAI質問のたびに全DBのメタデータを取り直す負荷を減らします。

### 最大取得DB数

```text
MAX_AI_DATABASES = 2
```

関連度の高い最大2DBのみ取得します。

### 1DBあたりの最大取得件数

```text
MAX_ROWS_PER_DB = 40
```

大量データを無制限にGeminiへ渡さないための安全策です。

### AIへ渡す最大コンテキスト

```text
MAX_CONTEXT_CHARS = 18000
```

取得データが多すぎる場合は上限で切ります。

### 日付フィルター

質問に次の表現が含まれる場合、日付プロパティを持つDBではNotion側で期間を絞ります。

- 今日
- 昨日
- 今週
- 先週
- 今月
- 先月
- 今年

例:

```text
AI 今月の家計簿を分析して
```

の場合、全履歴を読むのではなく今月分だけ取得します。

---

## 4. 60秒タイムアウト

AI検索は `app.py` 側で最大60秒待機します。

```text
worker.join(timeout=60)
```

60秒を超えた場合はLINEへタイムアウトメッセージを送ります。

この60秒設定は現在も維持しています。

理由:

- Gemini側の一時的な遅延に余裕を持たせるため
- Notion取得とGemini回答の両方を含むため
- 503 / 429 等の一時エラー時にリトライが入る場合があるため

DBルーティング最適化により以前より処理量は減っていますが、安定運用を優先して現時点では60秒のままです。

---

## 5. Notion DB ID の管理方針

専用機能で使うDBは個別の環境変数を使います。

```text
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
```

`NOTION_DATABASE_IDS` は、上記の専用変数に含まれない **追加のAI検索対象DB** をカンマ区切りで指定します。

コード側で専用DBと追加DBを自動統合し、重複IDを除去します。

つまり、現在9個DBがあり、そのうち5個が上記専用DBなら、`NOTION_DATABASE_IDS` には残り4個だけ入れる運用が推奨です。

```text
専用DB 5個
+
NOTION_DATABASE_IDS の追加DB 4個
=
AI検索候補 9個
```

同じDB IDを両方へ書いてしまってもコード側で重複除去されますが、管理上は重複させない方が分かりやすいです。

---

## 6. 家計簿

### 手動支出入力

```text
支出 1200 ラーメン
支出 3200 新宿 レストラン
```

店名に空白があっても全文を保存します。

ジャンルと支払方法はNotionのSelect候補からLINE Flex Messageで選択します。

### クレジットカード利用通知

Gmailのカード利用通知をGASが確認し、LINE Push APIへFlex Messageを直接送ります。

対応:

- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

推奨:

- GAS実行: 1時間ごと
- 実処理対象: 直近2時間
- Gmail Message IDで重複通知防止
- 既読/未読には依存しない
- 本文の利用日を可能な限り使用

---

## 7. 家計簿ダッシュボード

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
- 支払方法別支出

---

## 8. 予算

```text
予算 100000
予算 食費 30000
予算 2026-10 食費 35000
予算一覧
予算アラート
```

予算アラートは80% / 90% / 100%以上を判定します。

定期通知API:

```text
POST /api/budget-alert
```

---

## 9. 週次レポート

```text
週次レポート
今週
```

直近7日間と、その前の7日間を比較します。

表示:

- 支出合計
- 件数
- 前期間比
- 増減額
- 増減率
- 上位ジャンル

定期通知API:

```text
POST /api/weekly-report
```

---

## 10. 固定費

```text
固定費一覧
固定費
固定費追加 Netflix 1490 サブスク JCB
```

固定費マスタDBの `有効` がONの項目を使用します。

---

## 11. メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

削除は以下の2段階です。

```text
メモ削除
  ↓
候補一覧
  ↓
対象を選択
  ↓
削除確認
  ↓
削除する / やめる
```

1日1回の自動一覧通知も利用できます。

```text
POST /api/daily-memo
```

---

## 12. Notion汎用機能

### データ追加

```text
データ追加
```

対象DBのプロパティを順番に入力し、最後に確認して登録します。

### URL保存

```text
https://example.com
```

URLをそのまま送ると `NOTION_URL_DATABASE_ID` のDBへ保存します。

### Notionリンク

```text
Notion
```

`NOTION_PAGE_URL` を返信します。

---

## 13. 定期通知

GASからRender APIを呼び出します。

### 毎日

```text
sendDailyMemoReminder
sendDailyBudgetAlert
```

### 毎週

```text
sendWeeklyFinanceReport
```

Render側では `SCHEDULER_SECRET`、GAS側では同じ値のScript Propertyを使用します。

---

## 14. UI

LINE Flex Messageは長い日本語が切れにくいよう、原則1列・全幅ボタンを使用しています。

メモ削除など本文確認が重要な画面では、ボタンラベルだけでなく本文を表示してから操作できるようにしています。

---

## 15. ファイル構成

```text
line-notion-bot/
├── app.py
├── kakeibo.py
├── budget.py
├── insights.py
├── memo.py
├── menu.py
├── ui.py
├── notion_helper.py
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

### 主要役割

`app.py`
: Flask、LINE Webhook、コマンドルーティング、AI prefix判定、60秒タイムアウト、定期API

`notion_helper.py`
: Notion操作、AI向けDB自動ルーティング、スキーマキャッシュ、Gemini最終回答

`kakeibo.py`
: 支出、予算保存、固定費、カード通知

`budget.py`
: 月次予算と支出集計

`insights.py`
: ダッシュボード、予算アラート、週次レポート

`memo.py`
: メモ保存・一覧・確認付き削除

`menu.py` / `ui.py`
: LINE Flex Message UI

---

## 16. 環境変数

### LINE

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

### Notion

```text
NOTION_API_KEY
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_DATABASE_IDS
NOTION_PAGE_URL
```

### Gemini

```text
GEMINI_API_KEY
GEMINI_MODEL
```

`GEMINI_MODEL` は未設定時 `gemini-3.6-flash` を使用します。

### 定期実行

```text
SCHEDULER_SECRET
```

---

## 17. AIログ

AIルーターは選択したDBとスコアをRenderログへ出します。

例:

```text
[AI Router] 家計簿 score=18.0 reasons=role:食費,prop:金額
```

AIが違うDBを選んだ場合は、このログからルーティング改善ができます。

---

## 18. 今後の改善候補

- 予算アラートを80% / 90% / 100%到達時に各1回だけ通知
- 固定費の同月二重登録防止
- `user_states` のRedis等への永続化
- AIルーティング辞書を実際のDB名に合わせてさらに調整
- Gemini上限到達時の別AIフォールバック
- AI検索結果のページネーション / 集計専用ロジック

---

## 19. 開発時のルール

機能追加・仕様変更を行った場合は、コードだけでなく **README.md と SETUP.md も同時に更新**します。
