# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Google Apps Script・Gmail・Render を連携し、このリポジトリの Bot を**ゼロから構築する手順**と、既存環境を**現在の構成へ更新する手順**をまとめたものです。

README はシステム全体の説明、SETUP は実際の導入作業を順番に進めるための手順書として分けています。

---

# 1. 完成後の構成

```text
LINE
  ├─ ユーザー操作 → /callback → Render / Flask
  │                              ├─ Notion API
  │                              └─ Gemini API
  │
  └─ 通知受信 ← LINE Push API
                  ▲
                  │
         ┌────────┴────────┐
         │                 │
      GAS Code.gs      Render API
         ▲                 ▲
         │                 │
       Gmail         GAS Timer Trigger
                   DailyMemo / FinanceReports
```

用途ごとの流れは次のとおりです。

### カード通知

```text
カード会社
   ↓
Gmail
   ↓
Google Apps Script / gas/Code.gs
   ↓
LINE Push API
   ↓
Flex Message
   ↓ ユーザーがボタンを押す
LINE Webhook
   ↓
Render / app.py
   ↓
Notion 家計簿 DB
```

### 日次・週次通知

```text
Google Apps Script Trigger
   ↓
Render Scheduler API
   ↓
Notion 集計
   ↓
LINE Push
```

---

# 2. 必要なアカウント・サービス

準備するもの:

- GitHub
- Render
- LINE Developers
- Notion
- Google アカウント
  - Gmail
  - Google Apps Script
  - Google AI Studio / Gemini API

任意:

- UptimeRobot 等の外部監視サービス

---

# 3. リポジトリの主要ファイル

| ファイル | 用途 |
|---|---|
| `app.py` | LINE Webhook、コマンド分岐、Scheduler API |
| `kakeibo.py` | 支出登録、固定費、予算残高、カード登録 UI |
| `budget.py` | 予算・支出の月次集計、予算一覧 |
| `insights.py` | ダッシュボード、予算アラート、週次レポート |
| `memo.py` | メモ追加・一覧・確認付き削除 |
| `menu.py` | メインメニュー |
| `ui.py` | 長い選択肢を見やすくする共通 UI |
| `notion_helper.py` | Notion 汎用処理、URL保存、Gemini関連 |
| `gas/Code.gs` | カード通知メール監視 |
| `gas/DailyMemo.gs` | メモ日次通知 |
| `gas/FinanceReports.gs` | 予算アラート・週次レポート定期実行 |

---

# 4. Notion の準備

この Bot は Notion のプロパティ名と型を前提に処理します。

**名前と型はできるだけこの手順どおりに作成してください。**

## 4.1 家計簿 DB

新しいデータベースを作成します。

推奨 DB 名:

```text
家計簿
```

必要なプロパティ:

| 名前 | 型 | 例 |
|---|---|---|
| `内容・店名` | Title | セブンイレブン |
| `金額` | Number | 1200 |
| `日付` | Date | 2026-09-10 |
| `ジャンル` | Select | 食費 |
| `カード・支払方法` | Select | JCB |
| `月別管理` | Relation | 2026-09 |

`ジャンル` の例:

```text
食費
日用品
交通費
娯楽
医療費
衣服
固定費
サブスク
```

カード通知や手動登録で使用する通常ジャンル選択では、コード上 `固定費` と `サブスク` は除外されています。

`カード・支払方法` の例:

```text
現金
JCB
三井住友カード
楽天カード
PayPay
```

## 4.2 月別管理 DB

推奨 DB 名:

```text
月別管理
```

必要なプロパティ:

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |

ジャンル別予算を使用する場合、以下の形式で Number プロパティを追加します。

```text
食費予算
日用品予算
交通費予算
娯楽予算
```

重要:

```text
家計簿ジャンル名 + 「予算」
```

という名前にしてください。

例:

```text
ジャンル: 食費
↓
月別管理: 食費予算
```

