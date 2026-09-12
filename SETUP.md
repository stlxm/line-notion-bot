# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
- `PHASE3_TEST.md`: Phase 3B修正・取り消しテスト
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

環境変数:

```text
NOTION_KAKEIBO_DATABASE_ID
```

Phase 3BはこのDBの最新作成1件を対象にします。新しいプロパティは不要です。

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

## チラシ一覧

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

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

貸し借り・要望DB:

```text
NOTION_LOAN_DATABASE_ID=f9b2c4eb59ea4c13b968f8d9b48663bc
NOTION_FEATURE_REQUEST_DATABASE_ID=76e4fe5d248e4fd1a48f45e9bdd59e8c
```

GitHub更新後はRenderを最新版へ再デプロイしてください。

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

秘密値は `.gs` ファイルへ直書きせずScript Propertiesへ保存します。

---

# 6. 毎月1日の予算設定案内

実装ファイル:

```text
gas/FinanceReports.gs
```

手動テスト:

```text
testMonthlyBudgetNotice
```

トリガー作成:

```text
installMonthlyBudgetNoticeTrigger
```

`設定する` / `後でする` のPostbackには `displayText` があり、タップ直後にトークへ選択内容が表示されます。

---

# 7. 貸し借り管理

```text
貸した 田中 3000 ランチ代
借りた 田中 2000
貸し借り一覧
精算 田中 3000
```

`精算 相手 金額` は未精算レコードが1件だけ一致した場合のみ更新します。

---

# 8. 機能確認・Gemini補助判定・機能追加要望

```text
機能確認 貸し借り
機能確認 旅行のためにお金を貯める
貸し借りの記録ってできる？
```

登録済み機能で見つからない場合だけGeminiを使います。Geminiも未対応と判断した場合に限り、入力した機能名をそのまま要望DBへ登録します。

---

# 9. Phase 3B — 直前登録の修正・取り消し

追加設定・追加DBは不要です。既存の家計簿DBと `NOTION_KAKEIBO_DATABASE_ID` を使います。

実装ファイル:

```text
phase3b.py
phase2_commands.py
menu.py
```

LINE:

```text
直前登録
直前修正
直前取り消し
```

修正例:

```text
直前修正 金額 1500
直前修正 店名 サミット
直前修正 日付 2026-09-12
直前修正 ジャンル 食費
直前修正 支払方法 JCB
```

取り消しは `archived=true` を使い、物理削除しません。`直前取り消し` を送った時点ではまだ変更されず、確認画面の「取り消す」を押した後だけアーカイブします。

---

# 10. ボタンの即時タップ表示

LINE Postbackは、そのままだとRenderの応答が返るまで押したか分かりづらいため、`displayText` を追加しています。

対象:

```text
menu.py のPostback
ui.py のジャンル・支払方法・カード分類系Postback
gas/FinanceReports.gs の予算設定Postback
```

期待動作:

```text
ボタンを押す
→ トーク画面に「▶ 食費」などが即時表示
→ 数秒後にBotの処理結果が返る
```

LINEの message action ボタンは元から押した内容がトークに表示されるため、そのまま使います。

---

# 11. Gemini AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

---

# 12. サミットチラシ

状態: **実装完了・実機確認済み・日次運用中**

```text
detected=5
analyzed=5
missing=[]
flyers=5
deals=57
```

GAS:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

---

# 13. GASトリガー

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

# 14. 開発ロードマップ

レシート系はユーザー判断で正式対象から削除済みです。

```text
削除: #32 レシート入力
削除: #33 複数品目レシート分類

Phase 3A: #34 自然文家計簿入力 / #36 よく使う支出テンプレート
Phase 3B: #37 直前登録取り消し / #38 直前登録修正（実装済み・要実機確認）
Phase 3C: #39 / #40 / #45 / #46
```

詳細は `DEVELOPMENT.md` を正本とします。

---

# 15. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。

Channel Access Tokenをチャットやコードへ貼り付けた場合は、そのトークンを再発行し、RenderとGAS Script Propertiesの両方を新しい値へ更新してください。
