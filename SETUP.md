# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Google Apps Script・Gmail・Render を連携し、このリポジトリの Bot を**ゼロから構築する手順**と、既存環境を**現在の構成へ更新する手順**をまとめたものです。

README は「システム全体の説明」、SETUP は「実際の導入・更新作業を順番に進める手順書」として分けています。

---

# 1. 完成後の構成

```text
LINE
  ├─ ユーザー操作
  │      ↓ Webhook
  │   Render / Flask / app.py
  │      ├─ Notion API
  │      ├─ 家計簿・予算集計
  │      └─ Gemini API
  │          ※「AI 質問」と送った時だけ
  │
  └─ 通知受信 ← LINE Push API
                  ▲
                  │
         ┌────────┴────────┐
         │                 │
    GAS / Code.gs      Render API
         ▲                 ▲
         │                 │
       Gmail        GAS Timer Trigger
                    ├─ DailyMemo.gs
                    └─ FinanceReports.gs
```

カード通知と通常LINE操作は別経路です。

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

### AI検索

```text
LINE
  ↓
AI 今月の食費を分析して
  ↓
app.py が AI prefix を確認
  ↓
Gemini API
  ↓
LINE Push
```

`AI` を付けていない通常の未登録文字列は Gemini に送りません。

### 定期通知

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

必須:

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

# 3. Notion の準備

## 3.1 Notion Integration を作成

Notion Developers / Integrations で内部インテグレーションを作成し、APIシークレットを取得します。

Render では次の名前で設定します。

```text
NOTION_API_KEY
```

この値を GitHub や GAS ソースコードに直接書かないでください。

---

## 3.2 家計簿 DB

推奨 DB 名:

```text
家計簿
```

必要なプロパティ:

| プロパティ名 | 型 | 用途 |
|---|---|---|
| `内容・店名` | Title | 店名 / 支出内容 |
| `金額` | Number | 支出額 |
| `日付` | Date | 利用日 |
| `ジャンル` | Select | 食費、日用品など |
| `カード・支払方法` | Select | 現金、JCBなど |
| `月別管理` | Relation | 月別管理DBとの接続 |

`ジャンル` の例:

```text
食費
日用品
交通費
娯楽
医療
交際費
```

`カード・支払方法` の例:

```text
現金
JCB
三井住友カード
楽天カード
PayPay
```

Render 環境変数:

```text
NOTION_KAKEIBO_DATABASE_ID
```

---

## 3.3 月別管理 DB

推奨 DB 名:

```text
月別管理
```

必要なプロパティ:

