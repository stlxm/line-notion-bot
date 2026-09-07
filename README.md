# LINE Bot 運用・メンテナンス仕様書

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
| `NOTION_DATABASE_IDS` | 参照するNotionデータベースID（複数ある場合はカンマ区切りで指定） |

## Notionデータベースを追加・変更する手順
1. Notion上で新しく参照したいデータベースを開きます。
2. 画面右上のメニューアイコンからコネクトを追加を選択し、作成したインテグレーションを接続します。
3. データベースページのURLから32文字のIDを取得します。（例: notion.so/ の直後にある英数字の文字列）
4. Renderの管理画面を開き、Environment Variables の `NOTION_DATABASE_IDS` の末尾に `,新しいID` の形で追記して保存します。
5. Render側で自動再デプロイが行われ、新しいデータベースが即座に検索対象に入ります。

## プログラムの修正・機能変更手順
1. GitHubの該当リポジトリにアクセスします。
2. 変更したいファイル（`app.py` や `requirements.txt`）を開き、鉛筆マーク（編集）をクリックします。
3. コードを修正後、画面右上の Commit changes ボタンを押して保存します。
4. Renderが自動で変更を検知してビルドを実行します。（反映されない場合は Render の画面から Manual Deploy を実行します）

## トラブルシューティング
* **LINEから返信が来ない場合**
  Renderダッシュボードの Logs タブを開き、赤いエラーメッセージが出ていないか確認します。
* **返信に時間がかかる（10秒以上）場合**
  UptimeRobotを開き、監視ステータスが Up（緑色）になっているか確認します。スリープが発生している場合は監視設定のURLを見直します。
* **Notionのデータが返答に反映されない場合**
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

【システム概要】
Notionの複数データベースの最新情報を取得し、Gemini 3.6 Flashを使ってLINE Botで自動回答するWebアプリケーションです。

【技術スタック】
- Python (Flask) / gunicorn
- LINE Messaging API (line-bot-sdk v3)
- Google GenAI SDK (gemini-3.6-flash)
- Notion API (requestsによる直接HTTPリクエスト方式)
- ホスティング: Render (無料プラン)
- スリープ防止: UptimeRobot (トップページ `/` へ5分間隔でGETリクエスト)

【主要エンドポイント】
- GET `/`: UptimeRobot用のヘルスチェック（200 OK）
- POST `/callback`: LINE Webhook受信用

【環境変数】
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- GEMINI_API_KEY
- NOTION_API_KEY
- NOTION_DATABASE_IDS (カンマ区切りで複数指定)

【現在の状態】
すべての動作確認が完了し、本番環境で正常に稼働中です。この構成を前提に質問や機能追加の相談に答えてください。