## 4.3 Relation の設定

家計簿 DB の `月別管理` を、月別管理 DB への Relation にします。

Bot は支出登録時に対象月のページを取得または作成して、自動的に Relation を設定します。

## 4.4 固定費マスタ DB

推奨 DB 名:

```text
固定費マスタ
```

必要なプロパティ:

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

`有効` が ON の項目だけ一括登録対象です。

例:

```text
Netflix / 1490 / サブスク / JCB / ON
家賃 / 80000 / 固定費 / 振込 / ON
旧サービス / 980 / サブスク / JCB / OFF
```

> 現在は固定費の月内重複登録を完全には防止していません。`固定費` コマンドや `/api/register-fixed` を同月に複数回実行するときは注意してください。

## 4.5 メモ DB

推奨 DB 名:

```text
メモ
```

必要なプロパティ:

| 名前 | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

## 4.6 URL 保存 DB

推奨 DB 名:

```text
後で見る
```

最低限必要なプロパティ:

| 名前 | 型 |
|---|---|
| `URL` | Title |

現行コードでは URL をこの Title プロパティへ保存します。

---

# 5. Notion Integration の作成

1. Notion の Integration 管理画面を開く
2. Internal Integration を作成
3. Secret を取得
4. 後で Render の `NOTION_API_KEY` に設定
5. 使用する各 DB に Integration を接続

Integration が DB に接続されていないと、正しい Database ID を設定していても取得・保存できません。

## Database ID の取得

Notion DB の URL から Database ID を取得してください。

環境変数に必要な ID:

```text
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
```

また、AI検索や `データ追加` の対象 DB は `NOTION_DATABASE_IDS` にカンマ区切りで設定します。

例:

```text
abc123...,def456...,ghi789...
```

---

# 6. LINE Messaging API の設定

## 6.1 Messaging API Channel

LINE Developers で Messaging API Channel を用意します。

取得する情報:

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

これらは Render の Environment Variables に設定します。

## 6.2 Bot と友だちになる

定期 Push 通知を受け取るため、対象アカウントで Bot を友だち追加してください。

## 6.3 ADMIN_USER_ID / LINE_USER_ID

このシステムでは LINE User ID を2箇所で使います。

### Render

```text
ADMIN_USER_ID
```

用途:

- 日次メモ通知
- 予算アラート
- 週次レポート
- その他 Render からの Push

### GAS

```text
LINE_USER_ID
```

用途:

- Gmail で検知したカード利用通知を直接 LINE へ Push

通常は同じ本人の User ID を設定します。

---

# 7. Gemini API の準備

Google AI Studio で API Key を発行します。

Render に以下を設定します。

```text
GEMINI_API_KEY
```

AI検索を使用しない場合でも、コード全体をそのまま使うなら設定しておくことを推奨します。

---

# 8. Render へデプロイ

## 8.1 Web Service 作成

Render で GitHub リポジトリを接続し、Web Service を作成します。

設定例:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

## 8.2 Environment Variables

以下を設定します。

| Key | 必須条件 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE利用時必須 |
| `LINE_CHANNEL_SECRET` | LINE利用時必須 |
| `ADMIN_USER_ID` | 定期Push利用時必須 |
| `GEMINI_API_KEY` | Gemini利用時必須 |
| `NOTION_API_KEY` | Notion利用時必須 |
| `NOTION_KAKEIBO_DATABASE_ID` | 家計簿利用時必須 |
| `NOTION_MONTHLY_DATABASE_ID` | 予算利用時必須 |
| `NOTION_FIXED_DATABASE_ID` | 固定費利用時必須 |
| `NOTION_MEMO_DATABASE_ID` | メモ利用時必須 |
| `NOTION_URL_DATABASE_ID` | URL保存利用時必須 |
| `NOTION_DATABASE_IDS` | AI検索・汎用追加利用時 |
| `NOTION_PAGE_URL` | 任意 |
| `SCHEDULER_SECRET` | 日次・週次通知利用時必須 |

