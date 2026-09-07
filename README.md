# LINE Bot 運用・メンテナンス仕様書兼 README.md

## システム概要
LINEから送信されたメッセージに対し、Notionのデータベース情報をGemini 3.6 Flashで参照して自動回答する機能と、送信されたURLやメモ情報をNotionへ自動追加・保存する機能を備えたWebアプリケーションです。

## 主な機能
1. **Notionデータの参照・自動回答**: 設定された複数のNotionデータベースから情報を検索・取得し、Gemini 3.6 Flashを活用して自然な回答をLINEに返信します。
2. **Notionへのデータ追加・保存**: LINEで送信されたURLやテキスト情報を、指定した保存用Notionデータベースへ新規ページとして自動登録します。
3. **常時稼働・ヘルスチェック**: UptimeRobotと連携し、Render無料プランのスリープを防止します。

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
| `NOTION_DATABASE_IDS` | 参照・検索対象のNotionデータベースID（複数ある場合はカンマ区切りで指定） |
| `NOTION_URL_DATABASE_ID` | LINEから送られたURLやデータを新規保存するNotionデータベースID |

## Notionデータベースの設定手順

### A. 参照用データベースを追加・変更する場合
1. Notion上で新しく参照したいデータベースを開きます。
2. 画面右上のメニューからコネクトを追加を選択し、作成したインテグレーションを接続します。
3. データベースページのURLから32文字のIDを取得します。（例: notion.so/ の直後にある英数字の文字列）
4. Renderの Environment Variables にある `NOTION_DATABASE_IDS` の末尾に `,新しいID` の形で追記して保存します。
5. Render側で自動再デプロイが行われ、新しいデータベースが即座に検索対象に入ります。

### B. データ保存用データベースを設定・変更する場合
1. 新規データを保存するためのNotionデータベースを用意し、インテグレーションを接続します。
2. データベースページの32文字のIDを取得します。
3. Renderの Environment Variables にある `NOTION_URL_DATABASE_ID` にそのIDを設定して保存します。

## プログラムの修正・機能変更手順
1. GitHubの該当リポジトリにアクセスします。
2. 変更したいファイル（`app.py` や `requirements.txt`）を開き、鉛筆マーク（編集）をクリックします。
3. コードを修正後、画面右上の Commit changes ボタンを押して保存します。
4. Renderが自動で変更を検知してビルドを実行します。（反映されない場合は Render 画面から Manual Deploy を実行します）

## トラブルシューティング
* **LINEから返信が来ない場合**
  Renderダッシュボードの Logs タブを開き、赤いエラーメッセージが出ていないか確認します。
* **データの追加・保存が失敗する場合**
  `NOTION_URL_DATABASE_ID` が正しく設定されているか、対象のデータベースにコネクトが接続されているか確認します。
* **返信に時間がかかる（10秒以上）場合**
  UptimeRobotを開き、監視ステータスが Up（緑色）になっているか確認します。スリープが発生している場合は監視設定のURLを見直します。
* **Notionのデータが検索返答に反映されない場合**
  Notionの該当ページにコネクトが追加されているか、および Render の `NOTION_DATABASE_IDS` に該当IDが含まれているか確認します。

## システム基本構成
* **AIモデル**: `gemini-3.6-flash`
* **使用ライブラリ**: `Flask`, `requests`, `google-genai`, `line-bot-sdk`, `gunicorn`
* **サーバー環境**: Render Free Plan (Singapore)
* **スリープ対策**: UptimeRobot (HTTP監視 / 5分間隔)

---

## 次回Gemini用 引き継ぎプロンプト

新しいチャットセッションで開発や修正の相談をする際は、以下のテキストをそのまま送信してください。

```text
以下は現在運用中のLINE Botシステムの概要とコード構成です。この文脈を理解した上で開発・デバッグ・機能追加のアシスタントをしてください。

【ボットの目的】
LINE経由で日常的に収集したWebサイトのURLやメモを即座にNotionへ自動追加・保存・整理するとともに、Notion内に蓄積されたナレッジベースから必要な情報をGeminiが検索・抽出し、LINE上で対話形式で迅速に回答すること。情報の一元管理とナレッジの即時活用を目的としています。

【何ができるのか（主要機能）】
1. URL・テキストデータの自動保存
   LINEで送信されたURLやメモを解析し、保存用Notionデータベース（NOTION_URL_DATABASE_ID）へ新規ページとして自動登録・追加します。
2. Notionナレッジベースの参照・自動回答
   参照用Notionデータベース（NOTION_DATABASE_IDS）に保存されている最新情報をリアルタイムで検索・取得し、Gemini 3.6 Flashを使ってLINE上でユーザーからの問い合わせに自然な会話形式で自動回答します。
3. ヘルスチェック・常時稼働維持
   UptimeRobotからの定期GETリクエスト（GET /）を受信し、Renderの無料プラン環境でもスリープさせずに常時稼働を維持します。

【技術スタック】
- Python (Flask) / gunicorn
- LINE Messaging API (line-bot-sdk v3)
- Google GenAI SDK (gemini-3.6-flash)
- Notion API (requestsによる直接HTTPリクエスト方式)
- ホスティング: Render (無料プラン)
- スリープ防止: UptimeRobot (トップページ `/` へ5分間隔でGETリクエスト)

【主要エンドポイント】
- GET `/`: UptimeRobot用のヘルスチェック（200 OK）
- POST `/callback`: LINE Webhook受信用（データ検索・回答およびデータ追加保存処理）

【環境変数】
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- GEMINI_API_KEY
- NOTION_API_KEY
- NOTION_DATABASE_IDS (参照・検索用データベースID。カンマ区切りで複数指定)
- NOTION_URL_DATABASE_ID (URLやデータの追加・保存用データベースID)

【現在の状態】
データ参照・回答機能およびデータ追加機能の両方の動作確認が完了し、本番環境で正常に稼働中です。この構成を前提に質問や機能追加の相談に答えてください。
```