| プロパティ名 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算` | Number |
| `日用品予算` | Number |
| その他 `○○予算` | Number |

`年月` の値は次の形式です。

```text
2026-09
```

ジャンル予算は、家計簿のジャンル名 + `予算` という名前にします。

例:

```text
食費 → 食費予算
交通費 → 交通費予算
```

Render:

```text
NOTION_MONTHLY_DATABASE_ID
```

---

## 3.4 固定費マスタ DB

必要なプロパティ:

| プロパティ名 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

`有効` が ON の項目が固定費登録対象になります。

Render:

```text
NOTION_FIXED_DATABASE_ID
```

---

## 3.5 メモ DB

必要なプロパティ:

| プロパティ名 | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

Render:

```text
NOTION_MEMO_DATABASE_ID
```

---

## 3.6 URL保存 DB

最低限、次のプロパティを用意します。

| プロパティ名 | 型 |
|---|---|
| `URL` | Title |

Render:

```text
NOTION_URL_DATABASE_ID
```

---

## 3.7 Notion DB に Integration を接続

各 DB の共有 / Connections から、作成した Notion Integration を接続してください。

接続されていない DB は API から読み書きできません。

---

# 4. LINE Messaging API の準備

LINE Developers Console で Messaging API チャネルを作成します。

取得するもの:

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

Render へ同名で設定します。

### Webhook

Render デプロイ後、LINE Developers の Webhook URL を次の形式にします。

```text
https://YOUR-RENDER-DOMAIN.onrender.com/callback
```

Webhook を ON にします。

自動応答など LINE Official Account Manager 側の機能が Bot の返信と競合する場合は、必要に応じて OFF にしてください。

---

# 5. Gemini API の準備

Google AI Studio で API Key を作成します。

Render:

```text
GEMINI_API_KEY
```

現在のコードは `gemini-3.6-flash` を使用します。

## 5.1 AIの重要な仕様

AI は通常入力では起動しません。

### AIを使う

```text
AI 今月の食費を分析して
AI メモを整理して
```

### AIを使わない

```text
こんにちは
今日どう？
abc
```

これらが登録済みコマンドでなければ、Bot は

```text
そのコマンドはありません。メニューから機能を選んでください。
```

と返信し、メニューを表示します。

Gemini API の無料枠を無駄に使わないための仕様です。

### `AI` だけ送信した場合

API を呼ばず、AI検索の使い方を表示します。

---

# 6. GitHub リポジトリ

主要ファイル:

```text
app.py
kakeibo.py
budget.py
insights.py
memo.py
menu.py
ui.py
notion_helper.py
prompt.txt
requirements.txt
README.md
SETUP.md
gas/Code.gs
gas/DailyMemo.gs
gas/FinanceReports.gs
gas/README.md
```

各役割:

| ファイル | 主な役割 |
|---|---|
| `app.py` | Webhook、コマンド振り分け、定期API、AI起動判定 |
| `kakeibo.py` | 家計簿保存、固定費、予算保存 |
| `budget.py` | 月次予算一覧、支出集計 |
| `insights.py` | ダッシュボード、予算アラート、週次レポート |
| `memo.py` | メモ追加、一覧、確認付き削除 |
| `menu.py` | メインメニュー |
| `ui.py` | 読みやすい共通Flex UI |
| `notion_helper.py` | Notion汎用操作、Gemini呼び出し |

---

# 7. Render デプロイ

Render Dashboard で GitHub リポジトリを接続し Web Service を作成します。

推奨設定:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

---

# 8. Render 環境変数

以下を設定します。

| Key | 必要な機能 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE |
| `LINE_CHANNEL_SECRET` | LINE Webhook |
| `GEMINI_API_KEY` | AI検索 |
| `NOTION_API_KEY` | Notion |
| `NOTION_KAKEIBO_DATABASE_ID` | 家計簿 |
| `NOTION_MONTHLY_DATABASE_ID` | 予算 |
| `NOTION_FIXED_DATABASE_ID` | 固定費 |
| `NOTION_MEMO_DATABASE_ID` | メモ |
| `NOTION_URL_DATABASE_ID` | URL保存 |
| `NOTION_DATABASE_IDS` | 汎用DB追加 / AI参照 |
| `NOTION_PAGE_URL` | Notionリンク |
| `ADMIN_USER_ID` | 定期LINE Push |
| `SCHEDULER_SECRET` | 定期API認証 |

### `NOTION_DATABASE_IDS`

複数 DB を指定する場合はカンマ区切りです。

```text
id1,id2,id3
```

### `SCHEDULER_SECRET`

30文字以上程度のランダム文字列を推奨します。

Render と GAS Script Properties へ同じ値を設定します。

この値をチャットや GitHub に貼らないでください。

---

# 9. Render 動作確認

デプロイ後、ブラウザで次へアクセスします。

```text
https://YOUR-RENDER-DOMAIN.onrender.com/
```

正常なら:

```text
Bot is running!
```

が表示されます。

---

# 10. GAS プロジェクトの準備

Google Apps Script で1つのプロジェクトを作成し、次のファイルを追加します。

```text
Code.gs
DailyMemo.gs
FinanceReports.gs
```

GitHub の `gas/` フォルダにある最新版をコピーしてください。

GitHub のファイルを更新しても、通常は Google Apps Script 本体へ自動同期されません。

---

# 11. GAS Script Properties

Apps Script:

```text
プロジェクトの設定
  ↓
