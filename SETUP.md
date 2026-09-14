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
- `FLYER_TEST.md`: サミットチラシ・生活カレンダー実機テスト
- `gas/README.md`: GAS詳細

---

# 1. 必要サービス

GitHub / Render / LINE Developers / Notion / Gmail / Google Apps Script / Google AI Studio

Notion IntegrationはBotが使うすべてのDBへ接続し、読み取り・作成・更新を許可します。

---

# 2. 主要Notion DB

## 家計簿DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `日付` | Date |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `月別管理` | Relation |

環境変数: `NOTION_KAKEIBO_DATABASE_ID`

## 月別管理DB

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算`など | Number |
| `締め済み` | Checkbox |
| `締め日時` | Date |
| `確定支出` | Number |

環境変数: `NOTION_MONTHLY_DATABASE_ID`

`予算 お菓子 3000` のように未作成ジャンルを設定した場合、Botが `お菓子予算` Number列を自動追加してから保存します。

## メモDB — Phase 4

Database ID:

```text
3d60efb323d08089b369df4e332d7e36
```

環境変数:

```text
NOTION_MEMO_DATABASE_ID
```

Phase 4実装に合わせ、既存DBへ次を追加済みです。

| 名前 | 型 | 用途 |
|---|---|---|
| `メモ` | Title | 内容 |
| `日付` | Date | 登録日時 |
| `期限` | Date | #50 メモ期限 |
| `分類` | Select | 買い物 / やること / 予定 / アイデア / その他 |
| `完了` | Checkbox | 買い物リスト等の完了状態 |

## 後で見るURL DB — Phase 4

Database ID:

```text
3d40efb323d0806b927ce286e442add6
```

環境変数:

```text
NOTION_URL_DATABASE_ID
```

既存の `URL` / `時間` に加えて次を追加済みです。

| 名前 | 型 | 用途 |
|---|---|---|
| `ページタイトル` | Rich text | #56 Webタイトル |
| `カテゴリ` | Select | 記事 / 買い物 / 動画 / SNS / 資料 / その他 |
| `ドメイン` | Rich text | URLのホスト名 |
| `保存日時` | Date | 保存時刻 |

URLのタイトル取得・カテゴリ分類は `phase4.py` がルールベースで行い、Geminiは使いません。

## 固定費DB

環境変数: `NOTION_FIXED_DATABASE_ID`

## カード未処理DB

環境変数: `NOTION_CARD_PENDING_DATABASE_ID`

## カード学習ルールDB

環境変数: `NOTION_CARD_RULES_DATABASE_ID`

## 貯金目標DB

環境変数: `NOTION_SAVINGS_GOALS_DATABASE_ID`

## 貸し借り管理DB

```text
Database ID: f9b2c4eb59ea4c13b968f8d9b48663bc
NOTION_LOAN_DATABASE_ID=f9b2c4eb59ea4c13b968f8d9b48663bc
```

## 機能追加要望DB

```text
Database ID: 76e4fe5d248e4fd1a48f45e9bdd59e8c
NOTION_FEATURE_REQUEST_DATABASE_ID=76e4fe5d248e4fd1a48f45e9bdd59e8c
```

## 特売・生活カレンダーDB

```text
Database ID: 684f959e451047389505a95ed368a7d6
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

`3d90efb323d080b5999bed1820a6665e` は削除済みの旧 `特売カレンダー` です。

## チラシ一覧

```text
Database ID: fdd0c0ce50974273b9b88f5272858e90
```

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

Phase 4で新しい環境変数は増えません。既存の `NOTION_MEMO_DATABASE_ID` と `NOTION_URL_DATABASE_ID` を使います。

GitHub更新後はRenderを最新版へ再デプロイしてください。

---

# 4. Phase 4 実機確認

```text
メモ 住民票を明日までに提出
メモ一覧
買い物 牛乳
買い物 洗濯ネット
買い物リスト
買った 牛乳
https://example.com/
機能確認 買い物リスト
機能確認 URL分類
```

確認ポイント:

```text
・メモDBに期限 / 分類 / 完了が保存される
・買い物リストは未完了の買い物だけ表示される
・買った 商品名 で1件だけ一致した項目を完了にする
・URL DBにページタイトル / カテゴリ / ドメイン / 保存日時が入る
・URLタイトル取得失敗でもURL自体は保存できる
```

---

# 5. GAS Script Properties

共通:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

チラシ用:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

Apps Scriptタイムゾーン: `(GMT+09:00) Tokyo`

---

# 6. 今日の特売コマンド

```text
特売
特売情報
今日の特売
本日の特売
サミット特売
```

取得元は実運用中の `生活カレンダー` DBです。404 `object_not_found` が出る場合は、DB IDと `LINE bot Access` Integration共有を確認します。

---

# 7. Phase 3A / 3B

```text
自然文入力
今日サミットで2380円使った
支出テンプレート
本日のレポート
直前登録
直前修正
直前取り消し
```

---

# 8. 毎月1日の予算設定案内

GAS:

```text
sendMonthlyBudgetNotice
testMonthlyBudgetNotice
installMonthlyBudgetNoticeTrigger
```

---

# 9. 貸し借り管理

```text
貸した 田中 3000 ランチ代
借りた 田中 2000
貸し借り一覧
精算 田中 3000
```

---

# 10. AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

---

# 11. GASトリガー

```text
checkCardEmails                         1時間ごと
sendMonthlyBudgetNotice                 毎月1日6時台
runDailySummitLifeCalendarAutomation    毎日6時台
sendDailyMemoReminder                   毎日8時ごろ
sendDailyBudgetAlert                    毎日20時ごろ
sendDailyCardPendingReminder            毎日20〜21時ごろ
sendMonthEndCardCheck                   毎日21時ごろ
sendWeeklyFinanceReport                 毎週日曜20時ごろ
```

---

# 12. 開発順

```text
Phase 4 — 実装済み・要実機確認
Phase 5 — 次に実装
Phase 3C — Phase 5の後
Phase 6
Phase 7
```

---

# 13. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。

Channel Access Tokenをチャットやコードへ貼り付けた場合は、そのトークンを再発行し、RenderとGAS Script Propertiesの両方を新しい値へ更新してください。
