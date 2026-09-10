# LINE Notion Bot

LINE を入口に、**家計簿・予算管理・クレジットカード利用通知・メモ・Notion データ登録・AI検索**をまとめて扱う個人向けアシスタントです。

現在の構成では、LINE Messaging API、Notion API、Google Gemini、Gmail / Google Apps Script、Render を連携しています。日常操作はできるだけ LINE 上で完結するようにし、Flex Message を使ってボタンや一覧を見やすく表示します。

> 初めて構築する場合は [SETUP.md](./SETUP.md) を先に参照してください。
>
> Google Apps Script 関連の詳細は [gas/README.md](./gas/README.md) も参照してください。

---

## 1. この Bot でできること

### 1.1 家計簿

LINE から手動で支出を登録できます。

```text
支出 1200 ラーメン
支出 500
```

金額と店名を入力したあと、Notion の家計簿 DB に登録されている「ジャンル」「カード・支払方法」を LINE 上で選択できます。

店名に空白が含まれる場合も、店名全体を扱えるようにしています。

### 1.2 クレジットカード利用メールの自動検知

Gmail に届いたカード利用通知メールを Google Apps Script が定期的に確認し、対象メールを見つけると LINE へ Flex Message を直接 Push します。

現在対応しているカード通知は以下です。

- JCB
- 三井住友カード
- 楽天カード
- PayPay カード

現在の推奨運用は次のとおりです。

- GAS 実行間隔: **1時間ごと**
- 最終判定対象: **直近2時間以内のメール**
- Gmail 検索自体は少し広めに取得
- 既読 / 未読ではなく Gmail の Message ID で二重通知を防止
- LINE 送信成功後に処理済み Message ID を保存
- 可能な場合はメール受信日ではなく、本文内の実際のカード利用日を取得

カード利用通知では、店名・金額・カード名を確認してから、ジャンル選択や店名修正へ進めます。

### 1.3 予算管理

Notion の「月別管理」DB に保存した予算を使い、全体予算とジャンル別予算を管理できます。

```text
予算 100000
予算 食費 30000
予算 2026-10 食費 35000
```

一覧確認:

```text
予算一覧
```

表示内容には以下が含まれます。

- 全体予算
- 今月の使用額
- 残額
- ジャンル別予算
- ジャンル別使用額
- ジャンル別残額

### 1.4 家計簿ダッシュボード

```text
今月
```

またはメニューの「今月のダッシュボード」から表示できます。

ダッシュボードでは、単純な支出合計だけでなく以下をまとめて確認できます。

- 今月の総支出
- 全体予算
- 予算残額
- 予算消化率
- 月末までの残り日数
- 残予算から計算した1日あたり使える金額
- 支出額の大きいジャンル上位
- カード・支払方法別の支出額

### 1.5 予算アラート

```text
予算アラート
```

全体予算またはジャンル別予算が以下の水準に達しているかを判定します。

- 80%以上
- 90%以上
- 100%以上 / 予算超過

また、定期実行用 API `/api/budget-alert` を GAS から呼び出すことで、1日1回などの自動確認もできます。

80%未満の場合、定期アラートは LINE へ送信しません。

### 1.6 週次レポート

```text
週次レポート
今週
```

直近7日間を集計し、前の7日間と比較します。

主な表示内容:

- 直近7日間の総支出
- 登録件数
- 前の7日間との金額差
- 前期間比
- ジャンル別支出上位

GAS から `/api/weekly-report` を呼び出せば、毎週日曜日などに自動配信できます。

### 1.7 固定費・サブスク

Notion の固定費マスタから有効な項目を取得して、家計簿へ一括登録できます。

```text
固定費
固定費一覧
固定費追加 ジム会費 8000 固定費 三井住友カード
```

固定費マスタの `有効` チェックボックスが ON の項目が対象です。

> 注意: 現在の実装では、同じ月に固定費一括登録を複数回実行した場合の完全な重複防止は未実装です。運用時は重複登録に注意してください。

### 1.8 メモ

メモを Notion に保存できます。

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

削除操作は誤操作防止のため、現在は次の2段階です。

1. 削除候補一覧からメモを選ぶ
2. メモ内容を確認して「削除する」を押す

一覧では長いメモ内容も確認しやすいよう、短いボタン文字だけに依存しない UI に改善しています。

### 1.9 メモの1日1回通知

`gas/DailyMemo.gs` から Render の `/api/daily-memo` を呼び出すことで、保存中のメモ一覧を1日1回 LINE へ送信できます。

推奨例:

- 毎朝 8 時前後

最大30件を通知し、それ以上ある場合は残件数を表示します。

### 1.10 Notion への汎用データ追加

```text
データ追加
```

`NOTION_DATABASE_IDS` に登録されているデータベースを一覧化し、登録先を選択して各プロパティを対話形式で入力できます。

