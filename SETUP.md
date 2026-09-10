# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Google Apps Script・Gmail・Render を連携し、この Bot をゼロから構築するための手順書です。

現在の構成では、家計簿・予算・固定費・メモ・カード通知・週次レポート・日次通知・Notion検索・Gemini AI検索に加え、**AI回答の失敗例をNotionへ蓄積し、次回以降の回答改善に利用する仕組み**も含まれています。

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

推奨プロパティ:

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

最低限:

| 名前 | 型 |
|---|---|
| URL | Title |

## 3.6 AI改善ログ DB

今回追加された重要なDBです。

DB名は自由ですが、例として:

```text
AI改善ログ
```

とします。

プロパティは**次の名前と型で作成してください**。

| 名前 | 型 | 用途 |
|---|---|---|
| `質問` | Title | 元のAI質問 |
| `AI回答` | Rich text | 実際に返した回答 |
| `期待する回答` | Rich text | 本当はどう答えてほしかったか |
| `登録日時` | Date | 改善ログ保存日時 |

このDBは通常の検索対象DBとは役割が違います。

通常のNotion情報としてGeminiへ丸ごと渡すのではなく、`ai_feedback.py` が**似た質問の改善例だけを取り出す専用DB**として利用します。

---

# 4. Notion Integration

1. Notion で Integration を作成します。
2. API Secret を取得します。
3. 家計簿・月別管理・固定費・メモ・URL保存・AI改善ログ・その他AI検索対象DBすべてに Integration を接続します。
4. 各DBの Database ID を控えます。

AI改善ログDBに Integration の編集権限がない場合、`AI改善` の保存に失敗します。

---

# 5. LINE Messaging API

LINE Developers で Messaging API チャネルを作成します。

取得する値:

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

Webhook URL は Render デプロイ後に設定します。

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

任意で:

```text
GEMINI_MODEL
```

を設定できます。

未設定時は現在:

```text
gemini-3.6-flash
```

を使用します。

AIは通常メッセージでは呼ばれません。

```text
AI 質問内容
```

という形式だけGeminiを使用します。

---

# 7. Render Web Service

GitHub リポジトリを Render の Web Service として接続します。

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

`ADMIN_USER_ID` は日次通知・週次レポート等の送信先 LINE User ID です。

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

### NOTION_DATABASE_IDS の考え方

専用DBは個別環境変数へ入れます。

```text
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
```

それ以外のAI検索・汎用データ追加対象DBだけを `NOTION_DATABASE_IDS` にカンマ区切りで入れます。

例として現在DBが10個あり、

- 家計簿
- 月別管理
- 固定費
- メモ
- URL保存
- AI改善ログ
- その他4DB

という構成なら、`NOTION_DATABASE_IDS` にはその他4DBだけ入れる運用が推奨です。

`NOTION_AI_FEEDBACK_DATABASE_ID` はAI改善専用なので `NOTION_DATABASE_IDS` へ重複登録する必要はありません。

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

現在のAI検索はAPI節約のため2段階Gemini方式を廃止しています。

## 以前

```text
GeminiでDB選択
↓
Notion取得
↓
Geminiで回答
```

1質問につき最大2 Geminiリクエストでした。

## 現在

```text
PythonでDB選択
↓
必要な最大2DBだけNotion取得
↓
AI改善ログから類似例をPythonで検索
↓
Geminiで回答
```

原則:

```text
1 AI質問 = Gemini 1回
```

です。

DBルーターは以下を利用します。

- DB用途
- DBタイトル
- プロパティ名
- プロパティ型
- 質問文
- 日付表現

DBスキーマは約10分キャッシュされます。

---

# 10. AI改善機能の設定

## 10.1 環境変数

Render に:

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

を追加し、先ほど作成した `AI改善ログ` DB の ID を設定します。

## 10.2 動作フロー

まず:

```text
AI 今月の食費について分析して
```

と送ります。

