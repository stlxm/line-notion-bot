# LINE Notion Bot セットアップガイド

このドキュメントは、LINE・Notion・Gemini・Gmail・Google Apps Script・Render を連携して、このBotを構築・更新するための手順書です。

現在の構成には、家計簿・予算・固定費・メモ・カード即時通知・カード未処理キュー・日次/週次通知・Notion検索・Gemini AI検索・AI回答改善が含まれます。

---

# 1. 全体構成

```text
カード会社メール
  ↓
Gmail
  ↓
GAS
  ↓
Render /api/card-pending
  ↓
カード未処理DBへ一時保存
  ↓
LINEへ即時通知
  ↓
ジャンル保存 / 登録しない
  ↓
未処理ページをアーカイブ
  ↓
次の未処理カードを自動表示

LINE AI質問
  ↓
Python DB Router
  ↓
必要な最大2DB
  ↓
関連するAI改善例
  ↓
Gemini 1回
  ↓
LINE向けプレーンテキスト
```

---

# 2. Notion DB

## 家計簿 DB

| 名前 | 型 |
|---|---|
| 内容・店名 | Title |
| 金額 | Number |
| 日付 | Date |
| ジャンル | Select |
| カード・支払方法 | Select |
| 月別管理 | Relation |

## 月別管理 DB

| 名前 | 型 |
|---|---|
| 年月 | Title |
| 全体予算 | Number |
| 食費予算など | Number |

ジャンル別予算は `ジャンル名 + 予算` の形式にします。

## 固定費マスタ DB

| 名前 | 型 |
|---|---|
| 内容・店名 | Title |
| 金額 | Number |
| ジャンル | Select |
| カード・支払方法 | Select |
| 有効 | Checkbox |

## メモ DB

| 名前 | 型 |
|---|---|
| メモ | Title |
| 日付 | Date |

## URL保存 DB

| 名前 | 型 |
|---|---|
| URL | Title |

## AI改善ログ DB

| 名前 | 型 |
|---|---|
| 質問 | Title |
| AI回答 | Rich text |
| 期待する回答 | Rich text |
| 登録日時 | Date |

環境変数:

```text
NOTION_AI_FEEDBACK_DATABASE_ID
```

## カード未処理 DB

新しく作成する一時キューです。名前は `カード未処理` などで構いません。

プロパティ名と型を次に合わせてください。

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

環境変数:

```text
NOTION_CARD_PENDING_DATABASE_ID
```

このDBは履歴保存用ではありません。未処理のカード利用だけを保持し、家計簿への保存成功または `登録しない` の選択後は、Notion APIでページを `archived=true` にして通常の一覧・検索から消します。

Notion Integration をこのDBにも接続し、ページ作成・更新・アーカイブができる権限を与えてください。

---

# 3. Render 環境変数

LINE:

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

Notion:

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

Gemini:

```text
GEMINI_API_KEY
GEMINI_MODEL
```

定期API:

```text
SCHEDULER_SECRET
```

`SCHEDULER_SECRET` は長いランダム値にし、GAS側にも同じ値を設定します。チャットやGitHubに貼らないでください。

`NOTION_DATABASE_IDS` には、専用環境変数で指定していない追加のAI検索/汎用登録対象DBだけをカンマ区切りで入れる運用を推奨します。`AI改善ログ` と `カード未処理` は特殊用途なので重複登録不要です。

---

# 4. LINE Developers

Messaging API チャネルを作成し、次をRenderへ設定します。

```text
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
```

Webhook URL:

```text
https://YOUR-RENDER-DOMAIN.onrender.com/callback
```

Webhook利用をONにしてください。

過去にChannel Access Tokenをチャットや公開コードへ貼った場合は再発行し、RenderとGASの両方を更新してください。

---

# 5. Render Web Service

推奨設定:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

GitHub `main` への更新で自動デプロイする設定が便利です。

---

# 6. Google Apps Script