### 1.11 URL 保存

LINE に URL をそのまま送信すると、`NOTION_URL_DATABASE_ID` で指定したデータベースへ保存します。

```text
https://example.com
```

### 1.12 Notion / Gemini 検索

専用コマンドに該当しない通常メッセージは、Notion 検索・Gemini 応答処理へ渡されます。

例:

```text
今月の食費について教えて
楽天カードの支出を確認したい
```

検索対象 DB は `NOTION_DATABASE_IDS` で指定します。

---

## 2. LINE のメニュー

LINE で以下を送信します。

```text
メニュー
機能
機能一覧
```

現在のメニューは横幅の狭い2列ボタンを避け、**基本的に1列・全幅**で表示する構成です。

これは日本語の長いボタン名が6文字前後で切れてしまう問題を軽減するための変更です。

主な項目:

### 家計簿・予算

- 今月のダッシュボード
- 支出を入力する
- 予算一覧を見る
- 予算を設定する
- 予算アラートを見る
- 週次レポートを見る
- 固定費一覧を見る
- 固定費を一括登録
- 固定費を追加

### メモ

- メモを追加
- メモ一覧を見る
- メモを削除

### Notion・その他

- データ追加
- Notion を開く
- ヘルプ

選択肢 UI も原則1列表示としており、ジャンル名・支払方法などの長い文字を確認しやすくしています。

---

## 3. システム構成

```text
                        ┌────────────────────┐
                        │       LINE         │
                        │ Messaging API      │
                        └─────────┬──────────┘
                                  │ Webhook / Push
                    ┌─────────────┴─────────────┐
                    │                           │
          ┌─────────▼─────────┐       ┌────────▼─────────┐
          │      Render       │       │ Google Apps      │
          │ Flask / Gunicorn  │       │ Script           │
          └──────┬─────┬──────┘       └───────┬──────────┘
                 │     │                       │
          Notion API   │ Gemini API            │ Gmail
                 │     │                       │
          ┌──────▼──┐ ┌▼──────────┐     ┌──────▼──────┐
          │ Notion  │ │ Gemini    │     │ Card mails  │
          │ DB群    │ │           │     │ JCB etc.    │
          └─────────┘ └───────────┘     └─────────────┘

カード通知:
Gmail → GAS → LINE Push(Flex) → ユーザー操作 → LINE Webhook → Render → Notion

定期レポート:
GAS Trigger → Render Scheduler API → LINE Push
```

カード通知は、GAS が `CARD_NOTIFY|...` のようなテキストを Bot 自身へ送って Webhook を起こす方式ではありません。

**GAS が LINE Push API へ Flex Message を直接送信し、その Flex の postback ボタン操作だけが Render の `/callback` に届く**構成です。

---

## 4. ファイル構成

| ファイル | 役割 |
|---|---|
| `app.py` | Flask 本体、LINE Webhook、コマンド分岐、Postback、定期通知 API |
| `kakeibo.py` | 家計簿保存、予算残高、固定費、カード通知用 Flex |
| `budget.py` | 月別予算・支出集計、予算一覧 Flex |
| `insights.py` | 家計簿ダッシュボード、予算アラート、週次レポート |
| `memo.py` | メモ追加・取得・削除・削除確認 UI |
| `menu.py` | LINE メインメニュー |
| `ui.py` | 長い文字を見やすくする共通選択 UI |
| `notion_helper.py` | Notion DB 情報取得、データ追加、URL保存、Gemini関連処理 |
| `prompt.txt` | AI 応答用プロンプト |
| `requirements.txt` | Python 依存パッケージ |
| `gas/Code.gs` | Gmail カード利用メール監視、LINE Flex Push |
| `gas/DailyMemo.gs` | メモ一覧の日次通知 |
| `gas/FinanceReports.gs` | 予算アラート・週次レポートの定期呼び出し |
| `gas/README.md` | GAS の補足設定資料 |
| `SETUP.md` | 初期構築・移行・動作確認手順 |

---

## 5. Render 環境変数

| Key | 必須 | 用途 |
|---|---:|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | 必須 | LINE Messaging API のアクセストークン |
| `LINE_CHANNEL_SECRET` | 必須 | LINE Webhook 署名検証 |
| `ADMIN_USER_ID` | 定期通知利用時必須 | 日次メモ・予算アラート・週次レポートの送信先 LINE User ID |
| `GEMINI_API_KEY` | AI利用時必須 | Gemini API |
| `NOTION_API_KEY` | Notion利用時必須 | Notion Integration Secret |
| `NOTION_KAKEIBO_DATABASE_ID` | 家計簿利用時必須 | 家計簿 DB |
| `NOTION_MONTHLY_DATABASE_ID` | 予算利用時必須 | 月別管理 DB |
| `NOTION_FIXED_DATABASE_ID` | 固定費利用時必須 | 固定費マスタ DB |
| `NOTION_MEMO_DATABASE_ID` | メモ利用時必須 | メモ DB |
| `NOTION_URL_DATABASE_ID` | URL保存利用時必須 | URL 保存先 DB |
| `NOTION_DATABASE_IDS` | AI検索/汎用追加利用時 | 対象 DB ID をカンマ区切りで指定 |
| `NOTION_PAGE_URL` | 任意 | `Notion` コマンドで返すショートカット URL |
| `SCHEDULER_SECRET` | 定期API利用時必須 | GAS → Render の定期通知 API 認証用秘密鍵 |

