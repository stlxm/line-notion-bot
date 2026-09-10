# LINE Notion Bot セットアップガイド

この文書は、LINE・Notion・Gemini・Gmail・Google Apps Script・Render を連携し、このBotをゼロから構築し、AIを使わなくても日常保守できるようにするための手順書です。

関連文書:

- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期開発ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UI・Postback設計ルール
- `gas/README.md`: GAS詳細

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
LINEへカード利用通知
```

カード未処理はNotionへ保存されるため、途中で処理をやめても残りから再開できます。

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
4. 書き込みが必要なDBは更新権限も許可する。
5. Database IDをRender環境変数へ設定する。

DBを作り直すとDatabase IDが変わるため、Renderも更新してください。

---

# 4. Notion DB仕様

## 家計簿DB

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

## 月別管理DB

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算` など | Number |

```text
NOTION_MONTHLY_DATABASE_ID
```

## 固定費マスタDB

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

## メモDB

| 名前 | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

```text
NOTION_MEMO_DATABASE_ID
```

## URL保存DB

| 名前 | 型 |
|---|---|
| `URL` | Title |

```text
NOTION_URL_DATABASE_ID
```

## AI改善ログDB

| 名前 | 型 |
|---|---|
| `質問` | Title |
| `AI回答` | Rich text |
| `期待する回答` | Rich text |
| `登録日時` | Date |

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

## カード未処理DB

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

タイトル列はコード側で自動検出できますが、管理上は `GmailMessageID` を推奨します。

家計簿への保存成功、または `登録しない` を選んだ後はページをアーカイブします。

## その他AI検索対象DB

```text
NOTION_DATABASE_IDS=id1,id2,id3
```

専用環境変数があるDBを重複して入れる必要はありません。

---

# 5. LINE Developers

Renderへ設定:

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

Webhook URL:

```text
https://YOUR-RENDER-DOMAIN.onrender.com/callback
```

WebhookをONにします。

アクセストークンをチャットや公開コードへ貼ったことがある場合は再発行し、RenderとGASの両方を更新してください。

---

# 6. Render

推奨:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

ヘルスチェック:

```text
GET /
→ Bot is running!
```

GitHub `main` へのpushで自動デプロイする設定を推奨します。

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

Scheduler:

```text
SCHEDULER_SECRET
```

`SCHEDULER_SECRET` は長いランダム値にし、GASと完全一致させます。

---

# 8. Google Apps Script

同じApps ScriptプロジェクトへGitHubの最新版をコピーします。

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
```

GitHubの `.gs` は通常、自動同期されません。GitHubで更新したらApps Script側にもコピーしてください。

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

`RENDER_BASE_URL` は末尾 `/` なしを推奨します。

---

# 9. GASトリガー

```text
checkCardEmails
→ 1時間ごと

sendDailyCardPendingReminder
→ 毎日 20〜21時ごろ

sendDailyMemoReminder
→ 毎日 朝8時ごろ

sendDailyBudgetAlert
→ 毎日 20時ごろ

sendWeeklyFinanceReport
→ 毎週日曜日 20時ごろ
```

カード通常監視は1時間ごとに動かし、コード内部では直近2時間を検索します。

---

# 10. 2026年9月カード履歴の一括取り込み

Apps Scriptで次を手動実行します。

```text
backfillSeptember2026
```

処理:

```text
9月前後のGmailを検索
↓
本文から実利用日を解析
↓
2026-09の利用だけ採用
↓
カード未処理DBへ追加
↓
個別LINE通知はしない
↓
最後に追加件数だけ通知
```

途中まで処理済みでも、残った未処理だけ後から続けられます。

---

# 11. カード未処理操作

LINEで:

```text
カード未処理
```

表示:

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

古い処理済み通知をもう一度押しても、`pending_id` が無効なら家計簿へ二重登録しません。

---

# 12. LINE Postback 300文字エラー

## 症状

Render Logs:

```text
ValidationError: 1 validation error for PostbackAction
data
ensure this value has at most 300 characters
```

HTTP:

```text
POST /callback → 500
```

## 原因

カード未処理のジャンルボタンへ以下を全部埋め込むと、日本語店名のURLエンコードによって300文字を超える場合があります。

```text
card
store
amount
date
cat
pending_id
```

## 現在の修正版

未処理カードではPostbackを短くしています。

ジャンル選択:

```text
action=kakeibo_save
pending_id=<Notion page id>
cat=<ジャンル>
```

店名変更:

```text
action=card_change_store_start
pending_id=<Notion page id>
```

`app.py` が受信後に:

```text
card_queue.get_item(pending_id)
```

を呼び、Notionからカード名・店名・金額・日付を復元します。

## エラー発生後の復旧

この500エラーはFlex生成段階で発生するため、未処理DBのページは通常そのまま残っています。

1. GitHubの修正版がRenderへデプロイ済みか確認する。
2. Render Logsで起動成功を確認する。
3. LINEで `カード未処理` と送る。
4. 残っている項目から続きを処理する。

9月バックフィルをやり直す必要はありません。

---

# 13. AI検索

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
LINE向けプレーンテキスト
```

AI処理タイムアウトは60秒です。

Markdownは生成指示と送信前サニタイズの二重対策で除去します。

---

# 14. AI改善

```text
AI改善
```

直前の質問、AI回答、本当はどう答えてほしかったか、登録日時をNotionへ保存します。

---

# 15. UIルール

詳細は `UI_DESIGN.md` を参照してください。

重要:

```text
通常操作 → primary / 緑
キャンセル・戻る・登録しない → secondary
カードジャンル → 2列
長い選択肢・メニュー → 原則1列
Postback data → 必ず300文字以内
DBで再取得可能な値 → Postbackへ埋め込まない
```

---

# 16. 動作確認

Render再デプロイ後:

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

カード未処理では:

```text
店名変更ボタンがある
ジャンルが2列
長い店名でも画面が表示される
ジャンル保存できる
保存後に次へ進む
登録しないでも次へ進む
途中でやめても後から再開できる
```

GASでは `checkCardEmails` を手動実行し、正常なら:

```text
[解析成功]
[Render] /api/card-pending: 200
LINEレスポンス: 200
```

を確認します。

---

# 17. トラブル時の最短確認

1. Render最新デプロイ成功?
2. Render Logsに例外?
3. GAS実行履歴にエラー?
4. Notion DBの列名・型は正しい?
5. Integrationは対象DBに接続済み?
6. `SCHEDULER_SECRET` はGAS/Renderで同一?
7. GASへGitHub最新版をコピー済み?
8. FlexエラーならPostback dataが300文字を超えていない?

詳細は `MAINTENANCE.md` を参照してください。

---

# 18. 長期開発

`DEVELOPMENT.md` を唯一の進捗基準にします。

現在はPhase 1「カード自動化」が進行中です。`card_rules.py` の基盤は実装済みですが、まだLINEカード処理には接続していません。

機能追加ごとに:

```text
README.md
SETUP.md
DEVELOPMENT.md
```

を更新し、UI変更なら `UI_DESIGN.md` も更新します。

---

# 19. セキュリティ

GitHub、README、Issue、チャットへ次を貼らないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
```

漏えいしたアクセストークンは再発行し、RenderとGASの両方を更新します。
