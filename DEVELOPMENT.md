# DEVELOPMENT.md

このファイルはLINE Notion Botの長期開発メモ・進捗管理・次回再開位置の基準です。

## 運用ルール

- 機能追加時は README.md / SETUP.md / DEVELOPMENT.md を更新する。
- UI変更時は UI_DESIGN.md も更新する。
- 実機未確認のものは「実装済み・要実機確認」とする。
- LINE Postback dataは300文字以内。
- Gemini不要な処理はPython / Notion / GASで行う。
- 自動処理よりデータ保全を優先する。
- 大きいPhaseはA/B/Cへ細分化し、各ブロックごとにテスト可能な状態で止める。

---

# Phase 0 — 開発基盤

状態: 完了

- DEVELOPMENT / MAINTENANCE / UI_DESIGN
- README / SETUP役割分離
- Postback 300文字ルール

---

# Phase 1 — カード入力をほぼ自動化

状態: **実装完了・要実機確認**

実装済み:
- 店名正規化・ジャンル学習・おすすめ
- 同じ店の一括分類
- 3回以上100%一致+本人ONだけの自動登録
- 家計簿重複ガード
- 速報/確定候補照合
- サブスク→固定費DB→次回検出除外
- 月末未処理チェック
- `カードテスト`

安全仕様:
- 曖昧な重複候補は自動削除しない。
- 自動登録は本人が明示ONするまで有効化しない。

---

# AIモデル運用

状態: **実装済み・要実機確認**

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLite。月次レビューも選択中モデルを使う。

---

# Phase 2 — 月次・予算判断

状態: **実装完了・要実機確認**

## Phase 2A — 日々の家計判断

```text
今日使える
ペース
異常支出
```

## Phase 2B — 月次判断

```text
予算提案
月締め
月締め YYYY-MM
月締め確定 YYYY-MM
月締め確定強制 YYYY-MM
月次レビュー
月次レビュー YYYY-MM
```

安全仕様:
- 月締めは終了済み月のみ。
- 通常確定はカード未処理があると停止。
- 強制確定は明示コマンドのみ。

## Phase 2C — 将来予測・目標

```text
年間予測
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

---

# Phase 2.5 — 目的ベースの案内

状態: **実装完了・実機動作確認済み**

```text
？
ヘルプ
おすすめ
何したい 節約したい
コマンド
```

仕様:
- `？ / ヘルプ`: 目的別Flex。
- `おすすめ`: 状況から最大3件。
- `何したい ○○`: Pythonキーワード判定。
- `コマンド`: 全一覧。
- Geminiは使わない。

---

# Phase 2.6 — サミット特売Notionカレンダー基盤

状態: **実装完了・要実機確認**

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

基盤:
- `gas/FlyerDeals.gs`: HTML/iframe/画像取得、Gemini画像解析、Notion/LINE共通処理。
- Notion `特売カレンダー` DBを作成済み。
- `特売日`のカレンダービューを作成済み。
- Googleカレンダーは使用しない。

---

# Phase 2.7 — 月間チラシ一覧・画像確認フロー

状態: **実装完了・要実機確認**

追加要望:
- 月初に配信される1か月分のチラシも読み取る。
- Shufooのチラシ一覧を取得元として利用する。
- チラシ名 / 掲載期間 / URL / 画像URLを一覧管理する。
- 画像と抽出結果を確認してから特売情報を有効化する。

Shufoo対象:

```text
https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

実装ファイル:
- `gas/FlyerDeals.gs`: 共通取得・Notion・LINE処理。
- `gas/FlyerReview.gs`: Shufoo一覧取得、複数チラシ解析、月間/週次/日替わり分類、確認待ち同期。
- `gas/FlyerReviewedNotify.gs`: 確認済みだけを日次通知する安全な入口。
- `FLYER_TEST.md`: 実機確認手順。

Notion `チラシ一覧` DBを作成済み:
- `チラシ名` Title
- `種別` Select (`月間 / 週次 / 日替わり / その他`)
- `掲載期間` Date
- `元URL` URL
- `画像URL` URL
- `画像一覧` Rich text
- `抽出件数` Number
- `抽出サマリー` Rich text
- `確認状態` Select (`確認待ち / 確認済み / 要修正`)
- `チラシ識別` Rich text
- `取得日時` Date

