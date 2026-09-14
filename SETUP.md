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

実運用中の `生活カレンダー` DB:

```text
Database ID: 684f959e451047389505a95ed368a7d6
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

`3d90efb323d080b5999bed1820a6665e` は削除済みの旧 `特売カレンダー` です。Render/GASともこの旧IDを使わないでください。

主項目:

```text
予定名 / 日付 / 種類 / 金額 / 内容 / 価格 / 容量・単位 / 店舗 / 備考
優先度 / チラシURL / チラシ識別 / 識別キー / 元チラシID / 元チラシ名
元画像URL / 確認状態 / 有効 / 更新日時
```

LINEの `特売情報` コマンドはこのDBを読みます。

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

特売コマンド用:

```text
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

`flyer_command.py` は旧削除DB `3d90ef...` が環境変数に残っている場合でも、現在の生活カレンダーへ退避します。ただしRenderの環境変数自体も正しいIDへ直してください。

GitHub更新後はRenderを最新版へ再デプロイしてください。

---

# 4. GAS Script Properties

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

秘密値は `.gs` ファイルへ直書きせずScript Propertiesへ保存します。

---

# 5. 今日の特売コマンド

実装ファイル:

```text
flyer_command.py
phase2_commands.py
menu.py
feature_guide.py
```

LINE:

```text
特売
特売情報
今日の特売
本日の特売
サミット特売
```

取得条件:

```text
店舗 = サミット ミナノ分倍河原店
種類 = 特売
確認状態 = 確認済み
有効 = true
日付が今日を含む
```

短期特売を先に表示し、月間・長期特売を後に表示します。最大20件です。

実機確認:

```text
1. Renderの NOTION_FLYER_DATABASE_ID を 684f959e451047389505a95ed368a7d6 に修正
2. GitHub最新版をRenderへ再デプロイ
3. LINEで「特売情報」
4. メニュー → 🛒 特売・買い物 → 今日の特売を見る
5. 「機能確認 特売情報」
```

404 `object_not_found` が出る場合は、対象DBが `LINE bot Access` Integrationへ共有されているかも確認します。

---

# 6. Phase 3A — 自然文家計簿入力

```text
自然文入力
今日サミットで2380円使った
昨日コンビニで540円買った
```

追加DBは不要です。既存の家計簿DBのSelect候補を使います。最終確認前には保存しません。

---

# 7. よく使う支出テンプレート

```text
支出テンプレート
```

直近90日の家計簿から `店名 + ジャンル + 支払方法` を集計し、頻度順に候補を表示します。

---

# 8. 本日のレポート

```text
本日のレポート
今日のレポート
日次レポート
```

今日の支出、ジャンル内訳、最大支出、今月累計、残り予算、1日目安、カード未処理件数を表示します。

---

# 9. Phase 3B — 直前登録の修正・取り消し

```text
直前登録
直前修正
直前取り消し
```

取り消しは `archived=true` を使い、物理削除しません。

---

# 10. 毎月1日の予算設定案内

GAS:

```text
sendMonthlyBudgetNotice
testMonthlyBudgetNotice
installMonthlyBudgetNoticeTrigger
```

---

# 11. 貸し借り管理

```text
貸した 田中 3000 ランチ代
借りた 田中 2000
貸し借り一覧
精算 田中 3000
```

---

# 12. 機能確認

```text
機能確認 特売情報
機能確認 貸し借り
機能確認 自然文家計簿
```

登録済み機能で見つからない場合だけGeminiを使います。

---

# 13. AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

---

# 14. GASトリガー

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

# 15. 開発ロードマップ

```text
Phase 3A: #34 / #36 実装済み・要実機確認
Phase 3B: #37 / #38 実装済み・要実機確認
Phase 3C: #39 / #40 / #45 / #46 未着手
```

特売コマンドはPhase 2.7の操作性向上として追加しています。

---

# 16. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。

Channel Access Tokenをチャットやコードへ貼り付けた場合は、そのトークンを再発行し、RenderとGAS Script Propertiesの両方を新しい値へ更新してください。
