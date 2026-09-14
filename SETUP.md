# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
- `PHASE3_TEST.md`: Phase 3A/3B実機テスト
- `PHASE5_TEST.md`: Phase 4/5実機テスト
- `FLYER_TEST.md`: サミットチラシ・生活カレンダー実機テスト
- `gas/README.md`: GAS詳細

---

# 1. 必要サービス

GitHub / Render / LINE Developers / Notion / Gmail / Google Apps Script / Google AI Studio

Notion IntegrationはBotが使うすべてのDBへ接続し、読み取り・作成・更新を許可します。

---

# 2. Phase 4 / 5で使うNotion DB

## メモDB

```text
Database ID: 3d60efb323d08089b369df4e332d7e36
環境変数: NOTION_MEMO_DATABASE_ID
```

Phase 4で追加済み:

| 名前 | 型 |
|---|---|
| `期限` | Date |
| `分類` | Select (`買い物/やること/予定/アイデア/その他`) |
| `完了` | Checkbox |

## 後で見るURL DB

```text
Database ID: 3d40efb323d0806b927ce286e442add6
環境変数: NOTION_URL_DATABASE_ID
```

Phase 4で追加済み:

| 名前 | 型 |
|---|---|
| `ページタイトル` | Rich text |
| `カテゴリ` | Select (`記事/買い物/動画/SNS/資料/その他`) |
| `ドメイン` | Rich text |
| `保存日時` | Date |

## AI改善ログ DB

```text
Database ID: 3d70efb323d0806faa10ed0ec36351cb
環境変数: NOTION_AI_FEEDBACK_DATABASE_ID
```

既存:

```text
質問 Title
AI回答 Rich text
期待する回答 Rich text
登録日時 Date
```

Phase 5で追加済み:

```text
評価 Select: 👍 / 👎 / 改善
参照DB Rich text
根拠 Rich text
```

## 生活カレンダー

```text
Database ID: 684f959e451047389505a95ed368a7d6
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

旧 `3d90efb323d080b5999bed1820a6665e` は削除済みDBなので使用しません。

---

# 3. Render環境変数

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
NOTION_API_KEY
NOTION_PAGE_URL
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
NOTION_CARD_RULES_DATABASE_ID
NOTION_SAVINGS_GOALS_DATABASE_ID
NOTION_LOAN_DATABASE_ID
NOTION_FEATURE_REQUEST_DATABASE_ID
NOTION_FLYER_DATABASE_ID
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

Phase 4/5で新しい環境変数は増えません。既存のIDを利用します。

GitHub更新後はRenderを最新版へ再デプロイしてください。

---

# 4. Phase 4

実装ファイル:

```text
phase4.py
feature_guide.py
menu.py
```

LINE:

```text
Phase4
メモ 住民票を明日までに提出
メモ一覧
買い物 牛乳
買い物リスト
買った 牛乳
https://example.com/
```

URL取得先がJavaScript必須・ログイン必須・Bot拒否の場合、タイトルを取得できないことがあります。その場合でもURL本体は保存する設計です。

---

# 5. Phase 5

実装ファイル:

```text
phase5.py
ai_engine.py
ai_feedback.py
feature_guide.py
menu.py
```

## AI回答の参照DB・根拠

```text
AI 今月の食費を分析して
```

回答末尾に `【参照DB】` と `【根拠】` が付きます。参照DBは `notion_helper` が実際に選択して文脈化したDB名から生成します。

## AI評価

```text
AI評価 👍
AI評価 👎
```

メインメニューにもMessage actionの評価ボタンがあります。押した瞬間に評価コマンドがトークへ表示されます。

`👎` の後に `AI改善` を使うと、既存の期待回答入力フローを利用できます。

## AI改善 → DBルーター

過去の類似 `👎 / 改善` ログに `参照DB` が保存されている場合、そのDB名を次回のルーティングクエリへ補助情報として加えます。過去ログの回答内容を事実として再利用するものではありません。

## Notion DBヘルスチェック

```text
DBヘルスチェック
Notion DBヘルスチェック
```

確認内容:

```text
・必要な環境変数が設定されているか
・Notion APIからDBを取得できるか
・Phase 4/5などで必要な主要プロパティが存在するか
```

環境変数の値やAPIキーそのものはLINEへ表示しません。

---

# 6. Phase 4 / 5 実機確認

```text
メニュー
Phase4
メモ 住民票を明日までに提出
メモ一覧
買い物 牛乳
買い物リスト
買った 牛乳
https://example.com/
Phase5
DBヘルスチェック
AI 今月の食費を分析して
AI評価 👍
AI評価 👎
```

`PHASE5_TEST.md` に詳細手順を記載します。

---

# 7. 特売

```text
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

```text
特売
特売情報
今日の特売
```

LINEコマンドは実機確認済みです。

---

# 8. GAS Script Properties

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

---

# 9. AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

---

# 10. 現在の開発順

```text
Phase 4 — 主要実装済み・要実機確認
Phase 5 — 主要実装済み・要実機確認
Phase 3C — 次
Phase 6
Phase 7
```

---

# 11. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。

Channel Access Tokenをチャットやコードへ貼り付けた場合は、そのトークンを再発行し、RenderとGAS Script Propertiesの両方を新しい値へ更新してください。
