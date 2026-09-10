# LINE Notion Bot

LINE を入口に、**家計簿・予算管理・クレジットカード利用通知・メモ・Notion データ登録・AI検索**をまとめて扱う個人向けアシスタントです。

現在の構成では LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。日常操作はできるだけ LINE 上で完結し、Flex Message を使って長い日本語でも読みやすい UI にしています。

> 初めて構築する場合は [SETUP.md](./SETUP.md) を参照してください。
>
> Google Apps Script の詳細は [gas/README.md](./gas/README.md) も参照してください。

---

## 1. 重要な操作ルール

この Bot は、登録済みのコマンドと AI 検索を明確に分けています。

### 通常機能

家計簿、メモ、予算、固定費などは決められたコマンドで実行します。

### AI検索

Gemini API は**自動では呼び出しません**。

AI を使いたい場合だけ、メッセージの先頭に `AI` を付けます。

```text
AI 今月の食費について分析して
AI 保存しているメモを整理して
AI 家計簿の傾向を説明して
```

`AI` の後には半角または全角スペースを入れてください。

```text
AI 質問内容
```

`AI` だけ送信すると、AI検索の使い方を表示します。この時点では Gemini API を呼び出しません。

### 未登録コマンド

登録されていない文字列を送った場合、以前のように自動で Gemini へ送ることはありません。

```text
そのコマンドはありません。メニューから機能を選んでください。
```

と案内し、そのままメインメニューを表示します。

これにより、誤入力や雑談で Gemini API の回数を消費することを防ぎます。

---

## 2. この Bot でできること

### 2.1 メインメニュー

LINE で次のいずれかを送信します。

```text
メニュー
機能
機能一覧
```

家計簿、予算、メモ、AI、Notion 関連の主要機能を Flex Message で表示します。

UI は2列ボタンを避け、原則として**1列・全幅表示**にしています。長い日本語の機能名や支払方法が数文字で切れにくい構成です。

---

### 2.2 家計簿の手動登録

```text
支出 1200 ラーメン
支出 500 コンビニ
支出 3200 新宿 レストラン
```

金額と店名を受け取り、その後に Notion の家計簿 DB から取得した「ジャンル」と「カード・支払方法」を LINE 上で選択します。

店名に空白が含まれていても、店名全体を保存します。

---

### 2.3 クレジットカード利用メールの自動検知

Gmail に届いたカード利用通知メールを Google Apps Script が定期確認し、該当メールを見つけた場合は **GAS から LINE Push API へ Flex Message を直接送信**します。

対応カード:

- JCB
- 三井住友カード
- 楽天カード
- PayPay カード

推奨運用:

- GAS 実行間隔: **1時間ごと**
- 実処理対象: **直近2時間以内のメール**
- Gmail 検索は少し広めに取得
- 既読 / 未読状態には依存しない
- Gmail Message ID を使って二重通知を防止
- LINE Push 成功後に処理済み Message ID を記録
- 本文に利用日がある場合はメール受信日より利用日を優先

カード通知後は LINE 上で、店名確認、店名修正、ジャンル選択、登録キャンセルを行えます。

---

## 3. 予算管理

### 全体予算

```text
予算 100000
```

### ジャンル別予算

```text
予算 食費 30000
予算 日用品 10000
```

### 年月指定

```text
予算 2026-10 食費 35000
```

### 予算一覧

```text
予算一覧
```

表示内容:

- 全体予算
- 当月支出
- 残額
- ジャンル別予算
- ジャンル別支出
- ジャンル別残額

---

## 4. 家計簿ダッシュボード

```text
今月
```

または:

```text
ダッシュボード
家計簿ダッシュボード
```

表示内容:

- 今月の総支出
- 全体予算
- 予算残額
- 予算消化率
- 月末までの残り日数
- 残予算から算出した1日あたり利用可能額
- 支出額の大きいジャンル
- カード・支払方法別支出

日常的に家計状況を確認する場合は `今月` が最も便利です。

---

## 5. 予算アラート

```text
予算アラート
```

全体予算およびジャンル別予算について、以下の水準を判定します。

- 80%以上
- 90%以上
- 100%以上 / 予算超過

