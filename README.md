# LINE Bot 運用・メンテナンス仕様書兼 README.md

## システム概要
LINEから送信されたメッセージに対し、Notionのデータベース情報をGemini 3.6 Flashで参照して自動回答する機能、送信されたURLやメモ情報をNotionへ自動追加・保存・削除する機能、クレジットカードの利用通知メール（Gmail/GAS）やLINE手動入力から支出を記録して月別・ジャンル別予算のリアルタイム残高計算や固定費を一括登録する統合家計簿機能、および直感的に操作できるカード型機能メニュー（Flex Message）を備えたWebアプリケーションです。

## 主な機能
1. **カード型機能選択メニュー**
   * LINEで「メニュー」や「機能」と送信すると、家計簿・メモ・設定などの各機能呼び出しボタンがカード型（カルーセルUI）で表示されます。
2. **家計簿自動登録・管理機能**
   * **Gmail/GAS連携（カード通知）**: クレジットカードの利用通知メールをGASが定期検知し、LINEへボタン付きで通知。ジャンルを1タップするだけでNotion家計簿DBへ自動保存。
   * **LINE手動登録**: 「支出 1000 店名」と送信すると、Notion上の選択肢（ジャンル・支払方法）を自動取得してボタン化し、対話形式で保存（「登録しない」キャンセル機能付き）。
   * **予算管理・リアルタイム残高計算**: 月別管理DBと連動し、全体予算およびジャンル別予算の残り金額（あるいは利用合計額）を登録完了時にリアルタイムで返信。
   * **固定費・サブスクの一括登録・個別追加**: Notionの「固定費マスタDB」から有効な固定費を読み込み、LINEコマンド（「固定費」）または毎月1日のGASタイマー実行（/api/register-fixed）で一括登録。「固定費追加 店名 金額」でLINEからの新規登録も可能。
3. **メモ機能**
   * 「メモ 買い物リスト」と送信してNotion「メモDB」へ即座に保存。「メモ一覧」で確認し、「メモ削除」と送信すると保存中のメモがボタン表示され1タップで個別に削除可能。
4. **Notionデータの参照・自動回答**: 設定された複数のNotionデータベースから情報を検索・取得し、Gemini 3.6 Flashを活用して自然な回答をLINEに返信。
5. **Notionへの汎用データ追加・URL保存**: LINEで送信されたURLを「後で見る」DBへ即座に追加。また「データ追加」コマンドにより、対話形式で任意のNotion DBへ新規ページを登録。
6. **常時稼働・ヘルスチェック**: UptimeRobotと連携し、Render無料プランのスリープを防止。

## モジュール・システム構成
* `app.py`: メインのFlaskWebサーバー、LINE Webhook受信用ルーティング、コマンド判定・応答処理、/api/register-fixed エンドポイント。
* `kakeibo.py`: 家計簿機能全般（Notion家計簿DB保存、月別管理DB連動、予算残高計算、固定費一括登録・追加、Flex Messageボタン生成）。
* `memo.py`: メモ機能全般（NotionメモDB保存、一覧取得、削除処理、Flex削除ボタン生成）。
* `menu.py`: 機能選択用カード型UI（Flex Message）の生成。
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
| `NOTION_MEMO_DATABASE_ID` | 「メモ」データベースID |
| `NOTION_DATABASE_IDS` | AI参照・検索対象のNotionデータベースID（複数ある場合はカンマ区切り） |
| `NOTION_URL_DATABASE_ID` | LINEから送られたURLを新規保存するNotionデータベースID |
| `NOTION_PAGE_URL` | NotionページのショートカットURL（「Notion」送信時に案内） |

## Notionデータベースの設定手順

### A. 家計簿・メモ関連データベースの設定
1. **家計簿（支出明細）DB**: 「内容・店名(タイトル)」「金額(数値)」「日付(日付)」「ジャンル(セレクト)」「カード・支払方法(セレクト)」「月別管理(リレーション)」を作成。
2. **月別管理DB**: 「年月(タイトル)」「全体予算(数値)」「○○予算(数値)」「家計簿（支出明細）(リレーション)」を作成。
3. **固定費マスタDB**: 「内容・店名(タイトル)」「金額(数値)」「ジャンル(セレクト)」「カード・支払方法(セレクト)」「有効(チェックボックス)」を作成。
4. **メモDB**: 「メモ(タイトル)」「日付(日付)」を作成。

