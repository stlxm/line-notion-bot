# LINE Notion Bot

LINEを入口に、家計簿・予算・カード利用通知・固定費/サブスク・メモ・Notion・Gemini AIをまとめて扱う個人向けBotです。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: 日常保守、障害切り分け、復旧
- `DEVELOPMENT.md`: 長期ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIとPostback設計ルール
- `PHASE1_TEST.md`: カード自動化テスト
- `PHASE2_TEST.md`: 月次・予算判断テスト
- `FLYER_TEST.md`: サミットチラシ自動化・確認フローテスト
- `gas/README.md`: GAS固有設定

機能変更時はREADME.md / SETUP.md / DEVELOPMENT.mdを更新し、UI変更時はUI_DESIGN.mdも更新します。

---

# サミット特売Notionカレンダー・チラシ一覧・毎日通知

対象店舗:

```text
サミット ミナノ分倍河原店
公式: https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
Shufoo一覧: https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

Apps Scriptの3ファイルで動きます。

```text
gas/FlyerDeals.gs
  → 公式/iframe/画像取得、共通Notion/LINE処理

gas/FlyerReview.gs
  → Shufooチラシ一覧、月間/週次/日替わり判定、画像ごとの解析、確認待ち登録

gas/FlyerReviewedNotify.gs
  → 確認済みチラシだけを毎朝LINE通知
```

処理:

```text
Shufooチラシ一覧 + 公式ページを確認
↓
新しい画像・チラシだけGeminiで画像認識
↓
チラシ単位に「月間 / 週次 / 日替わり / その他」を判定
↓
Notion「チラシ一覧」へ
  チラシ名 / 掲載期間 / 元URL / 画像URL / 抽出サマリーを保存
↓
商品をNotion「特売カレンダー」へ確認待ちで保存
↓
画像と抽出結果を人が確認
↓
チラシ一覧の確認状態を「確認済み」に変更
↓
そのチラシの商品だけ有効化
↓
確認済みの今日の特売だけLINEへ毎朝通知
```

月初から月末近くまで有効な長期チラシは `月間` として扱います。月間チラシと週次・日替わりチラシは同時に保持できます。

## Notion「チラシ一覧」

主な項目:

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

Notionには `確認待ち` ビューと `月間チラシ` ビューを作成済みです。

## Notion「特売カレンダー」

従来項目に加えて:

| 名前 | 型 |
|---|---|
| `元チラシ名` | Rich text |
| `元画像URL` | URL |
| `確認状態` | Select |

を持ちます。

新規解析商品は最初 `有効=false / 確認待ち` です。チラシ一覧を `確認済み` にしたものだけ `有効=true` になり、カレンダー・LINE通知へ採用されます。

Googleカレンダーは使いません。Notionが正本です。

---

# 迷ったときの案内

```text
？
ヘルプ
おすすめ
何したい 節約したい
コマンド
```

- `？` / `ヘルプ`: 目的から選ぶ
- `おすすめ`: 現在の状態を見て最大3件提案
- `何したい ○○`: 自由文から関連コマンドを提案
- `コマンド`: 全コマンドを一覧表示

---

# 主なLINEコマンド

```text
メニュー
？
おすすめ
何したい 節約したい
コマンド
家計判断
支出 1200 ラーメン
今月
今日使える
ペース
予算提案
異常支出
年間予測
月締め
月次レビュー
貯金目標
予算一覧
週次レポート
固定費一覧
カード未処理
カードテスト
カード自動登録
メモ 牛乳を買う
メモ一覧
AI 今月の食費を分析して
AI Lite
AI Flash
AI Model
AI改善
```

---

# Phase 2 — 月次・予算判断

状態: **実装完了・要実機確認**

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

# AIモデル切替

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLiteです。

---

# Phase 1 — カード自動化

主な機能:
- 過去分類からおすすめジャンル表示
- 同じ店の一括分類
- 条件を満たした店の安全な自動登録
- 家計簿DBとの重複確認
- 店名変更
- サブスク→固定費DB→次回検出除外
- 月末未処理チェック

---

# GAS推奨トリガー

```text
checkCardEmails                              → 1時間ごと
runDailySummitFlyerCatalogReviewedAutomation → 毎日 朝6時台
sendDailyMemoReminder                        → 毎日 朝8時ごろ
sendDailyBudgetAlert                         → 毎日 20時ごろ
sendDailyCardPendingReminder                 → 毎日 20〜21時ごろ
sendMonthEndCardCheck                        → 毎日 21時ごろ
sendWeeklyFinanceReport                      → 毎週日曜 20時ごろ
```

チラシの旧トリガーは `installDailySummitFlyerReviewedTrigger` で削除されます。

---

# 保守・テスト

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

チラシ: `FLYER_TEST.md`

障害対応: `MAINTENANCE.md`

Phase 3はまだ開始していません。