支出を保存した直後にも予算状況をチェックし、80%以上に到達している項目がある場合は Flex Message を表示します。

定期実行 API:

```text
POST /api/budget-alert
```

この API は `SCHEDULER_SECRET` による認証が必要です。

---

## 6. 週次レポート

```text
週次レポート
```

または:

```text
今週
週間レポート
```

表示内容:

- 直近7日間の支出合計
- 支出件数
- その前の7日間との比較
- 増減額
- 増減率
- 今週の支出上位ジャンル

定期実行 API:

```text
POST /api/weekly-report
```

`gas/FinanceReports.gs` の `sendWeeklyFinanceReport()` から週1回呼び出せます。

---

## 7. 固定費・サブスク

### 固定費一覧

```text
固定費一覧
```

### 今月分を一括登録

```text
固定費
```

### 固定費を追加

```text
固定費追加 Netflix 1490 サブスク JCB
固定費追加 ジム会費 8000 固定費 三井住友カード
```

Notion の固定費マスタ DB で `有効` が ON の項目が対象です。

> 現在の改善候補として、同じ月の同じ固定費を重複登録しない仕組みの強化があります。

---

## 8. メモ機能

### 保存

```text
メモ 牛乳を買う
```

### 一覧

```text
メモ一覧
```

### 削除

```text
メモ削除
```

削除は安全のため2段階です。

```text
メモ削除
  ↓
削除候補一覧
  ↓
対象メモを選択
  ↓
「このメモを削除しますか？」確認
  ↓
削除する / やめる
```

候補一覧ではメモ本文をできるだけ読めるように表示し、選択しただけでは削除されません。

---

## 9. メモの1日1回通知

Render API:

```text
POST /api/daily-memo
```

`gas/DailyMemo.gs` の `sendDailyMemoReminder()` から呼び出します。

推奨トリガー:

```text
毎日 08:00 前後
```

保存中のメモを LINE へ一覧送信します。

---

## 10. Notion の汎用データ追加

```text
データ追加
```

`NOTION_DATABASE_IDS` に登録されている DB を一覧化し、登録先を選択した後、対応するプロパティを順番に入力します。

最後に内容確認を行い、`はい` で保存します。

---

## 11. URL保存

http / https から始まる URL をそのまま LINE へ送信すると、`NOTION_URL_DATABASE_ID` で指定した DB に保存します。

```text
https://example.com/article
```

---

## 12. Notionリンク

```text
Notion
```

`NOTION_PAGE_URL` が設定されていれば、その URL を返信します。

---

## 13. AI検索 / Gemini

現在の AI モデルは `gemini-3.6-flash` です。

AI検索は通常コマンドとは分離されています。

### APIを使わない例

```text
こんにちは
適当な文字
明日の予定
```

これらは未登録コマンドとしてメニューを表示し、Gemini API は呼び出しません。

### APIを使う例

```text
AI 今月の家計簿を分析して
```

この場合だけ Gemini を呼び出します。

Gemini の無料枠にはモデルごとのリクエスト制限があるため、明示的な AI モードにすることで API 消費を抑えています。

### AIプロバイダについて

このプロジェクトでは現時点で Gemini を維持します。

理由:

- 日本語の自然言語処理品質が高い
- 長いコンテキストを扱える
- すでに `google-genai` を使った実装が完成している
- Notion の情報を渡して分析する用途と相性が良い
- AI を明示コマンドだけに限定すれば、不要な API 消費を大幅に減らせる

API回数が将来不足する場合は、Gemini Flash-Lite 系や Groq 上のオープンモデルをフォールバックとして追加する選択肢があります。

---

## 14. システム構成

```text
                         ┌─────────────────┐
                         │     Notion      │
                         │ 家計簿 / 予算   │
                         │ メモ / URL / DB │
                         └────────┬────────┘
                                  │
                                  │ Notion API
                                  │
┌─────────┐   Webhook    ┌───────▼────────┐
│  LINE   │─────────────▶│ Render / Flask │
│         │◀─────────────│     app.py      │
└────▲────┘ Reply / Push └───────┬────────┘
     │                            │
     │                            ├── Gemini API
     │                            │   ※ AI prefix時のみ
     │                            │
     │                   ┌────────▼────────┐
     │                   │ budget/insights │
     │                   │ memo/kakeibo    │
     │                   └─────────────────┘
     │
     │ LINE Push API
     │
┌────┴──────────────┐
│ Google Apps Script│
├───────────────────┤
│ Code.gs           │◀──── Gmailカード通知
│ DailyMemo.gs      │
│ FinanceReports.gs │
└───────────────────┘
```

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

