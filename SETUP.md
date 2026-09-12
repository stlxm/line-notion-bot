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

---

# 3. 生活カレンダー・チラシ一覧

## 生活カレンダー

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

特売専用DBではなく、今後の日常予定をまとめる汎用カレンダーです。

| 名前 | 型 | 用途 |
|---|---|---|
| `予定名` | Title | 表示名 |
| `日付` | Date | 単日または期間 |
| `種類` | Select | 特売/家計/引き落とし/給料/メモ/予定/その他 |
| `金額` | Number | 金額を持つ予定用 |
| `内容` | Rich text | 補足説明 |
| `有効` | Checkbox | カレンダー表示対象 |
| `更新日時` | Date | 最終同期 |

チラシ由来の特売では追加で以下を使います。

```text
価格
容量・単位
店舗
備考
優先度
チラシURL
チラシ識別
識別キー
元チラシ名
元画像URL
確認状態
```

カレンダービュー `生活カレンダー` は `日付` を基準にし、`有効=true` を表示するよう作成済みです。

## チラシ一覧

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

| 名前 | 型 |
|---|---|
| `チラシ名` | Title |
| `種別` | Select (`月間/週次/日替わり/その他`) |
| `掲載期間` | Date |
| `元URL` | URL |
| `画像URL` | URL |
| `画像一覧` | Rich text |
| `抽出件数` | Number |
| `抽出サマリー` | Rich text |
| `確認状態` | Select (`確認待ち/確認済み/要修正`) |
| `チラシ識別` | Rich text |
| `取得日時` | Date |

`確認待ち`ビューと`月間チラシ`ビューは作成済みです。

Notion Integrationを **生活カレンダーとチラシ一覧の両方** へ接続してください。

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
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

チラシ連携用DB IDはGAS Script Propertiesへ設定します。

---

# 5. Gemini AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
AI 質問   → 選択中モデルで回答
```

LINE AIの既定はLiteです。チラシ画像解析も既定で `gemini-3.5-flash-lite` を使います。

---

# 6. サミットチラシ → 生活カレンダー

対象:

```text
公式店舗ページ:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufooチラシ一覧:
https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

Apps Scriptへコピーするファイルは2つです。

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

役割:
- `FlyerDeals.gs`: HTML/iframe/画像取得、Notion/LINE共通関数
- `FlyerLifeCalendar.gs`: Shufoo一覧、月間/週次/日替わり判定、確認待ち登録、生活カレンダー同期、確認済み通知

途中版の `FlyerReview.gs` / `FlyerReviewedNotify.gs` は使いません。

## GAS Script Properties

既存:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

チラシで追加:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
```

`NOTION_FLYER_DATABASE_ID` は互換性のため名前を残していますが、指す先は現在の **生活カレンダー** です。

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密値はチャットやGitHubへ貼らず、Apps Scriptの「プロジェクトの設定 → スクリプト プロパティ」へ直接設定してください。

Apps Scriptタイムゾーン:

```text
(GMT+09:00) Tokyo
```

---

# 7. 確認フロー

新しいチラシを読み取ると:

```text
チラシ一覧 → 確認状態 = 確認待ち
生活カレンダー → 種類=特売 / 確認状態=確認待ち / 有効=false
```

Notionの `チラシ一覧 > 確認待ち` で画像・掲載期間・抽出内容を比較します。

正しければ:

```text
確認状態 → 確認済み
```

誤りがあれば:

```text
確認状態 → 要修正
```

手動ですぐ反映する場合:

```text
applyLifeFlyerReviewsNow
```

確認済み由来の特売だけ `有効=true` になります。

---

# 8. 月間チラシ

月初に配信され、約20日以上の掲載期間を持つチラシは `月間` として扱います。

目安:

```text
20日以上 → 月間
4日以上  → 週次
1〜2日   → 日替わり
その他   → その他
```

画像/HTMLから期間が読めない場合は推測で確定しません。

---

# 9. 初回テスト

順番:

```text
1. testSummitLifeFlyerParse
2. testSummitLifeFlyerSync
3. Notion「チラシ一覧 > 確認待ち」で画像と抽出結果を確認
4. 正しいチラシを「確認済み」に変更
5. applyLifeFlyerReviewsNow
6. 生活カレンダーで 種類=特売 / 確認済み / 有効=true を確認
7. testTodayLifeCalendarFlyerNotification
8. installDailySummitLifeCalendarTrigger
```

詳細は `FLYER_TEST.md`。

---

# 10. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `runDailySummitLifeCalendarAutomation` | 毎日6時台 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

一度だけ `installDailySummitLifeCalendarTrigger` を実行すると、旧チラシトリガーを削除して完成版へ切り替えます。

---

# 11. トラブル時

チラシ解析0件:
- `testSummitLifeFlyerParse` の実行ログを見る
- `GEMINI_API_KEY` / `FLYER_GEMINI_MODEL` を確認
- Shufoo/公式サイトの画像配信形式変更を確認

Notion同期失敗:
- `NOTION_API_KEY`
- `NOTION_FLYER_DATABASE_ID`
- `NOTION_FLYER_LIST_DATABASE_ID`
- Integrationが両DBへ接続済みか
- DBプロパティ名/型がこのSETUPと一致するか

通知が0件:
- チラシ一覧が `確認済み` か
- 生活カレンダーで対象行が `種類=特売 / 確認状態=確認済み / 有効=true` か
- 当日が `日付` の範囲内か

---

# 12. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。
