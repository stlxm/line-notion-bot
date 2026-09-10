# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Google Apps Script・Gmail・Render を連携し、この Bot をゼロから構築・更新するための手順書です。

現在の構成には、家計簿・予算・固定費・メモ・カード通知・カード未処理キュー・週次レポート・日次通知・Notion検索・Gemini AI検索・AI回答改善が含まれます。

---

# 1. 全体構成

```text
LINE
  ├─ 通常コマンド
  │     ↓
  │   Render / Flask
  │     ├─ 家計簿 / 予算 / メモ
  │     ├─ カード未処理キュー
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

カード利用メール
  ↓
Gmail
  ↓
Google Apps Script
  ↓
Render /api/card-pending
  ↓
Notion カード未処理DB
  ↓
LINEへ即時利用通知
  ↓
ジャンル保存 / 登録しない
  ↓
未処理DBからアーカイブ
  ↓
次の未処理カードを表示
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

プロパティ:

| 名前 | 型 | 用途 |
|---|---|---|
| `質問` | Title | 元のAI質問 |
| `AI回答` | Rich text | 実際に返した回答 |
| `期待する回答` | Rich text | 本当はどう答えてほしかったか |
| `登録日時` | Date | 改善ログ保存日時 |

このDBは通常検索用ではなく、似た質問の改善例だけを取り出す専用DBです。

## 3.7 カード未処理 DB

今回追加するキュー専用DBです。

DB名の例:

```text
カード未処理
```

次のプロパティを**名前と型を合わせて**作成してください。

| 名前 | 型 | 用途 |
|---|---|---|
| `GmailMessageID` | Title | Gmailメッセージの重複識別 |
| `カード` | Rich text | JCB / 三井住友カード / 楽天カード / PayPay など |
| `利用先` | Rich text | 店名・利用先 |
| `金額` | Number | 利用金額 |
| `利用日` | Date | 実際の利用日 |
| `通知済み` | Checkbox | 即時LINE通知済みか |
| `登録日時` | Date | キューへ入れた日時 |

`状態` や `完了日時` は現在の実装では不要です。

このDBは履歴DBではありません。

```text
未処理の間だけ存在
↓
家計簿へ保存成功
または
登録しない
↓
該当ページを archived=true にして通常表示から消す
```

Notion API には一般的な完全削除APIがないため、コード上の「削除」はアーカイブを意味します。通常のDBビュー・クエリからは消えます。

---

# 4. Notion Integration

1. Notion で Integration を作成します。
2. API Secret を取得します。
3. 家計簿・月別管理・固定費・メモ・URL保存・AI改善ログ・カード未処理・その他AI検索対象DBすべてに Integration を接続します。
4. 各DBの Database ID を控えます。

書き込み権限が必要なDB:

- 家計簿
- 月別管理
- 固定費
- メモ
- URL保存
- AI改善ログ
- カード未処理

カード未処理DBではページ作成・プロパティ更新・アーカイブを行います。

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

アクセストークンを過去に公開したことがある場合は再発行し、Render と GAS の両方を更新してください。

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

未登録の通常文章は Gemini に送りません。

---

# 7. Render Web Service

推奨設定:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

GitHub `main` へのPushで自動デプロイする設定にしておくと更新が楽です。

---

# 8. Render 環境変数

## LINE

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

`ADMIN_USER_ID` は日次通知、週次レポート、カード未処理件数通知などの送信先です。

## Notion

```text
NOTION_API_KEY
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
NOTION_DATABASE_IDS
NOTION_PAGE_URL
```

### NOTION_CARD_PENDING_DATABASE_ID

新しく作成した `カード未処理` DB の Database ID を設定します。

```text
NOTION_CARD_PENDING_DATABASE_ID=カード未処理DBのID
```

### NOTION_DATABASE_IDS の考え方

専用DBは個別の環境変数へ入れます。

```text
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
```

それ以外のAI検索・汎用データ追加対象DBだけを `NOTION_DATABASE_IDS` にカンマ区切りで入れてください。

`AI改善ログ` と `カード未処理` は特殊用途なので `NOTION_DATABASE_IDS` へ重複登録する必要はありません。

## Gemini

```text
GEMINI_API_KEY
GEMINI_MODEL
```

## Scheduler / GAS認証

```text
SCHEDULER_SECRET
```

十分長いランダム文字列を設定してください。値をチャットやGitHubへ貼らないでください。

---

# 9. Google Apps Script の Script Properties

GAS の「プロジェクトの設定」→「スクリプト プロパティ」に設定します。

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

`RENDER_BASE_URL` の例:

```text
https://line-notion-bot.onrender.com
```

末尾 `/` はあってもコード側で除去します。

`SCHEDULER_SECRET` は Render と同じ値にします。

---

# 10. カード通知・未処理キューの仕組み

通常監視:

```text
checkCardEmails
```

推奨トリガー:

```text
1時間ごと
```

実処理対象:

```text
直近2時間
```

フロー:

```text
Gmailで新しいカードメール
↓
GASが本文からカード・利用先・金額・利用日を解析
↓
POST /api/card-pending
↓
カード未処理DBへ保存
↓
LINEへ即時Flex通知
```

LINE通知では:

- `ジャンルを選ぶ` → 緑
- `店名を変更する` → 緑
- `登録しない` → 色なし

ジャンル選択肢はすべて緑です。

### 1件保存した後

家計簿への保存が成功した場合のみ、カード未処理DBの該当ページをアーカイブします。

その後、未処理が残っていれば次のカードを自動表示します。

```text
1件目 保存
↓
1件目を未処理DBからアーカイブ
↓
2件目を自動表示
↓
2件目 保存
↓
...
```

### 登録しない場合

`登録しない` を押すと家計簿へは保存せず、カード未処理DBの該当ページだけをアーカイブして次へ進みます。

### 後からまとめて処理する

LINEで:

```text
カード未処理
```

と送るか、メニューの「カード未処理を確認」を押してください。

現在の件数と最も古い未処理カードを表示します。

---

# 11. カード未処理の日次リマインダー

`gas/FinanceReports.gs` の:

```text
sendDailyCardPendingReminder
```

に1日1回の時間主導トリガーを設定します。

おすすめ:

```text
毎日 20時〜21時ごろ
```

Render API:

```text
POST /api/card-pending-reminder
```

未処理0件なら通知なし。

未処理があるときだけ:

```text
ジャンル未選択のカード利用が 5 件あります
```

のように通知します。

---

# 12. 2026年9月をまとめて取り込む

GitHubの最新 `gas/Code.gs` をApps Scriptへコピーした後、GASエディタで次の関数を手動実行します。

```text
backfillSeptember2026
```

この関数は:

1. 2026年9月前後のカードメールを広めに検索
2. 本文から実利用日を抽出
3. 実利用日が `2026-09` のものだけ採用
4. カード未処理DBへ追加
5. 過去分1件ごとのLINE通知は送らない
6. 最後に新規追加件数だけLINE通知

という処理を行います。

その後:

```text
カード未処理
```

と送れば古い利用から順番にジャンルを付けられます。

## 2026年9月10日時点で実行する場合

今日は 2026年9月10日なので、9月11日〜30日のメールはまだ存在しません。

したがって今実行すると、主に:

```text
2026-09-01 〜 2026-09-10
```

までに利用・受信できているものが取り込まれます。

9月を丸ごと完成させるには、9月30日以降にも再実行してください。

楽天カードなど利用からメール到着まで遅延するケースを考えると、10月上旬にもう一度実行するのが安全です。

バックフィル済み Gmail Message ID は別の Script Property に保持するため、同じバックフィル関数を再実行したときの重複を抑えます。

## 既に家計簿へ登録済みの9月支出がある場合

現時点のバックフィルは Gmail Message ID 単位の再取り込み重複は抑えますが、**過去に別経路で既に家計簿へ登録済みの支出との完全照合までは行いません**。

すでに手動保存済みのカード支出が未処理へ出てきた場合は、もう一度保存せず `登録しない` でキューから外してください。

---

# 13. 任意の月をバックフィルする

汎用関数:

```javascript
backfillCardEmailsForMonth(year, month)
```

があります。

2026年8月なら、Apps Script に一時的に:

```javascript
function backfillAugust2026() {
  return backfillCardEmailsForMonth(2026, 8);
}
```

のようなラッパーを作って実行できます。

2026年9月は既に `backfillSeptember2026()` が用意されています。

---

# 14. AI検索の仕組み

現在は:

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

# 15. LINE向けAI回答の整形

Geminiが Markdown を返してもLINEで `**` や `##` が残らないよう二重対策しています。