### `app.py`

- Flask Web サーバー
- LINE Webhook
- コマンドルーティング
- Postback処理
- AIモード判定
- 未登録コマンド処理
- 定期通知 API

### `kakeibo.py`

- 支出保存
- 予算保存
- 固定費
- カード通知用 Flex
- Notion セレクト取得

### `budget.py`

- 月単位の予算 / 支出集計
- 予算一覧 Flex
- Notion ページネーション

### `insights.py`

- 家計簿ダッシュボード
- 予算アラート
- 週次レポート

### `memo.py`

- メモ追加
- 一覧取得
- 確認付き削除

### `menu.py`

- メインメニュー Flex
- AI検索の明示入口

### `ui.py`

- 長い日本語を読みやすくする共通 Flex UI
- ジャンル・支払方法選択
- カード通知後のジャンル選択

### `notion_helper.py`

- Notion 汎用 DB 操作
- URL保存
- Gemini AI 呼び出し

### `gas/Code.gs`

- Gmail カード利用通知検出
- LINE Flex 直接 Push
- Message ID 重複防止

### `gas/DailyMemo.gs`

- 日次メモ通知 API 呼び出し

### `gas/FinanceReports.gs`

- 予算アラート API 呼び出し
- 週次レポート API 呼び出し

---

## 16. Render 環境変数

| Key | 用途 | 必須 |
|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API | 必須 |
| `LINE_CHANNEL_SECRET` | LINE Webhook署名検証 | 必須 |
| `GEMINI_API_KEY` | Gemini API | AI使用時 |
| `NOTION_API_KEY` | Notion Integration | 必須 |
| `NOTION_KAKEIBO_DATABASE_ID` | 家計簿 DB | 家計簿使用時 |
| `NOTION_MONTHLY_DATABASE_ID` | 月別管理 DB | 予算使用時 |
| `NOTION_FIXED_DATABASE_ID` | 固定費 DB | 固定費使用時 |
| `NOTION_MEMO_DATABASE_ID` | メモ DB | メモ使用時 |
| `NOTION_URL_DATABASE_ID` | URL保存 DB | URL保存時 |
| `NOTION_DATABASE_IDS` | 汎用登録 / AI参照対象 | 任意 |
| `NOTION_PAGE_URL` | Notionショートカット | 任意 |
| `ADMIN_USER_ID` | 定期Push先LINE User ID | 定期通知時 |
| `SCHEDULER_SECRET` | GAS→Render API認証 | 定期通知時 |

秘密情報を GitHub のソースコードへ直接書かないでください。

---

## 17. GAS Script Properties

### カード通知用

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

### Render定期通知用

```text
RENDER_BASE_URL
SCHEDULER_SECRET
```

`SCHEDULER_SECRET` は Render と GAS で同じ値を設定します。

---

## 18. 推奨 GAS トリガー

| 関数 | 推奨頻度 | 用途 |
|---|---|---|
| `checkCardEmails` | 1時間ごと | カード利用メール確認 |
| `sendDailyMemoReminder` | 毎日朝 | メモ一覧通知 |
| `sendDailyBudgetAlert` | 毎日夜 | 80%以上の予算のみ通知 |
| `sendWeeklyFinanceReport` | 毎週日曜夜 | 週次レポート |

---

## 19. 主な Render API

| Path | Method | 用途 | 認証 |
|---|---|---|---|
| `/` | GET / HEAD | ヘルスチェック | なし |
| `/callback` | POST | LINE Webhook | LINE署名 |
| `/api/daily-memo` | POST | メモ一覧Push | `X-API-KEY` |
| `/api/budget-alert` | POST | 予算アラートPush | `X-API-KEY` |
| `/api/weekly-report` | POST | 週次レポートPush | `X-API-KEY` |
| `/api/register-fixed` | POST | 固定費一括登録 | 現在改善候補 |
| `/api/monthly-notice` | POST | 月初予算確認 | 現在改善候補 |