秘密情報は GitHub に直接書かず、Render の Environment Variables に設定してください。

---

## 6. GAS Script Properties

Google Apps Script の「プロジェクトの設定 → スクリプト プロパティ」に設定します。

| Key | 使用ファイル | 用途 |
|---|---|---|
| `LINE_USER_ID` | `Code.gs` | カード通知の送信先 |
| `LINE_CHANNEL_ACCESS_TOKEN` | `Code.gs` | GAS から LINE Push API を呼ぶためのトークン |
| `RENDER_BASE_URL` | `DailyMemo.gs`, `FinanceReports.gs` | Render の URL。例 `https://xxxx.onrender.com` |
| `SCHEDULER_SECRET` | `DailyMemo.gs`, `FinanceReports.gs` | Render 側と同じ定期 API 用秘密鍵 |

`LINE_CHANNEL_ACCESS_TOKEN` や `SCHEDULER_SECRET` を GAS のソースコードへ直接書かないでください。

---

## 7. Notion データベース仕様

### 7.1 家計簿 DB

必要なプロパティ:

| プロパティ | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `日付` | Date |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `月別管理` | Relation |

### 7.2 月別管理 DB

| プロパティ | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算` など `○○予算` | Number |

ジャンル別予算は、家計簿のジャンル名 + `予算` の名前にしてください。

例:

```text
食費 → 食費予算
交通費 → 交通費予算
娯楽 → 娯楽予算
```

`budget.py` は、月別管理 DB の **末尾が「予算」の Number プロパティ**を一覧対象として扱います。

### 7.3 固定費マスタ DB

| プロパティ | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

### 7.4 メモ DB

| プロパティ | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

### 7.5 URL 保存 DB

現行コードでは最低限、以下を使用します。

| プロパティ | 型 |
|---|---|
| `URL` | Title |

---

## 8. 定期実行

### カード利用通知

`gas/Code.gs`

推奨:

```text
checkCardEmails
1時間ごと
```

コード側では直近2時間以内を最終対象にします。

### 日次メモ

`gas/DailyMemo.gs`

推奨:

```text
sendDailyMemoReminder
毎日 朝8時前後
```

### 予算アラート

`gas/FinanceReports.gs`

推奨:

```text
sendDailyBudgetAlert
毎日 20時前後
```

80%以上の対象が存在するときだけ LINE 通知します。

### 週次レポート

```text
sendWeeklyFinanceReport
毎週日曜日 20時前後
```

---

## 9. Render API

| Method | Path | 用途 | 認証 |
|---|---|---|---|
| `GET/HEAD` | `/` | ヘルスチェック | なし |
| `POST` | `/callback` | LINE Webhook | LINE署名 |
| `POST` | `/api/daily-memo` | メモ一覧通知 | `X-API-KEY: SCHEDULER_SECRET` |
| `POST` | `/api/budget-alert` | 予算アラート | `X-API-KEY: SCHEDULER_SECRET` |
| `POST` | `/api/weekly-report` | 週次レポート | `X-API-KEY: SCHEDULER_SECRET` |
| `POST` | `/api/register-fixed` | 固定費一括登録 | 現状なし |
| `POST` | `/api/monthly-notice` | 月初予算設定通知 | 現状なし |

> `register-fixed` と `monthly-notice` は既存実装との互換性のため現状無認証です。外部公開 URL で運用するため、将来的には `SCHEDULER_SECRET` 保護へ統一することを推奨します。

---

## 10. 主な LINE コマンド

| 入力 | 動作 |
|---|---|
| `メニュー` | 全機能メニュー |
| `今月` | 家計簿ダッシュボード |
| `支出 1200 ラーメン` | 手動支出登録開始 |
| `予算一覧` | 月別・ジャンル別予算一覧 |
| `予算 100000` | 今月の全体予算設定 |
| `予算 食費 30000` | 今月の食費予算設定 |
| `予算アラート` | 80/90/100% 判定 |
| `週次レポート` / `今週` | 直近7日レポート |
| `固定費` | 固定費一括登録 |
| `固定費一覧` | 固定費マスタ一覧 |
| `固定費追加 ...` | 固定費マスタ追加 |
| `メモ 内容` | メモ追加 |
| `メモ一覧` | メモ一覧 |
| `メモ削除` | 確認付き削除 |
| `データ追加` | 汎用 Notion DB 追加 |
| `Notion` | Notion ショートカット URL |
| URLそのもの | URL保存 DB へ保存 |
| `ヘルプ` | 操作説明 |

---

## 11. セキュリティ上の注意

### LINE Channel Access Token

Channel Access Token をチャット、GitHub、スクリーンショット等へ公開した場合は、そのトークンを再利用せず LINE Developers で再発行してください。

再発行後は以下の両方を更新します。

```text
Render:
LINE_CHANNEL_ACCESS_TOKEN