## 8.3 SCHEDULER_SECRET の作成

日次通知 API を外部から勝手に実行されにくくするため、十分長いランダム文字列を作成してください。

例として必要な形式は単なる文字列です。

```text
SCHEDULER_SECRET=<長いランダム値>
```

実際の秘密値は GitHub やチャットへ貼らず、Render Environment と GAS Script Properties にだけ設定してください。

---

# 9. Render の初回動作確認

デプロイ後、Render の URL をブラウザで開きます。

例:

```text
https://your-service.onrender.com/
```

以下が表示されれば Flask 自体は起動しています。

```text
Bot is running!
```

---

# 10. LINE Webhook の設定

LINE Developers の Webhook URL を以下にします。

```text
https://your-service.onrender.com/callback
```

設定後:

1. Webhook 利用を ON
2. Webhook URL の検証を実行
3. LINE から `メニュー` と送信

正常なら Flex Message のメニューが表示されます。

---

# 11. Google Apps Script の準備

Google Apps Script プロジェクトを1つ作成します。

GitHub の `gas` フォルダにある以下のファイルを GAS 側にも作成してください。

```text
Code.gs
DailyMemo.gs
FinanceReports.gs
```

> GitHub の `.gs` を更新しても、通常の Google Apps Script プロジェクトには自動同期されません。GitHub で更新した場合は GAS 側にも反映してください。

---

# 12. GAS Script Properties

Apps Script 画面で:

```text
プロジェクトの設定
↓
スクリプト プロパティ
```

へ進み、以下を設定します。

| Key | 用途 |
|---|---|
| `LINE_USER_ID` | カード利用通知の送信先 |
| `LINE_CHANNEL_ACCESS_TOKEN` | GAS → LINE Push API |
| `RENDER_BASE_URL` | 定期通知 API の Render URL |
| `SCHEDULER_SECRET` | Render と GAS の共通秘密鍵 |

`RENDER_BASE_URL` の例:

```text
https://your-service.onrender.com
```

末尾 `/` は不要です。

---

# 13. カード利用通知 GAS

使用ファイル:

```text
gas/Code.gs
```

メイン関数:

```text
checkCardEmails
```

## 現在の動作

現在のコードは次の方式です。

```text
Gmail検索
↓
対象メール本文を解析
↓
店名 / 金額 / 利用日を抽出
↓
LINE Push API に Flex Message を直接送信
↓
ユーザーがジャンル選択
↓
LINE Webhook → Render
↓
Notion 保存
```

GAS から Render `/callback` に偽の LINE Webhook JSON を送る方式は使用しません。

## 対応カード

- JCB
- 三井住友カード
- 楽天カード
- PayPay カード

## 検索時間

現在はコード上:

```text
SEARCH_INTERVAL_MINUTES = 120
```

つまり、最終的に**直近2時間以内**のメールを処理対象とします。

Gmail の検索クエリ自体は `newer_than:2d` など広めに取り、その後 `msg.getDate()` で厳密に判定します。

## 重複防止

既読 / 未読だけでは管理しません。

処理済み Gmail Message ID を Script Properties に保存し、一度成功したメールは再送しない方式です。

---

# 14. カード通知トリガー

Apps Script 左側の「トリガー」から追加します。

推奨:

```text
実行する関数: checkCardEmails
イベントのソース: 時間主導型
時間ベース: 時間ベースのタイマー
間隔: 1時間おき
```

1時間ごとに動かし、コードでは2時間前まで確認するため、多少実行がずれても取りこぼしにくい構成です。

初回はトリガーを作る前に手動で `checkCardEmails()` を実行し、Google 権限を承認してください。

---

# 15. カード通知のテスト

実行ログを確認します。

正常例:

