# LINE Notion Bot

LINEを入口に、家計簿・予算・カード利用通知・固定費/サブスク・メモ・Notion・Gemini AIをまとめて扱う個人向けBotです。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: 日常保守、障害切り分け、復旧
- `DEVELOPMENT.md`: 長期ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIとPostback設計ルール
- `PHASE1_TEST.md`: カード自動化テスト
- `PHASE2_TEST.md`: 月次・予算判断テスト
- `FLYER_TEST.md`: サミットチラシ・生活カレンダー実機テスト
- `gas/README.md`: GAS固有設定

機能変更時はREADME.md / SETUP.md / DEVELOPMENT.mdを更新し、UI変更時はUI_DESIGN.mdも更新します。

---

# サミットチラシ → Notion生活カレンダー

対象店舗:

```text
サミット ミナノ分倍河原店
公式: https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
Shufoo一覧: https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

Notionは役割を2つに分けます。

```text
チラシ一覧
→ 元資料・画像・掲載期間・抽出結果・確認状態を管理

生活カレンダー
→ 実際に日付で見る予定を管理
   特売は「種類=特売」として登録
```

生活カレンダーは将来、特売以外にも家計・引き落とし・給料・メモ・通常予定を載せられる汎用DBです。

## GASファイル

チラシ機能でApps Scriptへコピーするのは次の2ファイルです。

```text
gas/FlyerDeals.gs
  → HTML/iframe/画像取得、Notion/LINE共通関数

gas/FlyerLifeCalendar.gs
  → Shufoo一覧、月間/週次/日替わり判定、確認待ち登録、生活カレンダー同期、確認済み通知
```

`FlyerReview.gs` / `FlyerReviewedNotify.gs` は途中版のため使用しません。

## 処理フロー

```text
Shufooチラシ一覧 + 公式ページを確認
↓
新しいチラシ画像をGeminiで読み取り
↓
月間 / 週次 / 日替わり / その他 に分類
↓
Notion「チラシ一覧」へ確認待ちで保存
↓
生活カレンダーへ 種類=特売 / 確認待ち / 有効=false で保存
↓
画像URLと抽出サマリーを人が確認
↓
正しいチラシだけ「確認済み」
↓
そのチラシ由来の特売だけ有効=true
↓
今日 + 確認済み + 有効=true の特売だけLINE通知
```

月初から月末近くまで有効な長期チラシは `月間` として管理します。月間・週次・日替わりチラシは同時に保持できます。

## Notion「生活カレンダー」

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

主な共通項目:

| 名前 | 型 |
|---|---|
| `予定名` | Title |
| `日付` | Date |
| `種類` | Select |
| `金額` | Number |
| `内容` | Rich text |
| `有効` | Checkbox |
| `更新日時` | Date |

`種類`:

```text
特売 / 家計 / 引き落とし / 給料 / メモ / 予定 / その他
```

チラシ由来の特売では、さらに価格・容量・店舗・元チラシ名・元画像URL・確認状態なども保存します。

カレンダービュー `生活カレンダー` は `日付` を基準にし、`有効=true` の予定だけ表示します。

## Notion「チラシ一覧」

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

主な項目:

```text
チラシ名
種別
掲載期間
元URL
画像URL
画像一覧
抽出件数
抽出サマリー
確認状態
チラシ識別
取得日時
```

ビュー `確認待ち` と `月間チラシ` を作成済みです。

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
checkCardEmails                         → 1時間ごと
runDailySummitLifeCalendarAutomation    → 毎日 朝6時台
sendDailyMemoReminder                   → 毎日 朝8時ごろ
sendDailyBudgetAlert                    → 毎日 20時ごろ
sendDailyCardPendingReminder            → 毎日 20〜21時ごろ
sendMonthEndCardCheck                   → 毎日 21時ごろ
sendWeeklyFinanceReport                 → 毎週日曜 20時ごろ
```

チラシの旧トリガーは `installDailySummitLifeCalendarTrigger` で削除されます。

---

# 保守・テスト

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

チラシ・生活カレンダー: `FLYER_TEST.md`

障害対応: `MAINTENANCE.md`

Phase 3はまだ開始していません。
