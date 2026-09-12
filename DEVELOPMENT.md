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

---

# AIモデル運用

状態: **実装済み・要実機確認**

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
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

---

# Phase 2.6 — 生活カレンダー基盤

状態: **実装完了・要実機確認**

当初の `特売カレンダー` を汎用の `生活カレンダー` へ変更した。

目的:
- チラシ一覧DBは元資料の管理・確認に専念する。
- 実際に日付で見る情報は生活カレンダーへ集約する。
- 将来、特売以外に家計・引き落とし・給料・メモ・通常予定を同じカレンダーへ載せられるようにする。

生活カレンダー主項目:

```text
予定名 Title
日付 Date
種類 Select
金額 Number
内容 Rich text
有効 Checkbox
更新日時 Date
```

種類:

```text
特売 / 家計 / 引き落とし / 給料 / メモ / 予定 / その他
```

チラシ由来行は価格・容量・店舗・元チラシ名・元画像URL・確認状態も保持する。

Database IDは互換性のため既存と同じ:

```text
684f959e451047389505a95ed368a7d6
```

GAS Script Property名も当面 `NOTION_FLYER_DATABASE_ID` を継続利用するが、実体は生活カレンダーDB。

---

# Phase 2.7 — 月間チラシ一覧・画像確認・生活カレンダー連携

状態: **実装完了・要実機確認**

対象:

```text
サミット ミナノ分倍河原店
公式: https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
Shufoo: https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

最終実装ファイル:
- `gas/FlyerDeals.gs`: 取得・Notion・LINE共通関数。
- `gas/FlyerLifeCalendar.gs`: Shufoo一覧、月間判定、確認待ち、生活カレンダー同期、確認済み通知、日次トリガー。
- `FLYER_TEST.md`: 実機確認手順。

途中版 `FlyerReview.gs` / `FlyerReviewedNotify.gs` は使用しない。

Notion `チラシ一覧` DB:
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

安全仕様:

```text
新チラシ検出
↓
Gemini画像解析
↓
チラシ一覧 = 確認待ち
生活カレンダー = 種類=特売 / 確認待ち / 有効=false
↓
画像URLと抽出サマリーを人が確認
↓
正しい → チラシ一覧を確認済み
誤り   → 要修正
↓
applyLifeFlyerReviewsNow または次回日次処理
↓
確認済み由来だけ 有効=true
↓
今日 + 確認済み + 有効=true の特売だけLINE通知
```

月間判定:
- 20日以上: `月間`
- 4日以上: `週次`
- 1〜2日: `日替わり`
- その他: `その他`
- 画像/HTMLから期間が読めない場合は推測で確定しない。

最終日次入口:

```text
runDailySummitLifeCalendarAutomation
```

トリガー作成:

```text
installDailySummitLifeCalendarTrigger
```

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

ユーザーはPhase 2.5以降の手作業をまだしていない。

次回の実機作業はこの順番:

```text
1. Apps Scriptへ FlyerDeals.gs / FlyerLifeCalendar.gs をコピー
2. GASタイムゾーンを Tokyo に設定
3. Script Propertiesの LINE_USER_ID / LINE_CHANNEL_ACCESS_TOKEN を確認
4. GEMINI_API_KEY / NOTION_API_KEY をGASへ設定
5. NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
6. NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
7. Notion Integrationを生活カレンダー/チラシ一覧の両方へ接続
8. testSummitLifeFlyerParse
9. testSummitLifeFlyerSync
10. チラシ一覧 > 確認待ち で画像と抽出内容を照合
11. 正しいチラシを確認済みに変更
12. applyLifeFlyerReviewsNow
13. 生活カレンダーで 種類=特売 / 確認済み / 有効=true を確認
14. testTodayLifeCalendarFlyerNotification
15. installDailySummitLifeCalendarTrigger
16. 問題なければPhase 2.7を完了扱いへ変更
17. ユーザー指示があった場合だけPhase 3開始
```

---

# 変更履歴

## 2026-09-12

- Phase 2を2A / 2B / 2Cへ細分化。
- Phase 2.5の目的ベース案内を実装し、実機動作確認済み。
- サミットチラシ自動化を追加。
- 月初の月間チラシとShufoo一覧へ対応。
- Notion `チラシ一覧` DBと確認ビューを作成。
- `特売カレンダー` を汎用 `生活カレンダー` へ変更。
- 生活カレンダーへ `種類 / 金額 / 内容` を追加。
- チラシは `種類=特売` として生活カレンダーへ入れる設計へ変更。
- 完成版GASを `FlyerLifeCalendar.gs` に統合。
- 新規解析データは確認前 `有効=false`、確認済みのみ日次通知する安全仕様を維持。
- README / SETUP / DEVELOPMENT / FLYER_TEST / gas/README を更新。