### B. 参照用データベースの追加・変更
Renderの `NOTION_DATABASE_IDS` の末尾に `,新しいID` の形で追記して保存します（メモDBを含めるとGeminiがメモ内容も検索可能になります）。

## プログラムの修正・機能変更手順
1. GitHubの該当リポジトリにアクセスします。
2. 変更したいファイル（`app.py`, `kakeibo.py`, `memo.py`, `menu.py`, `notion_helper.py`, `requirements.txt`）を編集します。
3. Commit changes ボタンを押して保存すると、Renderが自動でビルドおよび再デプロイを実行します。

## トラブルシューティング
* **LINEから返信が来ない場合**
  Renderダッシュボードの Logs タブを開き、エラーログがないか確認します。
* **家計簿やメモの保存で400エラーが出る場合**
  Notion側のプロパティ名（`内容・店名`, `金額`, `日付`, `メモ` など）や型がコード側の指定と完全一致しているか確認します。
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
Gmailで受け取ったクレジットカード利用通知（GAS経由）やLINEからの手動入力による支出記録、月別・ジャンル別予算の管理、固定費の一括登録、メモの保存・一覧・ボタン削除、WebサイトURLのNotion自動追加保存、そしてNotion内に蓄積されたナレッジベースからのGeminiによる対話型検索回答を一元化するパーソナルアシスタントシステムです。

【主要機能】
1. カード型機能選択メニュー (menu.py)
   「メニュー」または「機能」と送信すると、各機能をワンタップで呼び出せるカード型カルーセルUI（Flex Message）を返信。
2. クレジットカード利用の自動検知・家計簿保存 (GAS連携)
   Gmailに届いたカード利用通知メールをGASが定期検知しRenderへPOST。LINE上のFlex Messageでジャンルボタンを1タップするだけでNotion「家計簿（支出明細）DB」へ保存。
3. LINE手動支出入力
   「支出 金額 店名」と送信すると、Notionからリアルタイム取得した「ジャンル」「カード・支払方法」のセレクト選択肢をボタン表示して対話形式で保存（「登録しない」キャンセル機能付き）。
4. 予算管理とリアルタイム残高通知
   Notion「月別管理DB」と自動でリレーション紐付けを行い、登録完了時に当月の「全体予算の残り」および「該当ジャンル予算の残り」を返信（予算列がないジャンルは「予算なし」と判定）。LINEから「予算 100000」や「予算 食費 30000」で予算設定も可能。
5. 固定費・サブスクの一括登録・個別追加 (GASタイマー連携)
   Notion「固定費マスタDB」から有効な固定費を取得し、LINEで「固定費」と送信するか毎月1日にGASタイマー処理（/api/register-fixed）で家計簿へ自動一括保存。「固定費追加 店名 金額」でLINEから新規追加も可能。
6. メモ機能 (memo.py)
   「メモ テキスト」でNotion「メモDB」へ追加。「メモ一覧」で確認し、「メモ削除」で保存中のメモタイトルがボタン表示され1タップで個別に削除（アーカイブ）。
7. Notionナレッジベース参照・Gemini自動回答
   検索対象のNotion DB（NOTION_DATABASE_IDS）からデータを取得し、Gemini 3.6 Flashを用いて対話形式で回答。
8. 後で見るURL追加 & 汎用対話型データ追加
   LINEで送られたURLを「URL用DB」へ保存。「データ追加」コマンドで任意のNotion DBへ対話形式でデータ登録。
9. スリープ防止
   UptimeRobotによるトップページ（GET /）への5分間隔ヘルスチェック。

【モジュール・全体構成】
- app.py: メインのFlaskアプリ、LINE Webhook受信、コマンド分岐処理、/api/register-fixed エンドポイント
- kakeibo.py: 家計簿DB保存、月別管理DB連動、予算計算、固定費一括登録・追加、Flex Messageボタン生成
- memo.py: メモDB保存、一覧取得、削除処理、削除用Flex Messageボタン生成
- menu.py: 機能選択用カード型カルーセルUI生成
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
- NOTION_MEMO_DATABASE_ID
- NOTION_DATABASE_IDS
- NOTION_URL_DATABASE_ID
- NOTION_PAGE_URL

【現在の状態】
コードは5つのPythonファイル（app.py, kakeibo.py, memo.py, menu.py, notion_helper.py）およびGASで構成されており、全機能が正常に稼働中です。この構成を前提に質問や機能追加の相談に答えてください。
```
