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
```

途中までカード未処理を処理して中断しても問題ありません。保存済み・スキップ済みは未処理DBから消え、未処理だけが残るため、後から `カード未処理` で続きから再開できます。

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

## カード未処理 DB

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

Render環境変数:

```text
NOTION_CARD_PENDING_DATABASE_ID
```

このDBは一時キューです。家計簿への保存成功または `登録しない` の選択後はページをアーカイブし、通常の一覧から消します。

---

# 3. Render 環境変数

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
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
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
```

---

# 4. Google Apps Script

GitHub側の最新コードをApps Scriptへコピーします。

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
```

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

通常カード監視:

```text
checkCardEmails
→ 1時間ごと
```

未処理件数通知:

```text
sendDailyCardPendingReminder
→ 1日1回
```

2026年9月バックフィル:

```text
backfillSeptember2026
→ 必要なときだけ手動実行
```

---

# 5. カード未処理の操作

LINEで:

```text
カード未処理
```

と送ると、最も古い未処理カードを表示します。

カード未処理画面では次の操作ができます。

```text
ジャンル選択
→ 2列表示 / 緑

店名を変更する
→ 緑

登録しない
→ 色なし
```

ジャンル選択肢は短いラベルを前提に2列で表示します。店名変更は、カード会社から届いた加盟店名が分かりにくい場合に修正してからジャンル保存するための機能です。

ジャンル保存成功後:

```text
家計簿DBへ保存
↓
未処理ページをアーカイブ
↓
次の未処理カードを自動表示
```

`登録しない` の場合:

```text
家計簿へ保存しない
↓
未処理ページをアーカイブ
↓
次の未処理カードを自動表示
```

途中でLINEを閉じたり別の操作をしても、未処理項目はNotion DBに残っています。後から再度 `カード未処理` と送れば続きから処理できます。

---

# 6. 古い通知の二重登録防止

新方式の通知には `pending_id` が含まれます。すでに保存・スキップ済みの通知を後から押しても、家計簿へ再登録しないようガードします。

---

# 7. AI検索

```text
AI 質問内容
```

だけでGeminiを呼び出します。DB選択はPython、Gemini最終回答は原則1回、タイムアウトは60秒です。

MarkdownはLINE送信前に除去します。

---

# 8. AI改善

```text
AI改善
```

で直前の質問・AI回答・期待する回答を専用DBへ保存し、似た質問で改善例を参照します。

---

# 9. UIの色ルール

```text
通常操作・ジャンル・店名変更 → primary / 緑
キャンセル・登録しない       → secondary / 色なし
削除                         → 控えめ
```

ボタンの順番ではなく意味で色を決めます。通常画面は1列を基本にし、カードのジャンル選択だけは2列です。

---

# 10. 動作確認

Render再デプロイ後、`カード未処理` を送って以下を確認してください。

```text
・店名を変更するボタンが表示される
・ジャンルが2列で表示される
・ジャンルを選ぶと家計簿へ保存される
・保存後に次の未処理が自動表示される
・登録しないでも次へ進む
・途中でやめても後から続きから再開できる
```

README.md と SETUP.md は機能変更と同時に更新する方針です。
