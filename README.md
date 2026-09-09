# LINE Bot 運用・メンテナンス仕様書兼 README.md

## システム概要
LINEから送信されたメッセージに対し、Notionのデータベース情報をGemini 3.6 Flashで参照して自動回答する機能、送信されたURLやメモ情報をNotionへ自動追加・保存する機能、およびクレジットカードの利用通知メール（Gmail/GAS）やLINE手動入力から支出を記録し、月別・ジャンル別予算のリアルタイム残高計算や固定費を一括登録する統合家計簿機能を備えたWebアプリケーションです。

## 主な機能
1. **家計簿自動登録・管理機能**
   * **Gmail/GAS連携（カード通知）**: クレジットカード（JCB, 三井住友, PayPay, 楽天等）の利用通知メールをGASが定期検知し、Render（LINE Bot）へ送信。LINEのFlex Messageでジャンルを1タップするだけでNotion家計簿DBへ自動保存。
   * **LINE手動登録**: 「支出 1000 店名」と送信すると、Notion上の選択肢（ジャンル・支払方法）を自動取得してボタン化し、対話形式で保存（「登録しない」キャンセル機能付き）。
   * **予算管理・リアルタイム残高計算**: 月別管理DBと連動し、全体予算およびジャンル別予算の残り金額（あるいは利用合計額）を登録完了時にリアルタイムで返信。
   * **固定費・サブスク一括登録**: Notionの「固定費マスタDB」から有効な固定費を読み込み、LINEコマンド（「固定費」）または毎月1日のGASタイマー実行（/api/register-fixed）で一括登録。
2. **Notionデータの参照・自動回答**: 設定された複数のNotionデータベースから情報を検索・取得し、Gemini 3.6 Flashを活用して自然な回答をLINEに返信。
3. **Notionへの汎用データ追加・URL保存**: LINEで送信されたURLを「後で見る」DBへ即座に追加。また「データ追加」コマンドにより、対話形式で任意のNotion DBへ新規ページを登録。
4. **常時稼働・ヘルスチェック**: UptimeRobotと連携し、Render無料プランのスリープを防止。

## モジュール・システム構成
* `app.py`: メインのFlaskWebサーバー、LINE Webhook受信用ルーティング、コマンド判定・応答処理、/api/register-fixed エンドポイント。
* `kakeibo.py`: 家計簿機能全般（Notion家計簿DB保存、月別管理DB連動、予算残高計算、固定費一括登録、Flex Messageボタン生成）。
* `notion_helper.py`: Notion全DB参照、Gemini検索回答生成、後で見るURL保存、汎用データ追加機能。
* **Google Apps Script (GAS)**: Gmailのカード利用通知メール検知（10分間隔実行）および毎月1日の固定費自動登録API実行（月1回実行）。

## 管理用URL一覧
* **GitHubリポジトリ**: https://github.com/
* **Renderダッシュボード**: https://dashboard.render.com
* **LINE Developersコンソール**: https://developers.line.biz/console/
* **Google AI Studio**: https://aistudio.google.com/
* **UptimeRobotダッシュボード**: https://uptimerobot.com/dashboard

## 環境変数一覧（Render設定情報）

| Key | 設定内容・役割 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging APIのチャネルアクセストークン（長期） |
| `LINE_CHANNEL_SECRET` | LINE Messaging APIのチャネルシークレット |
| `GEMINI_API_KEY` | Google AI Studioで発行したAPIキー |
| `NOTION_API_KEY` | Notion内部インテグレーションシークレット |
| `NOTION_KAKEIBO_DATABASE_ID` | 「家計簿（支出明細）」データベースID |
| `NOTION_MONTHLY_DATABASE_ID` | 「月別管理」データベースID |
| `NOTION_FIXED_DATABASE_ID` | 「固定費マスタ」データベースID |
| `NOTION_DATABASE_IDS` | AI参照・検索対象のNotionデータベースID（複数ある場合はカンマ区切り） |
| `NOTION_URL_DATABASE_ID` | LINEから送られたURLを新規保存するNotionデータベースID |
| `NOTION_PAGE_URL` | NotionページのショートカットURL（「Notion」送信時に案内） |

## GAS (Google Apps Script) の設定・トリガー仕様

1. **カード通知検知スクリプト（10分間隔トリガー）**
   * Gmail内の未読通知メールを検索・パースし、Renderの `/callback`（`CARD_NOTIFY|カード名|店名|金額|日付`）へPOSTします。
2. **月初固定費自動登録スクリプト（月ベースタイマー / 毎月1日実行）**
   * 毎月1日の朝に Render の `/api/register-fixed` へPOSTリクエストを送り、固定費マスタから当月分の固定費を家計簿DBへ自動一括登録します。

## Notionデータベースの設定手順

### A. 家計簿関連データベースの設定
1. **家計簿（支出明細）DB**: 「内容・店名(タイトル)」「金額(数値)」「日付(日付)」「ジャンル(セレクト)」「カード・支払方法(セレクト)」「月別管理(リレーション)」を作成。
2. **月別管理DB**: 「年月(タイトル)」「全体予算(数値)」「○○予算(数値)」「家計簿（支出明細）(リレーション)」を作成。
3. **固定費マスタDB**: 「内容・店名(タイトル)」「金額(数値)」「ジャンル(セレクト)」「カード・支払方法(セレクト)」「有効(チェックボックス)」を作成。

