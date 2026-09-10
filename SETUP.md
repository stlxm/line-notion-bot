# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Google Apps Script・Gmail・Render を連携し、この Bot をゼロから構築するための手順書です。

現在の構成では、家計簿・予算・固定費・メモ・カード通知・週次レポート・日次通知・Notion検索・Gemini AI検索に加え、AI回答の失敗例をNotionへ蓄積し、次回以降の回答改善に利用する仕組みも含まれています。

---

# 1. 全体構成

```text
LINE
  ├─ 通常コマンド
  │     ↓
  │   Render / Flask
  │     ├─ 家計簿 / 予算 / メモ
  │     └─ Notion API
  │
  ├─ AI 質問
  │     ↓
  │   Python DB Router
  │     ↓
  │   必要な最大2DBをNotionから取得
  │     ↓
  │   AI改善ログから関連例を最大3件取得
  │     ↓
  │   Gemini 1回
  │     ↓
  │   LINE向けプレーンテキスト整形
  │     ↓
  │   LINE回答
  │
  └─ AI改善
        ↓
      直前の質問・AI回答を保持
        ↓
      「本当はどうしてほしかったか」を入力
        ↓
      AI改善ログDBへ保存

Gmail
  ↓
Google Apps Script
  ↓
LINE Push API
  ↓
カード利用Flex
```

---

# 2. 必要なサービス

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

# 3. Notion DB の作成

プロパティ名はコードと一致させてください。

## 3.1 家計簿 DB

| 名前 | 型 |
|---|---|
| 内容・店名 | Title |
| 金額 | Number |
| 日付 | Date |
| ジャンル | Select |
| カード・支払方法 | Select |
| 月別管理 | Relation |

## 3.2 月別管理 DB

| 名前 | 型 |
|---|---|
| 年月 | Title |
| 全体予算 | Number |
| 食費予算 | Number |
| 日用品予算 | Number |
| その他必要なジャンル予算 | Number |

ジャンル別予算は `ジャンル名 + 予算` の形式にしてください。

## 3.3 固定費マスタ DB

| 名前 | 型 |
|---|---|
| 内容・店名 | Title |
| 金額 | Number |
| ジャンル | Select |
| カード・支払方法 | Select |
| 有効 | Checkbox |

## 3.4 メモ DB

| 名前 | 型 |
|---|---|
| メモ | Title |
| 日付 | Date |

## 3.5 URL保存 DB

| 名前 | 型 |
|---|---|
| URL | Title |

## 3.6 AI改善ログ DB

DB名の例:

```text
AI改善ログ
```

プロパティは次の名前と型で作成してください。

| 名前 | 型 | 用途 |
|---|---|---|
| `質問` | Title | 元のAI質問 |
| `AI回答` | Rich text | 実際に返した回答 |
| `期待する回答` | Rich text | 本当はどう答えてほしかったか |
| `登録日時` | Date | 改善ログ保存日時 |

このDBは通常検索用ではなく、似た質問の改善例だけを取り出す専用DBです。

---

# 4. Notion Integration

1. Notion で Integration を作成します。
2. API Secret を取得します。
3. 家計簿・月別管理・固定費・メモ・URL保存・AI改善ログ・その他AI検索対象DBすべてに Integration を接続します。
4. 各DBの Database ID を控えます。

AI改善ログDBには書き込み権限も必要です。

---

# 5. LINE Messaging API

LINE Developers で Messaging API チャネルを作成します。

取得する値:

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

Webhook URL:

```text
https://YOUR-RENDER-DOMAIN.onrender.com/callback
```

Webhook利用をONにしてください。

---

# 6. Gemini API

Google AI Studio で API Key を作成します。

Render 環境変数:

```text
GEMINI_API_KEY
```

任意:

```text
GEMINI_MODEL
```

未設定時は現在:

```text
gemini-3.6-flash
```

を使用します。

AIは次の形式だけ起動します。

```text
AI 質問内容
```

---

# 7. Render Web Service

推奨設定:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

---

# 8. Render 環境変数

## LINE

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

## Notion

```text
NOTION_API_KEY
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_DATABASE_IDS
NOTION_PAGE_URL
```

専用DBは個別環境変数に入れ、それ以外のAI検索・汎用データ追加対象DBだけを `NOTION_DATABASE_IDS` にカンマ区切りで入れます。

AI改善ログDBは `NOTION_AI_FEEDBACK_DATABASE_ID` 専用なので、`NOTION_DATABASE_IDS` へ重複登録する必要はありません。

## Gemini

```text
GEMINI_API_KEY
GEMINI_MODEL
```

## Scheduler

```text
SCHEDULER_SECRET
```

長いランダム文字列を設定してください。

---

# 9. AI検索の仕組み

現在は以下の構成です。

```text
PythonでDB選択
↓
必要な最大2DBだけNotion取得
↓
AI改善ログから類似例をPythonで検索
↓
Geminiで回答
↓
LINE向けプレーンテキストへ整形
```

原則:

```text
1 AI質問 = Gemini 1回
```

DBルーターはDB用途、DBタイトル、プロパティ名、プロパティ型、質問文、日付表現を利用します。

DBスキーマは約10分キャッシュされます。

---

# 10. LINE向けAI回答の整形

