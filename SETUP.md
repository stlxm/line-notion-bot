# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
- `FLYER_TEST.md`: サミットチラシ・月間チラシ・確認フロー実機テスト
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

# 3. サミット特売用Notion DB

## 特売カレンダー

作成済みDatabase ID:

```text
684f959e451047389505a95ed368a7d6
```

| 名前 | 型 |
|---|---|
| `商品名` | Title |
| `特売日` | Date |
| `価格` | Rich text |
| `容量・単位` | Rich text |
| `店舗` | Select |
| `備考` | Rich text |
| `優先度` | Number |
| `チラシURL` | URL |
| `チラシ識別` | Rich text |
| `識別キー` | Rich text |
| `有効` | Checkbox |
| `更新日時` | Date |
| `元チラシ名` | Rich text |
| `元画像URL` | URL |
| `確認状態` | Select (`確認待ち/確認済み/要修正`) |

`特売日`を使うカレンダービューは作成済みです。`有効=true` の商品だけ表示します。

## チラシ一覧

作成済みDatabase ID:

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

Notion Integrationを **両方のDB** へ接続してください。

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

チラシ機能はGASでNotionへ直接同期するため、`NOTION_FLYER_DATABASE_ID` / `NOTION_FLYER_LIST_DATABASE_ID` はRenderではなくGAS Script Propertiesへ設定します。

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

# 6. サミットチラシ自動化

対象:

```text
公式店舗ページ:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufooチラシ一覧:
https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

Apps Scriptへ次の3ファイルをコピーします。

```text
gas/FlyerDeals.gs
gas/FlyerReview.gs
gas/FlyerReviewedNotify.gs
```

役割:
- `FlyerDeals.gs`: HTML/iframe/画像取得、共通Gemini・Notion・LINE処理
- `FlyerReview.gs`: Shufoo一覧解析、月間/週次/日替わり分類、チラシ一覧DB、確認状態反映
- `FlyerReviewedNotify.gs`: 確認済み商品のみ日次通知

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

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密値 (`GEMINI_API_KEY`, `NOTION_API_KEY`, LINE token等) はチャットやGitHubへ貼らず、Apps Scriptの「プロジェクトの設定 → スクリプト プロパティ」へ直接設定してください。

Apps Scriptタイムゾーン:

```text
(GMT+09:00) Tokyo
```

---

# 7. チラシの確認フロー

新しいチラシを読み取ると:

```text
チラシ一覧 → 確認状態 = 確認待ち
特売カレンダー商品 → 有効=false / 確認待ち
```

Notionの `チラシ一覧 > 確認待ち` で以下を比較します。

```text
画像URL / 画像一覧
チラシ名
掲載期間
抽出件数
抽出サマリー
元URL
```

正しければ `確認状態` を `確認済み` に変更します。

次回自動実行、または手動で:

```text
applyFlyerReviewsNow
```

を実行すると、そのチラシ由来の商品だけ:

```text
確認状態 = 確認済み
有効 = true
```

になります。

誤りがある場合はチラシ一覧を `要修正` にします。そのチラシの商品は `有効=false` のままです。

---

# 8. 月間チラシ

月初に配信され、約20日以上の掲載期間を持つチラシは `月間` として扱います。

Shufoo一覧と画像の掲載期間をGeminiが読み取り、`チラシ一覧 > 月間チラシ` に表示します。

月間チラシと週次/日替わりチラシは同時に有効化できます。同一商品でも元チラシ・価格・期間が異なれば別行として保持します。

---

# 9. チラシ初回テスト

順番:

```text
1. testSummitFlyerCatalogParse
2. testSummitFlyerCatalogAutomation
3. Notion「チラシ一覧 > 確認待ち」で画像と抽出結果を確認
4. 正しいチラシを「確認済み」に変更
5. applyFlyerReviewsNow
6. testTodayConfirmedSummitFlyerNotification
7. installDailySummitFlyerReviewedTrigger
```

詳細は `FLYER_TEST.md`。

---

# 10. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `runDailySummitFlyerCatalogReviewedAutomation` | 毎日6時台 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

一度だけ `installDailySummitFlyerReviewedTrigger` を実行すると、旧チラシトリガーを削除して新しい確認済み通知トリガーへ切り替えます。

---

# 11. トラブル時

チラシ解析0件:
- `testSummitFlyerCatalogParse` の実行ログを見る
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
- 特売カレンダーの対象商品が `確認状態=確認済み / 有効=true` か
- 当日が `特売日` の範囲内か

---

# 12. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。
