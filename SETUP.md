# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
- `FLYER_TEST.md`: サミットチラシ自動化テスト
- `gas/README.md`: GAS詳細

---

# 1. 必要サービス

GitHub / Render / LINE Developers / Notion / Gmail / Google Apps Script / Google AI Studio

Notion IntegrationはBotが使うすべてのDBへ接続し、読み取り・作成・更新を許可します。

---

# 2. Notion DB仕様

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

## 固定費DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

環境変数: `NOTION_FIXED_DATABASE_ID`

## カード未処理DB

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

環境変数: `NOTION_CARD_PENDING_DATABASE_ID`

## カード学習ルールDB

| 名前 | 型 |
|---|---|
| `店名キー` | Title |
| `表示名` | Rich text |
| `ジャンル` | Select |
| `学習回数` | Number |
| `一致回数` | Number |
| `自動登録` | Checkbox |
| `最終更新` | Date |

環境変数: `NOTION_CARD_RULES_DATABASE_ID`

## 貯金目標DB（Phase 2C）

| 名前 | 型 | 必須 |
|---|---|---|
| `目標名` | Title | 必須 |
| `目標額` | Number | 必須 |
| `現在額` | Number | 必須 |
| `期限` | Date | 任意 |
| `有効` | Checkbox | 必須 |

環境変数: `NOTION_SAVINGS_GOALS_DATABASE_ID`

## 特売カレンダーDB

サミットのチラシを保存する専用DBです。

| 名前 | 型 | 用途 |
|---|---|---|
| `商品名` | Title | 特売商品名 |
| `特売日` | Date | 単日または開始〜終了 |
| `価格` | Rich text | チラシ価格表記 |
| `容量・単位` | Rich text | 1パック、100gなど |
| `店舗` | Select | サミット ミナノ分倍河原店 |
| `備考` | Rich text | 税込/税抜・条件等 |
| `優先度` | Number | 1〜3 |
| `チラシURL` | URL | 取得元 |
| `チラシ識別` | Rich text | チラシ更新判定用 |
| `識別キー` | Rich text | 重複防止用 |
| `有効` | Checkbox | 現在のチラシで有効か |
| `更新日時` | Date | 最終同期日時 |

`特売日`を使ったカレンダービューを作成してください。おすすめのビュー条件は `有効 = true` です。

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
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

---

# 4. Gemini AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
AI 質問   → 選択中モデルで回答
```

既定はLiteです。

---

# 5. 目的ベースのヘルプ

```text
？
ヘルプ
おすすめ
何したい 節約したい
コマンド
```

この案内機能はGeminiを使いません。

---

# 6. Phase 2

## Phase 2A

```text
今日使える
ペース
異常支出
```

## Phase 2B

```text
予算提案
月締め
月締め YYYY-MM
月締め確定 YYYY-MM
月締め確定強制 YYYY-MM
月次レビュー
月次レビュー YYYY-MM
```

## Phase 2C

```text
年間予測
年間予測 2026
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

---

# 7. サミット特売Notionカレンダー・LINE日次通知

対象:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

Apps Scriptへ入れるファイルは1つです。

```text
gas/FlyerDeals.gs
```

この1ファイルが取得・Gemini画像解析・Notion同期・LINE通知を担当します。

## チラシ用 Script Properties

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

`NOTION_API_KEY`は既存のNotion Integration Tokenと同じものをScript Propertiesへ設定できます。秘密値はチャットへ貼らないでください。

Notion Integrationを特売カレンダーDBへ接続してください。

## Apps Scriptタイムゾーン

```text
(GMT+09:00) Tokyo
```

## 初回テスト

解析だけ:

```text
testSummitFlyerParse
```

Notion同期 + LINE:

```text
testSummitFlyerAutomation
```

Notion登録済みデータからLINEだけ:

```text
testTodaySummitFlyerNotification
```

## 毎日自動実行

一度だけ:

```text
installDailySummitFlyerTrigger
```

以降は毎日6時台に:

```text
最新チラシ確認
↓
新しいチラシだけGemini画像解析
↓
Notionへ同期
↓
Notionから今日分を再取得
↓
LINE通知
```

同じチラシならGemini解析結果を再利用します。

詳細は`FLYER_TEST.md`。

---

# 8. GAS

Apps Scriptへ最新版をコピー:

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
gas/FlyerDeals.gs
```

既存カード/定期通知用:

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
NOTION_FLYER_DATABASE_ID
```

GitHubの`.gs`は通常Apps Scriptへ自動同期されません。

---

# 9. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `runDailySummitFlyerAutomation` | 毎日6時台 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

---

# 10. Phase 1カード自動化

`カードテスト`で本物の未処理がなくてもテスト可能です。

---

# 11. Postback制限

LINE Postback `data`は300文字以内です。

---

# 12. 導入確認

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

チラシ: `FLYER_TEST.md`

---

# 13. トラブル時

チラシ自動化はApps Scriptの実行ログを確認します。

主な確認:
- `NOTION_FLYER_DATABASE_ID`が正しいか
- DBプロパティ名・型が上表と完全一致しているか
- Notion Integrationが特売DBへ接続されているか
- `GEMINI_API_KEY`が設定されているか
- `LINE_USER_ID` / `LINE_CHANNEL_ACCESS_TOKEN`が正しいか

---

# 14. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。