スクリプト プロパティ
```

## 11.1 カード通知

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

### LINE_USER_ID

通知先ユーザーの LINE User ID です。

### LINE_CHANNEL_ACCESS_TOKEN

Render と同じ LINE Messaging API チャネルの有効な Access Token を設定します。

トークンをソースコードへ直接書かないでください。

---

## 11.2 Render定期通知

```text
RENDER_BASE_URL
SCHEDULER_SECRET
```

例:

```text
RENDER_BASE_URL=https://your-app.onrender.com
```

末尾 `/` は不要です。

`SCHEDULER_SECRET` は Render 側と完全一致させます。

---

# 12. カード通知 GAS

`gas/Code.gs` のメイン関数:

```text
checkCardEmails
```

現在の設計:

- 1時間ごとに実行
- 直近2時間以内を最終処理対象
- Gmail検索はより広い期間で候補取得
- 既読 / 未読を処理条件にしない
- Gmail Message ID で二重通知防止
- LINEへFlex Messageを直接Push
- LINE送信成功後だけ処理済みIDを保存

## 12.1 推奨トリガー

Apps Script の「トリガー」から追加します。

```text
実行する関数: checkCardEmails
イベントのソース: 時間主導型
時間ベースのトリガー: 1時間おき
```

---

# 13. カード通知の手動テスト

GAS エディタから:

```text
checkCardEmails
```

を手動実行します。

初回は Gmail / 外部通信などの権限承認が必要です。

ログで次を確認します。

```text
Gmail検索
ヒットしたスレッド数
候補メール
期間外スキップ
重複スキップ
解析状態
解析成功
LINEレスポンス
処理成功
```

LINEレスポンスが `200` なら Push API は受理されています。

---

# 14. 日次メモ通知

GAS:

```text
sendDailyMemoReminder
```

Render:

```text
POST /api/daily-memo
```

推奨:

```text
毎日 08:00 前後
```

GAS トリガーで1日1回実行します。

---

# 15. 予算アラート

GAS:

```text
sendDailyBudgetAlert
```

Render:

```text
POST /api/budget-alert
```

80%以上に達した予算がなければ LINE Push は行われません。

推奨:

```text
毎日 20:00 前後
```

判定水準:

```text
80%
90%
100%以上
```

---

# 16. 週次レポート

GAS:

```text
sendWeeklyFinanceReport
```

Render:

```text
POST /api/weekly-report
```

推奨:

```text
毎週日曜日 20:00 前後
```

内容:

- 直近7日支出
- 件数
- 前7日との比較
- 増減率
- ジャンル上位

---

# 17. LINE コマンド動作確認

Render のデプロイが完了したら、以下を順番にテストします。

## 17.1 メニュー

```text
メニュー
```

主要機能が1列で表示されれば正常です。

---

## 17.2 家計簿ダッシュボード

```text
今月
```

確認項目:

- 今月支出
- 予算
- 残額
- 残り日数
- 1日あたり利用可能額
- ジャンル上位
- 支払方法別

---

## 17.3 手動支出

```text
支出 1200 ラーメン
```

ジャンル選択 → 支払方法選択 → Notion保存まで確認します。

---

## 17.4 予算

```text
予算 100000
予算 食費 30000
予算一覧
予算アラート
```

---

## 17.5 週次レポート

```text
週次レポート
```

---

## 17.6 メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

削除時に次の流れになることを確認します。

```text
一覧
 ↓
メモ選択
 ↓
削除確認
 ↓