作成済みビュー:
- `確認待ち`
- `月間チラシ`

`特売カレンダー`へ追加済み:
- `元チラシ名` Rich text
- `元画像URL` URL
- `確認状態` Select

安全仕様:

```text
新チラシ検出
↓
Gemini画像解析
↓
チラシ一覧 = 確認待ち
特売商品 = 確認待ち / 有効=false
↓
画像URLと抽出サマリーを人が確認
↓
正しい → チラシ一覧を確認済みに変更
誤り   → 要修正
↓
applyFlyerReviewsNow または次回日次処理
↓
確認済み由来だけ 有効=true
↓
確認済み + 有効=true + 今日対象だけLINE通知
```

月間判定:
- 掲載期間が約20日以上なら `月間`。
- 約4日以上なら `週次`。
- 1〜2日中心なら `日替わり`。
- 画像/HTMLから期間が読み取れない場合は推測で確定しない。

最終の日次入口は必ず:

```text
runDailySummitFlyerCatalogReviewedAutomation
```

トリガー作成は:

```text
installDailySummitFlyerReviewedTrigger
```

この関数は旧チラシトリガーを削除して、安全な確認済み通知へ切り替える。

注意:
- `runDailySummitFlyerCatalogAutomation` は確認済み限定通知の最終入口ではない。運用トリガーに使わない。
- Shufooの実際のHTML/画像配信形式はGAS実行で未確認。`testSummitFlyerCatalogParse`で必ず実機確認する。
- Geminiの画像認識結果も自動で正解扱いしない。

---

# Phase 3 — 入力・修正・検索

状態: **未着手**

対象: #32, #33, #34, #36, #37, #38, #39, #40, #45, #46

Phase 2.7の実機確認が終わるまでPhase 3へ進めない。

---

# Phase 4 — メモ・URL

状態: 未着手

# Phase 5 — AI品質

状態: 未着手

# Phase 6 — 信頼性

状態: 未着手

# Phase 7 — 特殊家計・出力

状態: 未着手

---

# 次に再開する場所

```text
1. Apps Scriptへ FlyerDeals.gs / FlyerReview.gs / FlyerReviewedNotify.gs をコピー
2. Script Propertiesへ NOTION_FLYER_DATABASE_ID / NOTION_FLYER_LIST_DATABASE_ID / NOTION_API_KEY / GEMINI_API_KEY を設定
3. testSummitFlyerCatalogParse を実行
4. ログで画像URL・複数チラシ・月間判定を確認
5. testSummitFlyerCatalogAutomation を実行
6. Notion「チラシ一覧 > 確認待ち」で画像と抽出結果を照合
7. 正しいチラシを「確認済み」に変更
8. applyFlyerReviewsNow を実行
9. 特売カレンダー側が 確認済み / 有効=true になったことを確認
10. testTodayConfirmedSummitFlyerNotification を実行
11. installDailySummitFlyerReviewedTrigger を一度だけ実行
12. 問題なければPhase 2.7を完了扱いへ変更
13. ユーザー指示があった場合だけPhase 3開始
```

---

# 変更履歴

## 2026-09-12

- Phase 2を2A / 2B / 2Cへ細分化。
- Phase 2.5として目的ベース案内を追加し、実機動作確認済み。
- サミット特売Notionカレンダー基盤を追加。
- 月初の1か月チラシ対応を追加。
- Shufooチラシ一覧URLを取得元へ追加。
- Notion `チラシ一覧` DBを作成。
- `確認待ち` / `月間チラシ` ビューを作成。
- 特売カレンダーに元チラシ・元画像・確認状態を追加。
- 新規解析データを確認前は `有効=false` にする安全仕様へ変更。
- `FlyerReview.gs` / `FlyerReviewedNotify.gs` を追加。
- 確認済みだけを日次LINE通知する最終トリガーへ変更。
- README / SETUP / DEVELOPMENT / FLYER_TEST / gas/README を更新。

## 2026-09-11

- Phase 1カード自動化を実装。
- AI Lite / Flash切替を追加。
- Phase 2 LINEコマンドを接続。
