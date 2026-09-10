# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Google Apps Script・Gmail・Render を連携して、このBotをゼロから構築する手順と、既存環境を現在の構成へ更新する手順をまとめたものです。

README は全体仕様、SETUP は実際の設定作業を順番に進めるための手順書です。

---

# 1. 完成後の構成

```text
LINE
  ├─ 通常コマンド
  │    ↓
  │  Render / Flask / app.py
  │    ├─ 家計簿
  │    ├─ 予算
  │    ├─ メモ
  │    └─ Notion操作
  │
  ├─ AI 質問
  │    ↓
  │  Python DB Router
  │    ↓ 最大2DB
  │  Notion API
  │    ↓
  │  Gemini 最終回答 1回
  │
  └─ 通知受信 ← LINE Push API
                    ▲
          ┌─────────┴─────────┐
          │                   │
      GAS Code.gs       Render定期API
          ▲                   ▲
          │                   │
        Gmail          GAS Timer Trigger
```

AI検索ではGeminiをDB選択に使わず、Python側で必要なDBを判定します。

---

# 2. 必要なサービス

- GitHub
- Render
- LINE Developers
- Notion
- Googleアカウント
  - Gmail
  - Google Apps Script
  - Google AI Studio / Gemini API

任意:

- UptimeRobot等の外部監視

---

# 3. Notionデータベース

このBotでは複数のNotion DBを扱えます。

専用機能用DBは以下の環境変数で個別に設定します。

## 家計簿DB

推奨プロパティ:

```text
内容・店名            Title
金額                  Number
日付                  Date
ジャンル              Select
カード・支払方法      Select
月別管理              Relation
```

## 月別管理DB

```text
年月                  Title
全体予算              Number
食費予算              Number
日用品予算            Number
その他必要な予算列    Number
```

## 固定費マスタDB

```text
内容・店名            Title
金額                  Number
ジャンル              Select
カード・支払方法      Select
有効                  Checkbox
```

## メモDB

```text
メモ                  Title
日付                  Date
```

## URL保存DB

```text
URL                   Title
```

---

# 4. 9個など多数DBがある場合の設定

すべてのDB IDを `NOTION_DATABASE_IDS` に重複して入れる必要はありません。

専用DBはそれぞれの専用環境変数に設定します。

```text
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
```

そして、それ以外でAIにも参照させたいDBだけを、

```text
NOTION_DATABASE_IDS
```

にカンマ区切りで入れます。

例えばDBが9個あり、5個が専用DBなら:

```text
専用変数 = 5DB
NOTION_DATABASE_IDS = 残り4DB
```

で合計9DBがAI検索候補になります。

コード側で専用DBと追加DBを自動統合し、同じDB IDが重複していても除去します。

### 推奨運用

`NOTION_DATABASE_IDS` には「追加DBだけ」を入れてください。

これによりRender環境変数の管理が楽になります。

---

# 5. Notion Integration

1. Notion Integrationを作成
2. Secretを取得
3. Botが使う各DBへIntegrationを接続
4. 各DB IDを取得
5. Render環境変数へ登録

重要:

AI候補に含めても、そのDBにIntegration権限がなければ読み取れません。

9DBすべてをAI検索対象にしたい場合は、9DBすべてへ同じNotion Integrationを接続してください。

---

# 6. LINE Messaging API

Renderに次を設定します。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

Webhook URL:

```text
https://YOUR-RENDER-URL.onrender.com/callback
```

Webhook利用をONにします。

---

# 7. Gemini API

Google AI StudioでAPIキーを作成します。

Render:

```text
GEMINI_API_KEY=...
```

モデルは環境変数でも変更できます。

```text
GEMINI_MODEL=gemini-3.6-flash
```

未設定なら `gemini-3.6-flash` を使用します。

---

# 8. AI検索の現在の動作

AIは `AI ` で始まるメッセージだけで起動します。

```text
AI 今月の食費を分析して
```

通常メッセージや未登録コマンドではGemini APIを呼びません。

## AI処理フロー

```text
AI 質問
 ↓
専用DB + NOTION_DATABASE_IDS を統合
 ↓
DBスキーマを取得 / 10分キャッシュ
 ↓
Pythonで関連度を計算
 ↓
最大2DBを選択
 ↓
必要なデータだけNotionから取得
 ↓
Geminiを1回だけ呼ぶ
 ↓
LINEへ回答
```

以前の「GeminiでDB選択 → Geminiで回答」という2回呼び出し方式は使いません。

---

# 9. AIルーターが見る情報

Python側で次を利用します。

- DBの専用用途
- DBタイトル
- プロパティ名
- プロパティ型
- 質問キーワード
- 日付表現

専用用途例:

```text
支出 / 食費 / カード
→ 家計簿

予算 / 残額
→ 月別管理

固定費 / サブスク
→ 固定費

メモ / TODO
→ メモ

URL / リンク
→ URL保存
```

追加DBはDBタイトルとプロパティ名から自動的に関連度を計算します。

そのため、9DBの正式名称をコードに全部ハードコードしなくても動作します。

---

# 10. 日付フィルター

AI質問に日付語がある場合、日付プロパティを持つDBではNotion検索時点で期間を絞ります。

対応:

```text
今日
昨日
今週
先週
今月
先月
今年
```

例:

```text
AI 今月の家計簿を分析して
```

なら、家計簿全履歴ではなく今月分だけを取得します。