1. GeminiへのプロンプトでMarkdown禁止
2. `sanitize_for_line()` で送信前にMarkdown記号を除去

見出しは `【見出し】`、箇条書きは `・` を使う方針です。

---

# 16. AI改善機能

```text
AI 今月の食費について分析して
```

回答が期待と違った場合:

```text
AI改善
```

Bot が「本当はどのように答えてほしかったですか？」と聞くので、期待内容を自然文で送ります。

AI改善ログDBへ:

```text
質問
AI回答
期待する回答
登録日時
```

を保存します。

次回はPythonで類似する改善例を最大3件選び、Geminiの最終回答へ参考例として追加します。改善ログ検索自体にはGeminiを使いません。

---

# 17. AIタイムアウト

`app.py` はAI処理を別スレッドで実行し、最大60秒待ちます。

```text
worker.join(timeout=60)
```

現在は60秒を維持します。

---

# 18. Flex Message UI の色ルール

現在は「何番目のボタンか」ではなく「操作の意味」で色を決めます。

通常の前向きな操作:

```text
primary = 緑
```

対象例:

- メインメニューの通常機能
- ジャンル選択
- 支払方法選択
- 店名変更
- AI検索の使い方
- Notionを開く

ネガティブ / 低頻度操作:

```text
secondary = 色なし
```