```text
--- 処理開始 ---
[JCB] Gmail検索: ...
[JCB] ヒットしたスレッド数: 1
[JCB] 候補メール: ...
[解析成功] JCB: 店名=... / 金額=... / 利用日=...
[LINE Flex送信] ...
LINEレスポンス: 200 ...
[処理成功] ...
--- 処理完了 ---
```

### 0件の場合

```text
ヒットしたスレッド数: 0
```

確認するもの:

- From アドレス
- 件名
- メール受信日時
- Gmail アカウントが正しいか

### 解析失敗

```text
[解析失敗]
```

カード会社のメール本文形式が変わった可能性があります。

### LINE 401

```text
LINEレスポンス: 401
```

`LINE_CHANNEL_ACCESS_TOKEN` を確認してください。

---

# 16. 日次メモ通知

使用ファイル:

```text
gas/DailyMemo.gs
```

関数:

```text
sendDailyMemoReminder
```

この関数は:

```text
POST /api/daily-memo
X-API-KEY: SCHEDULER_SECRET
```

を Render に送信します。

Render が Notion のメモ DB を取得し、`ADMIN_USER_ID` に LINE Push します。

推奨トリガー:

```text
毎日
朝8時前後
```

初回は `sendDailyMemoReminder()` を手動実行してください。

ログが 200 なら成功です。

---

# 17. 予算アラートの定期通知

使用ファイル:

```text
gas/FinanceReports.gs
```

関数:

```text
sendDailyBudgetAlert
```

Render API:

```text
POST /api/budget-alert
```

判定対象:

```text
全体予算
ジャンル別予算
```

閾値:

```text
80%
90%
100%以上
```

80%未満なら LINE Push は行われません。

推奨トリガー:

```text
毎日 20時前後
```

> 現在は「同じ80%状態では一度だけ通知」という履歴管理までは入っていないため、80%以上の状態が続くと定期実行ごとに通知される場合があります。

---

# 18. 週次レポートの定期通知

同じ `gas/FinanceReports.gs` を使用します。

関数:

```text
sendWeeklyFinanceReport
```

Render API:

```text
POST /api/weekly-report
```

推奨トリガー:

```text
毎週日曜日
20時前後
```

レポート内容:

- 直近7日間の総支出
- 件数
- 前の7日間との比較
- 増減率
- ジャンル上位

---

# 19. LINE メニュー・UI 動作確認

LINE で:

```text
メニュー
```

現在の UI は、以前の2列ボタンを中心とした設計から、**1列・全幅を基本**とするレイアウトへ変更しています。

特に以下を確認してください。

- ボタン文字が極端に省略されていない
- 長いジャンル名が以前より確認しやすい
- `三井住友カード` のような支払方法が読める
- メモ削除前に内容が確認できる

---

# 20. 家計簿ダッシュボードの確認

LINE で:

```text
今月
```

表示されるもの:

- 総支出
- 全体予算
- 残額
- 消化率
- 残り日数
- 1日あたり使える額
- 支出上位ジャンル
- 支払方法別集計

データが出ない場合は `NOTION_KAKEIBO_DATABASE_ID` と家計簿 DB のプロパティ名を確認してください。

---

# 21. 予算一覧の確認

LINE で:

```text
予算一覧
```

または:

```text
予算確認
今月の予算
```

ジャンル別予算が表示されない場合、月別管理 DB の列名を確認します。

正しい例:

```text
食費予算
交通費予算
```

間違い例:

```text
予算_食費
食費の予算
```

現行実装は末尾の `予算` を基準に読み取ります。

---

# 22. 予算設定の確認

```text
予算 100000
```

今月の全体予算を設定します。

```text
予算 食費 30000
```

今月の食費予算を設定します。

```text
予算 2026-10 食費 35000
```

年月を指定します。

---

# 23. 予算アラート手動確認

LINE で:

```text
予算アラート
```

80%以上に達している全体予算またはジャンル予算を表示します。

---

