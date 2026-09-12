# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
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

毎月1日の予算設定案内で入力した金額は、このDBの当月 `全体予算` へ保存されます。

## 固定費DB

`内容・店名` Title / `金額` Number / `ジャンル` Select / `カード・支払方法` Select / `有効` Checkbox

環境変数: `NOTION_FIXED_DATABASE_ID`

## カード未処理DB

`GmailMessageID` Title / `カード` Rich text / `利用先` Rich text / `金額` Number / `利用日` Date / `通知済み` Checkbox / `登録日時` Date

環境変数: `NOTION_CARD_PENDING_DATABASE_ID`

## カード学習ルールDB

`店名キー` Title / `表示名` Rich text / `ジャンル` Select / `学習回数` Number / `一致回数` Number / `自動登録` Checkbox / `最終更新` Date

環境変数: `NOTION_CARD_RULES_DATABASE_ID`

## 貯金目標DB

`目標名` Title / `目標額` Number / `現在額` Number / `期限` Date / `有効` Checkbox

環境変数: `NOTION_SAVINGS_GOALS_DATABASE_ID`

## 貸し借り管理DB

Database ID:

```text
f9b2c4eb59ea4c13b968f8d9b48663bc
```

| 名前 | 型 |
|---|---|
| `相手` | Title |
| `種類` | Select (`貸した/借りた`) |
| `金額` | Number |
| `日付` | Date |
| `状態` | Select (`未精算/精算済み`) |
| `精算日` | Date |
| `メモ` | Rich text |

環境変数:

```text
NOTION_LOAN_DATABASE_ID=f9b2c4eb59ea4c13b968f8d9b48663bc
```

このDBは家計簿とは別管理です。貸し借り記録を自動で支出・収入扱いにしません。

## 機能追加要望DB

Database ID:

```text
76e4fe5d248e4fd1a48f45e9bdd59e8c
```

| 名前 | 型 |
|---|---|
| `要望` | Title |
| `問い合わせ文` | Rich text |
| `状態` | Select (`未確認/検討中/採用/見送り`) |
| `登録日` | Date |
| `回数` | Number |
| `備考` | Rich text |

環境変数:

```text
NOTION_FEATURE_REQUEST_DATABASE_ID=76e4fe5d248e4fd1a48f45e9bdd59e8c
```

LINEで未実装の未知機能を聞いたときに自動登録します。同名要望がある場合は新規行を増やさず `回数` を増やします。

---

# 3. 生活カレンダー・チラシ一覧

## 生活カレンダー

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

主項目:

| 名前 | 型 | 用途 |
|---|---|---|
| `予定名` | Title | 表示名 |
| `日付` | Date | 単日または期間 |
| `種類` | Select | 特売/家計/引き落とし/給料/メモ/予定/その他 |
| `金額` | Number | 金額を持つ予定用 |
| `内容` | Rich text | 補足説明 |
| `有効` | Checkbox | カレンダー表示対象 |
| `更新日時` | Date | 最終同期 |

チラシ由来では `価格 / 容量・単位 / 店舗 / 備考 / 優先度 / チラシURL / チラシ識別 / 識別キー / 元チラシID / 元チラシ名 / 元画像URL / 確認状態` も使います。

## チラシ一覧

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

Notion Integrationを生活カレンダーとチラシ一覧の両方へ接続してください。

---

# 4. Render環境変数

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
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

今回追加する値:

```text
NOTION_LOAN_DATABASE_ID=f9b2c4eb59ea4c13b968f8d9b48663bc
NOTION_FEATURE_REQUEST_DATABASE_ID=76e4fe5d248e4fd1a48f45e9bdd59e8c
```

設定後、Renderを再デプロイしてください。

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

Apps Scriptタイムゾーン:

```text
(GMT+09:00) Tokyo
```

**LINEのUser IDやChannel Access Tokenは `.gs` ファイルへ直書きしません。必ずScript Propertiesへ保存します。**

---

# 6. 毎月1日の予算設定案内

実装ファイル:

```text
gas/FinanceReports.gs
```

必要なScript Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

手動テスト:

```text
testMonthlyBudgetNotice
```

正常ならLINEへ「今月の全体予算を設定しますか？」のFlexが届きます。

`設定する` を押すとRender側の既存処理が `WAITING_MONTHLY_BUDGET` 状態へ移り、数字だけを送ると当月の `全体予算` がNotion月別管理DBへ保存されます。

トリガー作成:

```text
installMonthlyBudgetNoticeTrigger
```

これにより `sendMonthlyBudgetNotice` が毎月1日6時台に実行されます。

---

# 7. 貸し借り管理

Render再デプロイ後、LINEで:

```text
貸した 田中 3000 ランチ代
借りた 田中 2000
貸し借り一覧
精算 田中 3000
```

を使えます。

`精算 相手 金額` は、未精算レコードが1件だけ一致したときだけ `状態=精算済み` と `精算日` を更新します。同じ相手・同じ金額が複数ある場合は安全のため自動更新しません。

---

# 8. 機能確認・機能追加要望

Render再デプロイ後、LINEで:

```text
機能確認 レシート入力
レシート入力ってできる？
貸し借りってある？
```

のように質問できます。

- 実装済み: 使い方を返す
- 正式ロードマップ済み・未実装: 予定を返す
- 未知の機能: `機能追加要望` DBへ自動登録

機能一覧は `feature_guide.py` の `FEATURES` を正本にして順次更新します。

---

# 9. Gemini AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
AI 質問   → 選択中モデルで回答
```

LINE AIの既定はLiteです。

---

# 10. サミットチラシ → 生活カレンダー

状態: **実装完了・実機確認済み・日次運用中**

対象:

```text
公式店舗ページ:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
Shufoo店舗ID:
264241
```

Apps Scriptへコピーする完成版ファイル:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

実機成功結果:

```text
detected=5
analyzed=5
missing=[]
flyers=5
deals=57
```

LINE通知:

```text
1〜7日間 → 🔥 今日・短期特売
8日以上  → 📅 月間・長期特売
```

---

# 11. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `sendMonthlyBudgetNotice` | 毎月1日6時台 |
| `runDailySummitLifeCalendarAutomation` | 毎日6時台 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

---

# 12. 開発ロードマップ

Phase 3より先に次を実機確認します。

```text
Phase 2.8 毎月1日の予算設定案内
Phase 2.9 貸し借り管理
Phase 2.10 機能ナビ + 機能追加要望収集
```

確認完了後にPhase 3Aへ進みます。

```text
#32 レシート入力
#33 複数品目レシート分類
#34 自然文家計簿入力
#36 よく使う支出テンプレート
```

---

# 13. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。

Channel Access Tokenをチャットやコードへ貼り付けた場合は、そのトークンを再発行し、RenderとGAS Script Propertiesの両方を新しい値へ更新してください。
