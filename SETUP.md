# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Gmail・Google Apps Script・Render を連携して、このBotをゼロから構築し、AIを使わなくても日常保守できる状態にするための手順書です。

関連文書:

- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期開発ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIの設計ルール
- `gas/README.md`: GASの詳細

---

# 1. 全体構成

```text
LINE
  ↓
Render / Flask
  ├─ 家計簿・予算・メモ
  ├─ カード未処理キュー
  ├─ Notion API
  └─ Gemini AI

カード会社メール
  ↓
Gmail
  ↓
Google Apps Script
  ↓
Render /api/card-pending
  ↓
Notion カード未処理DB
  ↓
LINEへカード通知
```

カード未処理はNotionに永続化されるため、途中で処理をやめても問題ありません。保存済み・スキップ済みは未処理DBからアーカイブされ、残りだけ後から続けられます。

---

# 2. 必要なサービス

- GitHub
- Render
- LINE Developers / Messaging API
- Notion
- Gmail
- Google Apps Script
- Google AI Studio / Gemini API

---

# 3. Notion Integration

1. NotionでIntegrationを作成する。
2. Internal Integration Secretを取得する。
3. Botが使うすべてのDBへIntegrationを接続する。
4. 書き込みが必要なDBでは更新権限も有効にする。
5. Database IDをRender環境変数へ設定する。

Notion DBを複製・作り直した場合、Database IDが変わるのでRenderも更新してください。

---

# 4. Notion DB仕様

## 4.1 家計簿DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `日付` | Date |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `月別管理` | Relation |

環境変数:

```text
NOTION_KAKEIBO_DATABASE_ID
```

## 4.2 月別管理DB

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算` など | Number |

ジャンル別予算は `ジャンル名 + 予算` の名前にします。

```text
NOTION_MONTHLY_DATABASE_ID
```

## 4.3 固定費マスタDB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

```text
NOTION_FIXED_DATABASE_ID
```

## 4.4 メモDB

| 名前 | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

```text
NOTION_MEMO_DATABASE_ID
```

## 4.5 URL保存DB

| 名前 | 型 |
|---|---|
| `URL` | Title |

```text
NOTION_URL_DATABASE_ID
```

## 4.6 AI改善ログDB

| 名前 | 型 |
|---|---|
| `質問` | Title |
| `AI回答` | Rich text |
| `期待する回答` | Rich text |
| `登録日時` | Date |

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

このDBは通常のAI検索対象へ混ぜません。

## 4.7 カード未処理DB

一時キュー専用です。

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

```text
NOTION_CARD_PENDING_DATABASE_ID
```

タイトル列はコードが自動検出できますが、管理しやすさのため `GmailMessageID` を推奨します。

保存成功または `登録しない` の後は `archived=true` にして通常表示から消します。

## 4.8 その他のAI検索対象DB

専用環境変数がない追加DBだけをカンマ区切りで入れます。

```text
NOTION_DATABASE_IDS=id1,id2,id3
```

---

# 5. LINE Developers

取得する値:

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

Webhook URL:

```text
https://YOUR-RENDER-DOMAIN.onrender.com/callback
```

WebhookをONにします。

Channel Access Tokenをチャットや公開コードへ貼った場合は再発行し、RenderとGASの両方を更新してください。

---

# 6. Render Web Service

推奨設定:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

GitHubの `main` へpushされたら自動デプロイする設定を推奨します。

ルート確認:

```text
GET /
→ Bot is running!
```

---

# 7. Render環境変数

LINE:

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

Notion:

```text
NOTION_API_KEY
NOTION_PAGE_URL
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
NOTION_DATABASE_IDS
```

Gemini:

```text
GEMINI_API_KEY
GEMINI_MODEL
```

定期API:

```text
SCHEDULER_SECRET
```

`SCHEDULER_SECRET` は長いランダム文字列にし、GAS側と完全に同じ値を使います。

---

# 8. Google Apps Script

GitHub側の最新コードを同じApps Scriptプロジェクトへコピーします。

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
```

通常のApps ScriptプロジェクトはGitHubと自動同期されません。GitHub側の `.gs` を変更したら、Apps Script側へもコピーしてください。

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

`RENDER_BASE_URL` は末尾 `/` なしを推奨します。

例:

```text
https://line-notion-bot.onrender.com
```

---

# 9. GASトリガー

## カード通常監視

```text
checkCardEmails
→ 1時間ごと
```