削除する / やめる
```

選択しただけで削除されてはいけません。

---

## 17.7 AI検索

まず:

```text
AI
```

を送信します。

この操作では API を消費せず、使い方が返ります。

次に:

```text
AI 今月の家計簿を分析して
```

を送信します。

Gemini が起動し、後から LINE Push で回答が返れば正常です。

---

## 17.8 未登録コマンド

例:

```text
abcdefg
```

期待結果:

```text
そのコマンドはありません。メニューから機能を選んでください。
```

その後にメインメニューが表示されます。

**Gemini API が呼ばれていないこと**も Render ログで確認してください。

---

# 18. AI API 回数を節約する設計

以前は、どのコマンドにも一致しない入力をすべて Gemini へ送っていました。

現在はこの挙動を廃止しています。

AI呼び出し条件:

```text
^AI[半角/全角スペース]+質問
```

つまり:

```text
AI 質問
```

だけがAI対象です。

この設計により、LINEでの通常操作、タイプミス、雑談、未登録コマンドで Gemini の1日上限を消費しません。

---

# 19. AIモデルを変更したい場合

現在の Gemini 呼び出しは `notion_helper.py` にあります。

モデル名:

```text
gemini-3.6-flash
```

モデル変更時は、コードだけでなく必ず以下も更新してください。

```text
README.md
SETUP.md
```

APIキー名やプロバイダまで変える場合は Render 環境変数も変更が必要です。

---

# 20. Geminiを使い続ける理由

この Bot の AI は主に、Notion情報を含んだ日本語質問への回答や整理に使います。

現時点では Gemini を主AIとして維持する構成です。

理由:

- 日本語性能
- 大きなコンテキスト
- Notion情報をまとめて渡す用途との相性
- `google-genai` ですでに統合済み
- 無料枠がある
- AI prefix 制限により利用回数を大幅に抑えられる

無料回数が不足する場合は、まず別モデル / フォールバックの導入を検討します。

候補:

```text
Gemini Flash-Lite 系
Groq のオープンモデル
OpenAI API
Claude API
```

ただし OpenAI / Claude は基本的に従量課金前提なので、「無料枠を重視する」場合は Gemini Flash-Lite や Groq のほうが候補になりやすいです。

---

# 21. 未登録コマンド設計

新しいコマンドを追加するときは、`app.py` の `handle_message()` に AI 判定より前に追加してください。

重要:

```text
登録済み機能
 ↓
AI prefix 判定
 ↓
未登録コマンド + メニュー
```

この順番を維持します。

これを崩すと、通常コマンドが AI に送られたり、API を無駄に消費する可能性があります。

---

# 22. Render Scheduler API

現在の主な API:

| Endpoint | 用途 | 認証 |
|---|---|---|
| `/api/daily-memo` | 日次メモ | `X-API-KEY` |
| `/api/budget-alert` | 予算アラート | `X-API-KEY` |
| `/api/weekly-report` | 週次レポート | `X-API-KEY` |
| `/api/register-fixed` | 固定費一括登録 | 現在改善候補 |
| `/api/monthly-notice` | 月初予算確認 | 現在改善候補 |

認証付き API では HTTP Header に次を付けます。

```text
X-API-KEY: SCHEDULER_SECRET
```

---

# 23. セキュリティチェック

GitHub へコミットしてはいけないもの:

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GEMINI_API_KEY
NOTION_API_KEY
SCHEDULER_SECRET
LINE_USER_ID
```

GASでは Script Properties、Renderでは Environment Variables を使用します。

もし秘密情報を GitHub、チャット、スクリーンショット等へ公開した場合は、該当トークンを再発行してください。

---

# 24. トラブルシューティング

## LINEから返信がない

Render Logs を確認します。

確認項目:

- アプリが起動しているか
- `/callback` へのアクセス
- LINE署名エラー
- Python例外

---

## 未登録コマンドでGeminiが動いてしまう

Render が古いコミットを動かしている可能性があります。

最新 `main` がデプロイされているか確認します。

現在は未登録コマンドで Gemini を呼ばない仕様です。

---

## `AI 質問` でもAIが動かない

確認項目:

```text
GEMINI_API_KEY
Render Logs
Gemini API quota
```

また `AI` と質問の間にスペースがあるか確認してください。

---

## AIが429になる