# 24. 週次レポート手動確認

LINE で:

```text
週次レポート
```

または:

```text
今週
```

を送信します。

---

# 25. メモ機能の確認

## 追加

```text
メモ 牛乳を買う
```

## 一覧

```text
メモ一覧
```

## 削除

```text
メモ削除
```

現在は安全のため:

```text
削除候補を選択
↓
メモ本文を確認
↓
削除する / やめる
```

という2段階です。

選択しただけでは削除されません。

---

# 26. 固定費の確認

一覧:

```text
固定費一覧
```

登録:

```text
固定費
```

追加:

```text
固定費追加 Netflix 1490 サブスク JCB
```

固定費一括登録を同月に何度も実行しないよう注意してください。

---

# 27. URL 保存の確認

LINE へ URL をそのまま送信します。

```text
https://example.com
```

`NOTION_URL_DATABASE_ID` の DB に保存されれば成功です。

---

# 28. 汎用データ追加

```text
データ追加
```

`NOTION_DATABASE_IDS` に設定した DB 名が番号付きで表示されます。

番号を送ると、対象 DB の対応プロパティを順番に質問します。

最後に確認して Notion へ保存します。

---

# 29. ヘルスチェック

Render のトップ URL:

```text
GET /
```

が 200 を返します。

外部監視を使う場合はこの URL を監視対象にできます。

ただし Render の料金プランやスリープ仕様は変更される可能性があるため、UptimeRobot 等を利用する場合は現在の Render の仕様を確認してください。

---

# 30. セキュリティ

## Token をソースへ書かない