実際の検索対象は直近2時間です。1時間ごとに2時間を見ることで多少の実行ずれに耐えます。

## カード未処理リマインダー

```text
sendDailyCardPendingReminder
→ 1日1回 20〜21時ごろ
```

未処理が0件なら通知しません。

## メモ通知

```text
sendDailyMemoReminder
→ 毎日 朝8時ごろ
```

## 予算通知

```text
sendDailyBudgetAlert
→ 毎日 20時ごろ
```

## 週次レポート

```text
sendWeeklyFinanceReport
→ 毎週日曜日 20時ごろ
```

---

# 10. 2026年9月カード履歴の一括取り込み

Apps Scriptで:

```text
backfillSeptember2026
```

を手動実行します。

処理:

```text
9月前後のGmailを検索
↓
メール本文から実利用日を解析
↓
2026-09の利用だけ採用
↓
未処理DBへ追加
↓
1件ずつはLINE通知しない
↓
最後に追加件数だけ通知
```

途中までジャンル処理済みでも問題ありません。保存済みはキューから消えているため、残りだけ処理できます。

---

# 11. カード未処理操作

LINEで:

```text
カード未処理
```

と送ります。

表示内容:

```text
金額
利用先
カード
利用日
残り件数
```

操作:

```text
ジャンル → 緑・2列
店名を変更する → 緑
登録しない → 色なし
```

保存成功後は未処理ページをアーカイブし、自動で次の未処理を表示します。

古いLINE通知を再度押した場合、`pending_id` がすでに処理済みなら家計簿へ二重登録しません。

---

# 12. AI検索

起動:

```text
AI 今月の食費を分析して
```

処理:

```text
PythonでDB選択
↓
最大2DB取得
↓
AI改善ログから関連例を最大3件選択
↓
Gemini最終回答1回
↓
LINE向けプレーンテキスト整形
```

通常コマンドではGeminiを使いません。

AIタイムアウト:

```text
60秒
```

Markdownは禁止し、送信前にも `**`、`##`、コードフェンス等を除去します。

---

# 13. AI改善

AI回答後:

```text
AI改善
```

Botが「本当はどう答えてほしかったか」を聞きます。

保存内容:

```text
質問
AI回答
期待する回答
登録日時
```

似た質問では改善例をPythonで選び、最終プロンプトへ加えます。

---

# 14. UIルール

詳細は `UI_DESIGN.md` を参照してください。

原則:

```text
通常操作・保存・選択 → primary / 緑
キャンセル・戻る     → secondary
登録しない           → secondary
削除                 → 確認画面を挟む
```

カードジャンルは2列、長い選択肢とメニューは原則1列です。

将来はメインメニューを次のカテゴリ型へ移行します。

```text
🏠 今日
💰 家計簿
💳 カード
🎯 予算・目標
📝 メモ・保存
🤖 AI
⚙️ その他
```

---

# 15. 基本動作確認

デプロイ後に順番に確認します。

```text
メニュー
カード未処理
今月
予算一覧
予算アラート
週次レポート
メモ一覧
AI
```

カードでは:

```text
未処理表示
→ 店名変更できる
→ ジャンルが2列
→ 保存
→ 未処理から消える
→ 次が自動表示
```

GASでは `checkCardEmails` を手動実行し、ログに:

```text
[解析成功]
[Render] /api/card-pending: 200
LINEレスポンス: 200
```

が出ることを確認します。

---

# 16. トラブル時の最短確認

詳しくは `MAINTENANCE.md` を参照してください。

最短チェック:

1. Render最新デプロイ成功?
2. Render Logsに例外?
3. GAS実行履歴にエラー?
4. Notion DB列名・型が一致?
5. IntegrationがDBへ接続?
6. `SCHEDULER_SECRET` がGASとRenderで一致?
7. GASへGitHub最新版をコピーした?

---

# 17. 開発を再開するとき

必ず `DEVELOPMENT.md` を開いて、

```text
次に再開する場所
```

から進めます。

現在はPhase 1「カード自動化」が次の開発対象です。

機能追加のたびに:

```text
README.md
SETUP.md
DEVELOPMENT.md
```

を更新し、UI変更なら `UI_DESIGN.md` も更新します。

---

# 18. セキュリティ

GitHub、README、Issue、チャットへ次を貼らないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
```

漏えいしたアクセストークンは再発行し、RenderとGASの両方を更新します。