Gemini のレート / 日次制限に達している可能性があります。

対策順:

1. AI prefix 以外でAPIを呼んでいないことを確認
2. 翌日の quota reset を待つ
3. Flash-Lite 系を検討
4. 有料枠を検討
5. Groq 等をフォールバックに追加

---

## メニューの文字が見切れる

最新の `menu.py` と `ui.py` が Render にデプロイされているか確認してください。

現在は原則1列表示です。

---

## メモ削除が即時実行される

古い `memo.py` / `app.py` が動いています。

現在は削除確認を1回挟む仕様です。

---

## カード通知が届かない

GAS の実行ログを確認します。

特に:

```text
ヒットしたスレッド数
候補メール
解析成功
LINEレスポンス
```

を確認してください。

`LINEレスポンス: 200` ならLINE API側は送信を受理しています。

---

## 定期通知が401

Render と GAS の `SCHEDULER_SECRET` が一致していません。

---

# 25. Uptime / ヘルスチェック

外部監視を使う場合は Render の `/` を対象にします。

```text
GET https://YOUR-RENDER-DOMAIN.onrender.com/
```

UptimeRobot 等を使用できます。

サービスプランやスリープ仕様は変更される可能性があるため、現在の Render 契約内容に合わせて判断してください。

---

# 26. 既存環境を今回の仕様へ更新する場合

既に Bot を運用中の場合は以下を確認してください。

### GitHub

最新版:

```text
app.py
menu.py
README.md
SETUP.md
```

### Render

GitHub `main` の最新コミットをデプロイ。

### 動作確認

```text
AI
AI テスト
適当な未登録文字列
メニュー
```

期待動作:

```text
AI
→ AI使い方表示 / API未使用

AI テスト
→ Gemini実行

適当な未登録文字列
→ 「そのコマンドはありません」+ メニュー

メニュー
→ AI検索を含む機能一覧
```

---

# 27. ドキュメント更新ルール

今後、機能改善を行った場合は、コード変更だけで終わらせず **README.md と SETUP.md を同じ変更の一部として更新**します。

更新対象になる例:

- 新しいコマンド
- コマンド名変更
- AI起動条件
- AIモデル変更
- UI変更
- Notion DB変更
- 環境変数追加
- GAS Script Properties追加
- トリガー変更
- Render API追加
- セキュリティ方式変更
- 操作フロー変更

README と SETUP の内容が実コードと食い違わない状態を維持してください。

---

# 28. 推奨テストチェックリスト

デプロイ後は以下を確認します。

```text
[ ] GET / が200
[ ] LINE Webhook verify成功
[ ] メニュー表示
[ ] 今月ダッシュボード
[ ] 手動支出登録
[ ] 予算一覧
[ ] 予算アラート
[ ] 週次レポート
[ ] 固定費一覧
[ ] メモ追加
[ ] メモ一覧
[ ] メモ削除確認
[ ] URL保存
[ ] データ追加
[ ] AI 単独でAPIを使わない
[ ] AI 質問 でAPIを使う
[ ] 未登録入力でAIを使わない
[ ] 未登録入力でメニュー表示
[ ] カード通知GAS
[ ] 日次メモGAS
[ ] 予算アラートGAS
[ ] 週次レポートGAS
```

---

# 29. 現在の改善候補

今後の優先候補:

1. 固定費の二重登録防止
2. 予算アラートを80 / 90 / 100%到達時にそれぞれ1回だけ通知
3. `/api/register-fixed` の認証
4. `/api/monthly-notice` の認証
5. `user_states` の永続化
6. Gemini quota 到達時のフォールバック AI

---

# 30. 基本方針

このシステムでは、AIをすべての入力に使うのではなく、

```text
決まった操作 → コマンド処理
曖昧な分析や質問 → AI プレフィックス
```

という役割分担にします。

この方式にすると、家計簿やメモなど重要な操作を安定して処理しながら、Gemini API の無料枠や費用も抑えられます。