Geminiは通常、Markdown形式で回答することがあります。

例:

```text
## 今月の分析
**食費** は 30,000円です。
- 外食 20,000円
- 自炊 10,000円
```

LINEの通常テキストメッセージではMarkdownが装飾表示されないため、`##` や `**` がそのまま見えて読みにくくなります。

現在は `ai_engine.py` で二重対策しています。

## 10.1 Geminiへの出力指示

Geminiの最終プロンプトで、Markdownを使わずプレーンテキストで回答するよう明示します。

推奨表示:

```text
【今月の分析】
食費は30,000円です。
・外食 20,000円
・自炊 10,000円
```

## 10.2 応答後の自動サニタイズ

GeminiがMarkdownを返してしまった場合も、`sanitize_for_line()` でLINE送信前に整形します。

主な処理:

- `#` / `##` / `###` の見出し記号を除去
- `**` / `__` の装飾記号を除去
- バッククォートとコードフェンスを除去
- `>` の引用記号を除去
- `~~` の取り消し線記号を除去
- Markdownリンクを「表示名 (URL)」へ変換
- `-` / `*` / `+` の箇条書きを `・` に統一
- 過剰な空行を整理

この整形はGemini APIの追加呼び出しを行わないため、API使用回数は増えません。

---

# 11. AI改善機能

まず:

```text
AI 今月の食費について分析して
```

回答が期待と違った場合:

```text
AI改善
```

Botが「本当はどのように答えてほしかったですか？」と聞くので、期待内容を自然文で送ります。

するとAI改善ログDBへ質問、AI回答、期待する回答、登録日時を保存します。

次回以降は最大100件からPythonで類似度を計算し、関連度の高い最大3件だけをGemini最終プロンプトへ参考例として追加します。

改善例検索そのものにはGeminiを使いません。

---

# 12. AIタイムアウト

`app.py` はAI処理を別スレッドで実行し、最大60秒待ちます。

```text
worker.join(timeout=60)
```

現在は60秒を維持します。

Notion DBルーティングとGemini回数を最適化していても、Gemini・Notionの一時的な遅延やAPIリトライに備えて余裕を残しています。

---

# 13. AI改善の一時状態

直前のAI質問とAI回答はRenderのメモリに短期保持します。

`AI改善` の入力完了後はNotionへ永続化されます。

RenderがAI回答直後に再起動すると、直前AI回答の一時情報が消える可能性があります。将来的にはRedisまたは一時ログDBへ永続化する余地があります。

---

# 14. Google Apps Script

GitHubの `gas/` フォルダ:

```text
gas/Code.gs
gas/DailyMemo.gs
gas/FinanceReports.gs
```

## Code.gs

推奨トリガー:

```text
1時間ごと
```

実処理対象:

```text
直近2時間
```

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

## DailyMemo.gs

```text
RENDER_BASE_URL
SCHEDULER_SECRET
```

推奨:

```text
sendDailyMemoReminder
毎日 朝8時前後
```

## FinanceReports.gs

推奨:

```text
sendDailyBudgetAlert
毎日 20時前後

sendWeeklyFinanceReport
毎週日曜日 20時前後
```

---

# 15. 動作確認

Renderデプロイ後、まず通常機能を確認します。

```text
メニュー
今月
予算一覧
予算アラート
週次レポート
メモ一覧
AI
```

AI検索:

```text
AI 今月の食費を分析して
```

回答に次のようなMarkdown記号が残っていないことを確認してください。

```text
**
##
###
```

見出しは `【見出し】`、箇条書きは `・` の形で表示されれば正常です。

続けてAI改善も確認します。

```text
AI改善
```

理想回答を入力し、NotionのAI改善ログDBに1件保存されれば成功です。

---

# 16. AI改善が保存できない場合

確認項目:

1. `NOTION_AI_FEEDBACK_DATABASE_ID` がRenderにあるか
2. DB ID が正しいか
3. Notion Integration がAI改善ログDBに接続されているか
4. プロパティ名が完全一致しているか
5. 型が正しいか

必要な名前:

```text
質問          Title
AI回答        Rich text
期待する回答  Rich text
登録日時      Date
```

---

# 17. AIが違うDBを読む場合

Render Logs にAI Routerの結果が出ます。

例:

```text
[AI Router] 家計簿 score=18.0 reasons=role:食費,prop:金額
```

質問に対して違うDBを選んでいる場合は `notion_helper.py` のルーティングヒントを改善します。

---

# 18. 未登録コマンド

登録されていないコマンドはGeminiを呼ばず:

```text
そのコマンドはありません。メニューから機能を選んでください。
```

と返し、メニューを表示します。

---

# 19. セキュリティ

GitHubに以下を直接書かないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GEMINI_API_KEY
NOTION_API_KEY
SCHEDULER_SECRET
```

Render Environment または GAS Script Properties で管理します。

---

# 20. 今後の改善候補

- AI直前回答の永続化
- AI改善ログの評価機能
- 改善ログが数千件になった場合のEmbedding / ベクトル検索
- AI改善ログからDBルーターも自動改善する仕組み
- 予算アラートの重複通知防止
- 固定費二重登録防止
- Scheduler API認証統一
- `user_states` の永続化

機能変更時は README.md と SETUP.md も同時に更新する方針です。