GitHub側の最新コードをApps Scriptへ手動コピーします。

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
```

GitHub更新は通常のスタンドアロンApps Scriptへ自動同期されません。`clasp` 等を使っていない場合は、変更後にコピーしてください。

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

`RENDER_BASE_URL` 例:

```text
https://line-notion-bot.onrender.com
```

---

# 7. カード通常監視

GAS関数:

```text
checkCardEmails
```

推奨トリガー:

```text
1時間ごと
```

実処理対象は直近2時間です。1時間ごとに2時間を見ることで、Apps Scriptの実行時刻が多少ずれても取りこぼしにくくしています。

新しいカード利用を検知すると、まず未処理DBへ保存し、その後LINEへ即時Flex通知します。

通知ボタン:

```text
ジャンルを選ぶ    → 緑
店名を変更する    → 緑
登録しない        → 色なし
```

ジャンル選択肢も通常操作なので緑です。

---

# 8. カード未処理を連続処理

LINEで:

```text
カード未処理
```

と送るか、メニューの `カード未処理を確認` を押します。

未処理件数と最も古い1件を表示します。

ジャンルを保存すると:

```text
家計簿DBへ保存
↓
保存成功を確認
↓
その未処理ページをアーカイブ
↓
次の未処理カードを自動表示
```

となります。

`登録しない` の場合は家計簿へ保存せず、その未処理ページをアーカイブして次へ進みます。

---

# 9. 古いLINE通知からの二重登録防止

新キュー方式のカード通知には `pending_id` が埋め込まれています。

一度ジャンル保存またはスキップして未処理ページがアーカイブされた後、LINEの古いカード通知をもう一度押しても、`app.py` が pending_id の有効性を確認します。

処理済みなら家計簿保存を実行せず、次のように案内します。

```text
このカード利用はすでに処理済みです。
古い通知からの二重登録は行いませんでした。
```

未処理が残っていれば次のカードを表示します。

注意: この保護は `pending_id` を持つ新方式の通知が対象です。キュー導入前の古い通知や、別経路で手動登録済みの過去支出との完全照合は別機能です。

---

# 10. 未処理件数の日次通知

`gas/FinanceReports.gs` の:

```text
sendDailyCardPendingReminder
```

に1日1回の時間主導トリガーを設定します。

例:

```text
毎日 20時〜21時ごろ
```

Render API:

```text
POST /api/card-pending-reminder
```

未処理が0件なら通知しません。1件以上なら件数だけLINEへ通知します。

---

# 11. 2026年9月のカード履歴をまとめて取り込む

最新 `gas/Code.gs` をApps Scriptへコピー後、GASエディタで次を手動実行します。

```text
backfillSeptember2026
```

内部では:

```text
backfillCardEmailsForMonth(2026, 9)
```

を実行します。

処理内容:

```text
9月前後のカードメールを広めに検索
↓
本文から実利用日を解析
↓
利用日が2026-09のものだけ採用
↓
カード未処理DBへ一括追加
↓
個別のLINE通知は送らない
↓
最後に新規追加件数だけ通知
```

その後 `カード未処理` から古い順にジャンルを付けてください。

### 2026年9月10日時点で実行する場合

9月11日〜30日の利用メールはまだ存在しないため、今日実行しても9月全体は完成しません。現時点で取得できる9月分を先に取り込み、9月30日以降に再実行してください。

楽天カードなど利用から通知まで遅れるケースもあるため、10月上旬にも再実行すると安全です。

バックフィル済みGmail Message IDを別のScript Propertyに保持するため、同じメールの再バックフィルを抑止します。

### 既に手動登録済みの支出

現在のバックフィルはGmail Message ID単位の重複を抑止しますが、家計簿DBに別経路で既に登録済みの支出との完全照合はまだ行いません。

同じ支出が未処理に出てきた場合は `登録しない` を選んでください。今後、自動照合を追加できます。

---

# 12. AI検索

AIは次の形式だけ起動します。

```text
AI 質問内容
```

処理:

```text
PythonでDB選択
↓
最大2DBだけNotion取得
↓
AI改善ログから類似例をPythonで検索
↓
Gemini最終回答 1回
↓
LINE向けプレーンテキスト整形
```

原則 `1 AI質問 = Gemini 1回` です。

60秒タイムアウトは維持します。

```text
worker.join(timeout=60)
```

GeminiにはMarkdown禁止を指示し、返答後も `sanitize_for_line()` で `**`、`##`、コードフェンスなどを除去します。

---

# 13. AI改善

AI回答後に:

```text
AI改善
```

と送ると、本当はどう答えてほしかったかを尋ねます。

回答はAI改善ログDBへ次の4項目で保存します。

```text
質問
AI回答
期待する回答
登録日時
```

今後の似た質問ではPythonで関連例を最大3件選び、Geminiへ参考情報として渡します。改善例検索自体にはGeminiを使いません。

---

# 14. UIの色ルール

順番ではなく操作の意味で決めます。

```text
通常の操作・選択・次へ → primary / 緑
キャンセル               → secondary / 色なし
登録しない               → secondary / 色なし
削除                     → secondary / 控えめ
```

メインメニューの通常機能、ジャンル選択、支払方法選択、店名変更などは緑です。

「先頭1個だけ」「最初の2個だけ」緑というルールはありません。

---

# 15. 推奨トリガー

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

# 16. 動作確認

Render再デプロイとGAS更新後、次を確認します。

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

カードキューのテストでは、新しいカード通知について以下を確認します。

```text
LINEへ即時通知
↓
カード未処理DBに存在
↓
ジャンル保存
↓
家計簿DBに追加
↓
カード未処理DBから消える
↓
次の未処理があれば自動表示
```

さらに処理済みの古いLINE通知をもう一度押し、家計簿へ重複登録されないことも確認してください。

---

# 17. トラブルシューティング

カード未処理DBへ保存できない場合:

```text
NOTION_CARD_PENDING_DATABASE_ID がRenderにあるか
Notion IntegrationがDBに接続されているか
プロパティ名・型が完全一致しているか
SCHEDULER_SECRETがGASとRenderで一致しているか
RENDER_BASE_URLが正しいか
```

必要な未処理DBプロパティ:

```text
GmailMessageID  Title
カード           Rich text
利用先           Rich text
金額             Number
利用日           Date
通知済み         Checkbox
登録日時         Date
```

Renderが401を返す場合は `SCHEDULER_SECRET` の不一致を確認してください。

---

# 18. セキュリティ

GitHubへ次を直接書かないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GEMINI_API_KEY
NOTION_API_KEY
SCHEDULER_SECRET
```

Render Environment または GAS Script Properties で管理します。

---

# 19. 今後の改善候補

- バックフィル時に家計簿DBまで照合する完全な重複防止
- 固定費二重登録防止
- 予算アラートの段階別一度だけ通知
- `/api/register-fixed` / `/api/monthly-notice` の認証統一
- AI直前回答と `user_states` の永続化
- AI改善ログが大量になった場合のベクトル検索

README.md と SETUP.md は機能変更と同時に更新する方針です。