回答が変だった場合:

```text
AI改善
```

または:

```text
AIフィードバック
AI修正
```

と送ります。

Bot が直前の質問と回答を表示し、

```text
本当はどのように答えてほしかったですか？
```

と聞きます。

ユーザーは理想の回答方法を自然文で送ります。

例:

```text
食費の合計だけではなく、予算との差額と、月末まで1日いくら使えるかも出してほしかった。
```

するとAI改善ログDBへ:

```text
質問
AI回答
期待する回答
登録日時
```

が保存されます。

## 10.3 次回以降

次回のAI質問時に `ai_feedback.py` が改善ログを読みます。

処理:

```text
最大100件の改善ログ取得
↓
Pythonで質問類似度を計算
↓
関連度の高い最大3件を選択
↓
Gemini最終プロンプトへ参考例として追加
```

Geminiは改善例の検索には使いません。

そのため、この機能を追加してもGemini APIの呼び出し回数は原則増えません。

---

# 11. AI改善ログを使う際のルール

AI改善ログは「過去の正解データ」ではなく、**ユーザーが期待する回答方法の教師例**です。

Geminiへは次のルールを渡しています。

- 今回取得したNotionデータを事実として優先する
- 過去改善例の数字や事実を今回の質問にそのまま流用しない
- 過去例の回答構成・観点・粒度・判断方法を参考にする

これにより古い家計データなどが誤って新しい質問へ混ざるリスクを抑えています。

---

# 12. AIタイムアウト

`app.py` はAI処理を別スレッドで実行し、最大60秒待ちます。

```text
worker.join(timeout=60)
```

60秒を超えた場合:

```text
AI検索が60秒の制限を超えました。もう一度試してください。
```

と返します。

現在は60秒を維持してください。

Notion DBルーティングやGemini回数を最適化したため以前より高速化が期待できますが、Gemini・Notionの一時的な遅延やAPIリトライに備えて余裕を残しています。

---

# 13. AI改善の一時状態について

直前のAI質問とAI回答は Render のメモリに短期保持します。

つまり:

```text
AI質問
↓
AI回答
↓
AI改善
```

の間に Render が再起動しなければ、その回答を改善対象として利用できます。

`AI改善` の入力完了後はNotionへ永続化されます。

現在の制限:

Renderが回答直後に再起動すると、直前AI回答の一時情報が消える可能性があります。

将来的には Redis または一時ログDBへ永続化する方法があります。

---

# 14. Google Apps Script

GitHub の `gas/` フォルダには以下があります。

```text
gas/Code.gs
gas/DailyMemo.gs
gas/FinanceReports.gs
```

## Code.gs

カード利用メールを確認します。

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

Script Properties:

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

Renderデプロイ後、LINEで順番に確認してください。

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

正常なら回答後に:

```text
回答が期待と違う場合は「AI改善」と送ると...
```

という案内が追加で届きます。

続けて:

```text
AI改善
```

と送ります。

理想回答を入力し、Notion `AI改善ログ` DB に1件保存されれば成功です。

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

Render Logs に:

```text
AI改善ログ保存エラー
```

が出ていないか確認してください。

---

# 17. AIが違うDBを読む場合

Render Logs にAI Routerの結果が出ます。

例:

```text
[AI Router] 家計簿 score=18.0 reasons=role:食費,prop:金額
```

質問に対して違うDBを選んでいる場合は `notion_helper.py` のルーティングヒントを改善します。

AI改善ログは「回答の仕方」を学ぶ機能であり、DBルーティング自体の誤りはRenderログから別途調整するのが基本です。

---

# 18. 未登録コマンド

登録されていないコマンドを送信すると、Geminiを呼ばず:

```text
そのコマンドはありません。メニューから機能を選んでください。
```

と返し、メニューを表示します。

これによりGemini API無料枠を無駄に消費しません。

---

# 19. セキュリティ

GitHub に以下を直接書かないでください。

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