GAS Script Properties:
LINE_CHANNEL_ACCESS_TOKEN
```

### Scheduler Secret

`SCHEDULER_SECRET` は十分長いランダム文字列にし、以下で同じ値を使用します。

```text
Render Environment:
SCHEDULER_SECRET

GAS Script Properties:
SCHEDULER_SECRET
```

秘密鍵そのものをリポジトリへコミットしないでください。

---

## 12. トラブルシューティング

### LINE に返信が来ない

1. Render の Deploy が成功しているか確認
2. Render Logs を確認
3. LINE Developers の Webhook URL が `/callback` になっているか確認
4. Webhook 利用が ON か確認
5. `LINE_CHANNEL_SECRET` と `LINE_CHANNEL_ACCESS_TOKEN` を確認

### カード利用通知が届かない

GAS の実行ログを確認します。

確認するログ例:

```text
[JCB] Gmail検索: ...
[JCB] ヒットしたスレッド数: ...
[JCB] 候補メール: ...
[解析成功] ...
[LINE Flex送信] ...
LINEレスポンス: 200 ...
```

`ヒットしたスレッド数: 0` の場合は、メール送信元・件名・検索期間を確認してください。

`LINEレスポンス: 401` の場合は LINE Channel Access Token を確認してください。

### 同じカード通知が何度も来る

`Code.gs` は処理済み Gmail Message ID を Script Properties に保存します。Script Properties を削除・リセットした場合、期間内のメールが再通知される可能性があります。

### 予算一覧が出ない

以下を確認します。

- `NOTION_MONTHLY_DATABASE_ID`
- `年月` が Title 型か
- `全体予算` が Number 型か
- ジャンル別列が `食費予算` のような名前か
- Notion Integration が DB に接続されているか

### ダッシュボードの支出が合わない

家計簿 DB の以下の型・名称を確認します。

```text
金額: Number
日付: Date
ジャンル: Select
カード・支払方法: Select
```

### 日次メモ / 予算アラート / 週次レポートが 401

Render と GAS で `SCHEDULER_SECRET` が一致しているか確認してください。

### Notion 保存が 400

Notion 側のプロパティ名と型がコードと一致しているかを確認してください。

---

## 13. 現在の既知の改善候補

現在でも運用できますが、今後改善すると安全性・使いやすさが上がる項目です。

1. 固定費の月内重複登録防止
2. `/api/register-fixed` と `/api/monthly-notice` の認証統一
3. 予算アラートを80%・90%・100%の各到達時に一度だけ通知する履歴管理
4. `user_states` の Redis 等への移行（Render 再起動時の会話状態消失防止）
5. Notion API エラー時のリトライ・タイムアウト統一
6. 自動テスト / GitHub Actions の追加

---

## 14. 技術スタック

- Python
- Flask
- Gunicorn
- LINE Messaging API / `line-bot-sdk`
- Notion API
- Google Gemini / `google-genai`
- Google Apps Script
- Gmail
- Render

依存ライブラリは `requirements.txt` を参照してください。

---

## 15. 開発時の基本フロー

```text
GitHub main へ変更をコミット
        ↓
Render が自動デプロイ
        ↓
Render Logs で起動確認
        ↓
LINE で動作確認
```

GAS ファイルについては、GitHub の `gas/*.gs` を変更しても、通常のスタンドアロン Google Apps Script プロジェクトには自動反映されません。

GitHub 側を更新した場合は、GAS 側にも同じコードを反映してください。

---

## 16. 最小動作確認チェック

デプロイ後は以下を順番に確認すると問題箇所を切り分けやすくなります。

```text
1. Render URL の / が 200 を返す
2. LINE Webhook の検証が成功する
3. 「メニュー」が表示される
4. 「今月」が表示される
5. 「予算一覧」が表示される
6. 「メモ一覧」が表示される
7. 「支出 100 テスト」が登録できる
8. GAS の checkCardEmails を手動実行する
9. 日次/週次 GAS を手動実行し 200 を確認する
```

より詳細な構築手順は [SETUP.md](./SETUP.md) を参照してください。