---

# 11. AI負荷制限

現在の設定:

```text
MAX_AI_DATABASES = 2
MAX_ROWS_PER_DB = 40
MAX_CONTEXT_CHARS = 18000
_SCHEMA_CACHE_TTL = 600秒
```

目的:

- Notion API負荷削減
- Gemini入力削減
- 応答時間短縮
- API回数節約
- 無関係なDB情報を回答に混ぜない

---

# 12. 60秒タイムアウト

`app.py` ではAI検索をバックグラウンドで処理し、最大60秒待機します。

```text
worker.join(timeout=60)
```

現時点では60秒を維持してください。

理由:

- Notionアクセスが含まれる
- Geminiが混雑時に遅くなる場合がある
- 503 / 429等でリトライが発生する場合がある

DB選択のGemini呼び出しを削除したため以前より軽くなっていますが、安定性重視で60秒を安全弁として残します。

---

# 13. Render環境変数

## LINE

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

## Gemini

```text
GEMINI_API_KEY
GEMINI_MODEL
```

## Notion

```text
NOTION_API_KEY
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_DATABASE_IDS
NOTION_PAGE_URL
```

## Scheduler

```text
SCHEDULER_SECRET
```

---

# 14. Renderデプロイ

Render Web Service:

```text
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn app:app
```

GitHubの `main` ブランチを自動デプロイ対象にします。

---

# 15. GAS Script Properties

Google Apps ScriptのScript Propertiesに設定します。

カード通知:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

定期通知:

```text
RENDER_BASE_URL
SCHEDULER_SECRET
```

秘密鍵やアクセストークンをコードへ直接書かないでください。

---

# 16. カード通知GAS

GitHub:

```text
gas/Code.gs
```

現在の推奨設定:

```text
checkCardEmails
1時間ごと
```

コード側では実処理対象を直近2時間に設定しています。

カードメールを見つけるとGASがLINE Push APIへFlex Messageを直接送ります。

Renderの `/callback` に疑似WebhookをPOSTする方式ではありません。

---

# 17. 日次メモ通知

GitHub:

```text
gas/DailyMemo.gs
```

関数:

```text
sendDailyMemoReminder
```

推奨:

```text
毎日 08:00前後
```

Render:

```text
POST /api/daily-memo
```

---

# 18. 予算アラート

GitHub:

```text
gas/FinanceReports.gs
```

関数:

```text
sendDailyBudgetAlert
```

推奨:

```text
毎日 20:00前後
```

80%以上の予算項目がある場合のみLINEへ通知します。

Render:

```text
POST /api/budget-alert
```

---

# 19. 週次レポート

関数:

```text
sendWeeklyFinanceReport
```

推奨:

```text
毎週日曜日 20:00前後
```

Render:

```text
POST /api/weekly-report
```

---

# 20. LINE動作確認

## メニュー

```text
メニュー
```

## 家計簿

```text
支出 1200 ラーメン
```

## ダッシュボード

```text
今月
```

## 予算

```text
予算 100000
予算 食費 30000
予算一覧
予算アラート
```

## 週次

```text
週次レポート
```

## メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

## AI

```text
AI 今月の支出を分析して
AI メモを整理して
```

## 未登録コマンド確認

```text
abcdefg
```

期待:

```text
そのコマンドはありません。
```

+ メニュー表示

Geminiは呼び出されません。

---

# 21. AIルーターログ確認

Render Logsで以下を確認できます。

```text
[AI Router] DB名 score=... reasons=...
```

質問と違うDBを選択している場合は、`notion_helper.py` の `ROLE_HINTS` や実際のDB名・プロパティ名を見て調整できます。

---

# 22. 9DBを設定した後のテスト

最低限次を試してください。

```text
AI 今月の食費はいくら？
AI 予算について分析して
AI 固定費を整理して
AI メモの内容をまとめて
AI <追加DBの名前に関する質問>
```

Render Logsで毎回1〜2DBだけ選ばれていることを確認します。

---

# 23. Notion DBを追加した場合

専用機能ではない新規DBなら:

1. Notion IntegrationをそのDBへ接続
2. DB IDを取得
3. `NOTION_DATABASE_IDS` の末尾へ追加
4. Renderを再デプロイ

専用DBを追加・変更する場合は該当する専用環境変数を更新します。

---

# 24. トラブルシューティング

## AIが返らない

確認:

- `AI ` を先頭に付けているか
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- Gemini API上限
- Render Logs
- Notion Integration権限

## 60秒タイムアウト

Render Logsで:

- `[AI Router]` が出ているか
- Notion APIエラーがないか
- Gemini 429 / 503がないか

を確認します。

## AIが違うDBを見る

Render Logsのスコアを確認し、DBタイトルまたはプロパティ名が質問と一致しやすい名前になっているか確認します。

## 追加DBが検索されない

- `NOTION_DATABASE_IDS` にIDがあるか
- カンマ区切りが正しいか
- Integrationが接続されているか

## カード通知が来ない

GAS Logsで検索件数・対象日時・LINEレスポンスを確認します。

---

# 25. セキュリティ

以下はGitHubへ書かないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
```

Render EnvironmentまたはGAS Script Propertiesで管理します。

---

# 26. 今後の更新ルール

今後、機能追加や仕様変更を行う場合は、実装コードだけでなく **README.md と SETUP.md も同時に更新**します。