以下は GitHub へ直接書かないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
LINE_USER_ID
ADMIN_USER_ID
```

秘密情報は Render Environment または GAS Script Properties に保存します。

## LINE Token を公開してしまった場合

LINE Developers で再発行してください。

その後:

```text
Render の LINE_CHANNEL_ACCESS_TOKEN
GAS の LINE_CHANNEL_ACCESS_TOKEN
```

を両方更新します。

## Scheduler Secret

Render と GAS で同じ値を使用します。

一致していない場合は Scheduler API が 401 になります。

---

# 31. Scheduler API 一覧

| Path | 用途 | 認証 |
|---|---|---|
| `/api/daily-memo` | 日次メモ | `X-API-KEY` |
| `/api/budget-alert` | 予算アラート | `X-API-KEY` |
| `/api/weekly-report` | 週次レポート | `X-API-KEY` |
| `/api/register-fixed` | 固定費一括登録 | 現状なし |
| `/api/monthly-notice` | 月初予算確認 | 現状なし |

`X-API-KEY` には `SCHEDULER_SECRET` を設定します。

既存の `/api/register-fixed` と `/api/monthly-notice` はまだ共通秘密鍵保護へ統一されていません。

---

# 32. よくあるトラブル

## Render Deploy が失敗

Render Logs の最初の Python Error を確認してください。

よくある原因:

- SyntaxError
- ImportError
- Environment Variable 不足
- requirements.txt の依存関係不足

## LINE Webhook 検証失敗

確認:

```text
Webhook URL が /callback まで入っているか
LINE_CHANNEL_SECRET が正しいか
Render が起動しているか
```

## LINE Push が届かない

確認:

- Bot を友だち追加済みか
- User ID が正しいか
- Channel Access Token が正しいか

## Scheduler API が401

```text
Render SCHEDULER_SECRET
GAS SCHEDULER_SECRET
```

が同じか確認します。

## Notion 400

ほぼ最初に確認する項目:

- プロパティ名
- プロパティ型
- Database ID
- Integration 接続

## メニューは出るがボタン文字が見切れる

Render が最新 `main` をデプロイしているか確認してください。

現在の `menu.py` / `ui.py` は全幅1列 UI を基本にしています。

## GAS の GitHub 更新が反映されない

仕様です。

GitHub とスタンドアロン GAS は自動同期していません。

GitHub の `gas/*.gs` を GAS プロジェクトへ手動で反映してください。

---

# 33. 既存環境から今回の最新版へ更新する場合

すでに Bot が動いている場合は、最低限以下を確認してください。

## GitHub / Render

最新 `main` に以下が存在すること:

```text
budget.py
insights.py
ui.py
```

`app.py`、`menu.py`、`memo.py` も最新版へ更新します。

Render が Auto Deploy なら commit 後に自動再デプロイされます。

## Render Environment

追加されていない場合:

```text
ADMIN_USER_ID
SCHEDULER_SECRET
```

を設定してください。

## GAS

最新の以下を反映します。

```text
gas/Code.gs
gas/DailyMemo.gs
gas/FinanceReports.gs
```

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

トリガー:

```text
checkCardEmails           1時間ごと
sendDailyMemoReminder     1日1回
sendDailyBudgetAlert      1日1回
sendWeeklyFinanceReport   週1回
```

---

# 34. 推奨トリガー構成

実用上は次の構成がおすすめです。

| 関数 | 頻度 | 例 |
|---|---|---|
| `checkCardEmails` | 1時間ごと | 毎時 |
| `sendDailyMemoReminder` | 1日1回 | 朝8時前後 |
| `sendDailyBudgetAlert` | 1日1回 | 20時前後 |
| `sendWeeklyFinanceReport` | 週1回 | 日曜20時前後 |

Google Apps Script の時間主導トリガーは指定時刻ちょうどではなく、その時間帯内で実行される場合があります。

---

# 35. 最終動作確認チェックリスト

セットアップ完了後、以下を一通り確認してください。

- [ ] Render `/` が 200
- [ ] LINE Webhook 検証成功
- [ ] `メニュー` が表示される
- [ ] メニュー文字が見切れにくい
- [ ] `今月` が表示される
- [ ] `予算一覧` が表示される
- [ ] `予算アラート` が表示される
- [ ] `週次レポート` が表示される
- [ ] `支出 100 テスト` で支出登録フローに進める
- [ ] `メモ テスト` を保存できる
- [ ] `メモ一覧` で表示できる
- [ ] `メモ削除` で削除前確認が出る
- [ ] `固定費一覧` が表示される
- [ ] URL を送って保存できる
- [ ] `データ追加` が開始できる
- [ ] `checkCardEmails()` の手動実行が成功
- [ ] カード通知が LINE Flex で届く
- [ ] `sendDailyMemoReminder()` が 200
- [ ] `sendDailyBudgetAlert()` が 200
- [ ] `sendWeeklyFinanceReport()` が 200

---

# 36. 現在の既知の改善候補

運用前に把握しておくとよい項目です。

1. 固定費の月内二重登録防止
2. 予算アラートの80/90/100%到達履歴を保存し、同じ閾値を繰り返し通知しない仕組み
3. `/api/register-fixed` と `/api/monthly-notice` の `SCHEDULER_SECRET` 保護
4. `user_states` を外部ストレージへ移し、Render 再起動後も入力途中状態を維持
5. Notion API 通信のリトライ処理強化
6. 自動テスト・CI の追加

---

# 37. 更新作業の基本フロー

Python / Render 側:

```text
GitHub main を更新
↓
Render Deploy
↓
Render Logs
↓
LINE 動作確認
```

GAS 側:

```text
GitHub gas/*.gs を更新
↓
Google Apps Script 側にも反映
↓
対象関数を手動実行
↓
実行ログ確認
↓
トリガー運用
```

---

# 38. 参考: よく使う LINE コマンド

```text
メニュー
今月
支出 1200 ラーメン
予算一覧
予算 100000
予算 食費 30000
予算アラート
週次レポート
固定費
固定費一覧
メモ 牛乳を買う
メモ一覧
メモ削除
データ追加
Notion
ヘルプ
```

これで基本機能を一通り確認できます。