### B. 参照用データベースの追加・変更
Renderの `NOTION_DATABASE_IDS` の末尾に `,新しいID` の形で追記して保存します。

## プログラムの修正・機能変更手順
1. GitHubの該当リポジトリにアクセスします。
2. 変更したいファイル（`app.py`, `kakeibo.py`, `notion_helper.py`, `requirements.txt`）を編集します。
3. Commit changes ボタンを押して保存すると、Renderが自動でビルドおよび再デプロイを実行します。

## トラブルシューティング
* **LINEから返信が来ない場合**
  Renderダッシュボードの Logs タブを開き、エラーログがないか確認します。
* **家計簿の保存で400エラーが出る場合**
  Notion側のプロパティ名（`内容・店名`, `金額`, `日付`, `ジャンル`, `カード・支払方法`, `月別管理`）や型（セレクト/リレーションなど）が完全一致しているか確認します。
* **カード通知が届かない場合**
  GASの実行数ログを開き、エラーの発生有無やGmail検索クエリに合致するメールが存在するか確認します。

## システム基本構成
* **AIモデル**: `gemini-3.6-flash`
* **使用ライブラリ**: `Flask`, `requests`, `google-genai`, `line-bot-sdk v3`, `gunicorn`
* **サーバー環境**: Render Free Plan
* **外部連携**: Google Apps Script (Gmail検知・定時実行), UptimeRobot (HTTP監視 / 5分間隔)

---

## 次回Gemini用 引き継ぎプロンプト

新しいチャットセッションで開発や修正の相談をする際は、以下のテキストをそのまま送信してください。

```text
以下は現在運用中のLINE Botシステムの概要とコード構成です。この文脈を理解した上で開発・デバッグ・機能追加のアシスタントをしてください。

【ボットの目的】
Gmailで受け取ったクレジットカード利用通知（GAS経由）やLINEからの手動入力による支出記録、月別・ジャンル別予算の管理、固定費の一括登録、WebサイトURLやメモのNotion自動追加・保存、そしてNotion内に蓄積されたナレッジベースからのGeminiによる対話型検索回答を一元化するパーソナルアシスタントシステムです。

【主要機能】
1. クレジットカード利用の自動検知・家計簿保存 (GAS連携)
   Gmailに届いたカード利用通知メール（JCB, 三井住友, PayPay, 楽天など）をGASが10分間隔で定期検知し、RenderへPOST送信。LINE上のFlex Messageでジャンルボタンを1タップするだけでNotion「家計簿（支出明細）DB」へ保存。
2. LINE手動支出入力
   「支出 金額 店名」と送信すると、Notionからリアルタイム取得した「ジャンル」「カード・支払方法」のセレクト選択肢をボタン表示して対話形式で保存（「登録しない」キャンセル機能付き）。
3. 予算管理とリアルタイム残高通知
   Notion「月別管理DB」と自動でリレーション紐付けを行い、登録完了時に当月の「全体予算の残り」および「該当ジャンル予算の残り」を返信（予算列がないジャンルは「予算なし」と判定）。LINEから「予算 100000」や「予算 食費 30000」で予算設定も可能。
4. 固定費・サブスクの一括登録 (GASタイマー連携)
   Notion「固定費マスタDB」から有効な固定費を取得し、LINEで「固定費」と送信するか、毎月1日にGASのタイマー処理（/api/register-fixed）を呼び出して家計簿へ自動一括保存。
5. Notionナレッジベース参照・Gemini自動回答
   検索対象のNotion DB（NOTION_DATABASE_IDS）からデータを取得し、Gemini 3.6 Flashを用いて対話形式で回答。
6. 後で見るURL追加 & 汎用対話型データ追加
   LINEで送られたURLを「URL用DB」へ保存。「データ追加」コマンドで任意のNotion DBへ対話形式でデータ登録。
7. スリープ防止
   UptimeRobotによるトップページ（GET /）への5分間隔ヘルスチェック。

【モジュール・全体構成】
- app.py: メインのFlaskアプリ、LINE Webhook受信、コマンド分岐処理、/api/register-fixed エンドポイント
- kakeibo.py: 家計簿DB保存、月別管理DB連動、予算計算、固定費一括登録、Flex Messageボタン生成
- notion_helper.py: Notionデータ検索、Gemini回答生成、URL追加、汎用データ追加処理
- Google Apps Script (GAS): Gmailカード利用通知の定期検知・送信、毎月1日の固定費自動一括登録リクエスト

【技術スタック】
- Python (Flask) / gunicorn
- LINE Messaging API (line-bot-sdk v3)
- Google GenAI SDK (gemini-3.6-flash)
- Google Apps Script (GAS)
- Notion API (requestsによる直接HTTPリクエスト方式)
- ホスティング: Render (無料プラン)
- スリープ防止: UptimeRobot

【環境変数 (Render)】
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- GEMINI_API_KEY
- NOTION_API_KEY
- NOTION_KAKEIBO_DATABASE_ID
- NOTION_MONTHLY_DATABASE_ID
- NOTION_FIXED_DATABASE_ID
- NOTION_DATABASE_IDS
- NOTION_URL_DATABASE_ID
- NOTION_PAGE_URL

【現在の状態】
コードは3つのPythonファイル（app.py, kakeibo.py, notion_helper.py）およびGASで構成されており、全機能（自動通知・手動入力・予算管理・固定費登録・検索回答・URL保存）が正常に本番稼働中です。この構成を前提に質問や機能追加の相談に答えてください。
```