対象例:

- キャンセル
- 登録しない
- 削除する
- メモ削除

「先頭1個だけ」「最初の2個だけ」緑にするロジックは使いません。

---

# 19. その他の定期トリガー

おすすめ例:

```text
checkCardEmails
→ 1時間ごと

sendDailyMemoReminder
→ 毎日 朝8時ごろ

sendDailyBudgetAlert
→ 毎日 20時ごろ

sendDailyCardPendingReminder
→ 毎日 20時〜21時ごろ

sendWeeklyFinanceReport
→ 毎週日曜日 20時ごろ
```

---

# 20. 動作確認

RenderデプロイとGAS更新後、LINEで順番に確認してください。

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

手動支出:

```text
支出 500 コンビニ
```

ジャンル・支払方法が緑、キャンセルだけ色なしならUIは正常です。

カード通知が新しく来た場合は:

1. LINEに即時カード通知が来る
2. `カード未処理` DB に1件存在する
3. ジャンルを保存する
4. 家計簿DBへ支出が追加される
5. カード未処理DBから該当項目が消える
6. 他の未処理があれば次が自動表示される

ことを確認してください。

---

# 21. カード未処理DBへ保存できない場合

確認項目:

1. Render に `NOTION_CARD_PENDING_DATABASE_ID` があるか
2. Database ID が正しいか
3. Notion Integration がカード未処理DBに接続されているか
4. DBプロパティ名が完全一致しているか
5. `SCHEDULER_SECRET` がGASとRenderで一致しているか
6. `RENDER_BASE_URL` が正しいか

必要なプロパティ:

```text
GmailMessageID  Title
カード           Rich text
利用先           Rich text
金額             Number
利用日           Date
通知済み         Checkbox
登録日時         Date
```

---

# 22. セキュリティ

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

# 23. GASコード更新時の注意

GitHub の `gas/*.gs` を更新しても、通常はApps Scriptプロジェクトへ自動同期されません。

今回の変更後は最低でも次をApps Script側へ最新版でコピーしてください。

```text
gas/Code.gs
gas/FinanceReports.gs
```

日次メモも利用する場合:

```text
gas/DailyMemo.gs
```

も保持してください。

---

# 24. 今後の改善候補

- 過去カードバックフィル時の家計簿DB完全重複チェック
- AI直前回答の永続化
- AI改善ログの評価機能
- 改善ログが数千件になった場合のEmbedding / ベクトル検索
- 予算アラートの重複通知防止
- 固定費二重登録防止
- Scheduler API認証統一
- `user_states` の永続化

機能変更時は README.md と SETUP.md も同時に更新する方針です。