---

## 20. コマンド早見表

| コマンド | 動作 |
|---|---|
| `メニュー` | 全機能表示 |
| `今月` | 家計簿ダッシュボード |
| `支出 1200 店名` | 手動支出登録 |
| `予算一覧` | 予算一覧 |
| `予算 100000` | 全体予算設定 |
| `予算 食費 30000` | ジャンル予算設定 |
| `予算アラート` | 予算警告確認 |
| `週次レポート` | 直近7日レポート |
| `固定費一覧` | 固定費一覧 |
| `固定費` | 今月の固定費一括登録 |
| `固定費追加 ...` | 固定費追加 |
| `メモ 内容` | メモ追加 |
| `メモ一覧` | メモ一覧 |
| `メモ削除` | 確認付き削除 |
| `データ追加` | 汎用Notion登録 |
| `Notion` | Notionリンク |
| `AI 質問` | Gemini AI検索 |
| `AI` | AIの使い方 |
| `ヘルプ` | コマンド説明 |

---

## 21. セキュリティ

- LINE Channel Access Token を GitHub に書かない
- LINE Channel Secret を GitHub に書かない
- Notion API Key を GitHub に書かない
- Gemini API Key を GitHub に書かない
- `SCHEDULER_SECRET` を公開しない
- トークンをチャットや公開リポジトリへ貼った場合は再発行する
- GAS では Script Properties を使用する
- Render では Environment Variables を使用する

---

## 22. トラブルシューティング

### 未登録の文字を送ったらAIが動く

現在の `app.py` では動かない仕様です。Render が最新 `main` をデプロイしているか確認してください。

### AIが動かない

入力形式を確認します。

```text
AI 質問内容
```

さらに Render の `GEMINI_API_KEY` とログを確認してください。

### AIの無料回数を使い切る

通常操作では AI を呼ばないため、まず `AI` プレフィックス運用で使用回数を抑えます。それでも不足する場合は Flash-Lite 系または別 AI のフォールバックを検討します。

### カード通知が届かない

`gas/Code.gs` の実行ログを確認します。

確認点:

- Gmail検索ヒット数
- 2時間以内判定
- 処理済み Message ID
- LINE Push API の HTTP status
- GAS の `LINE_USER_ID`
- GAS の `LINE_CHANNEL_ACCESS_TOKEN`

### 予算一覧が取得できない

Notion の以下を確認します。

- `年月`
- `全体予算`
- `○○予算`
- 家計簿の `日付`
- 家計簿の `金額`
- 家計簿の `ジャンル`

### 定期通知が401

Render と GAS の `SCHEDULER_SECRET` が一致しているか確認します。

---

## 23. 開発時のドキュメント運用

機能追加、コマンド変更、環境変数追加、GASトリガー変更、API追加、UI変更などを行った場合は、**コード変更と同時に `README.md` と `SETUP.md` も更新する**運用とします。

特に以下は必ずドキュメントへ反映します。

- 新しい LINE コマンド
- 削除 / 登録など操作フローの変更
- 新しい環境変数
- GAS Script Properties
- GAS トリガー
- Render API
- AIモデル / AI起動条件
- Notion DB のプロパティ変更

---

## 24. 現在の改善候補

- 固定費の月内二重登録防止
- 予算アラートを80% / 90% / 100%到達時に各1回だけ送信
- `/api/register-fixed` の `SCHEDULER_SECRET` 認証
- `/api/monthly-notice` の `SCHEDULER_SECRET` 認証
- `user_states` の Redis 等への永続化
- Gemini API 上限超過時のフォールバック AI

---

## 25. 開発方針

この Bot は、AIだけに依存するチャットボットではなく、**日常操作は確実なコマンド処理、必要なときだけAI**という構成を基本方針とします。

この設計により、API コストと利用上限を抑えながら、家計簿・メモ・Notion 管理の安定性を優先できます。
