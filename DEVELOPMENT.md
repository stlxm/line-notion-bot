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

当初の `特売カレンダー` を汎用の `生活カレンダー` へ変更。

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

チラシ由来行は `価格 / 容量・単位 / 店舗 / 元チラシID / 元チラシ名 / 元画像URL / 確認状態` も保持する。

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

GAS Script Property名は互換性のため `NOTION_FLYER_DATABASE_ID` を継続利用するが、実体は生活カレンダーDB。

---

# Phase 2.7 — 月間チラシ一覧・画像確認・生活カレンダー連携

状態: **実装完了・要実機確認**

対象:

```text
サミット ミナノ分倍河原店
Shufoo店舗ID: 264241
```

最終実装ファイル:
- `gas/FlyerDeals.gs`: HTML/iframe/画像取得、Notion/LINE共通関数。
- `gas/FlyerLifeCalendar.gs`: Shufoo配信ID列挙、配信ID単位の個別解析、確認待ち、生活カレンダー同期、確認済み通知、日次トリガー。
- `FLYER_TEST.md`: 実機確認手順。

## 2026-09-12 重要修正 — 名前ではなくShufoo配信IDで分離

実機テストで、9月1日から有効なチラシが3種類あるのに1件しか認識されないことを確認。

原因:

```text
旧実装
一覧ページから取得した複数画像をまとめてGeminiへ渡す
↓
Geminiに「別チラシ」を推定させる
↓
同期間/似た名称の複数チラシが1件へ統合される場合がある
```

修正後:

```text
Shufoo一覧HTML
↓
/t/asp_iframe/shop/264241/<配信ID>/ を列挙
↓
配信IDごとにページ取得
↓
配信IDごとに画像取得
↓
配信IDごとにGeminiを個別実行
↓
掲載期間から 月間 / 週次 / 日替わり / その他 を判定
```

確認済みの別配信ID例:

```text
9783726841844
4441736841834
```

同じ店舗でも配信IDが違えば必ず別チラシとして扱う。`チラシ名` は表示用であり、識別には使用しない。

Notion変更:

```text
チラシ一覧
+ 配信ID Rich text

生活カレンダー
+ 元チラシID Rich text
```

重複キーも配信IDを含める。

## 安全仕様

```text
新しい配信IDを検出
↓
その配信IDだけ画像解析
↓
チラシ一覧 = 確認待ち
生活カレンダー = 種類=特売 / 確認待ち / 有効=false
↓
画像URLと抽出内容を人が確認
↓
正しい → チラシ一覧を確認済み
誤り   → 要修正
↓
applyLifeFlyerReviewsNow または次回日次処理
↓
確認済みの配信ID由来だけ 有効=true
↓
今日 + 確認済み + 有効=true の特売だけLINE通知
```

月間判定:
- 20日以上: `月間`
- 4〜19日: `週次`
- 1〜2日: `日替わり`
- その他: `その他`
- 画像/HTMLから期間が読めない場合は登録しない。

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

現在の再開位置:

```text
1. Apps Scriptの FlyerLifeCalendar.gs をGitHub最新版で上書き
2. FlyerDeals.gs はそのまま最新版を使用
3. testSummitLifeFlyerParse を実行
4. ログ先頭の「検出した配信ID」を確認
5. 現在チラシが3種類なら配信IDも3件出ることを確認
6. 9783726841844 と 4441736841834 が別IDとして出ることを確認
7. 各IDの imageUrls / 掲載期間 / 商品を確認
8. testSummitLifeFlyerSync
9. Notion「チラシ一覧 > 確認待ち」で配信IDごとに別行になっていることを確認
10. 正しい配信IDを確認済みに変更
11. applyLifeFlyerReviewsNow
12. 生活カレンダーで 元チラシID / 確認済み / 有効=true を確認
13. testTodayLifeCalendarFlyerNotification
14. installDailySummitLifeCalendarTrigger
15. 問題なければPhase 2.7を完了扱いへ変更
16. ユーザー指示があった場合だけPhase 3開始
```

---

# 変更履歴

## 2026-09-12

- Phase 2を2A / 2B / 2Cへ細分化。
- Phase 2.5の目的ベース案内を実装し、実機動作確認済み。
- サミットチラシ自動化を追加。
- Notion `チラシ一覧` DBと確認ビューを作成。
- `特売カレンダー` を汎用 `生活カレンダー` へ変更。
- 完成版GASを `FlyerLifeCalendar.gs` に統合。
- 実機で複数チラシが1件へ統合される問題を発見。
- チラシ名/画像グループ推定方式を廃止し、Shufoo `配信ID` 単位の個別取得・個別Gemini解析へ変更。
- `チラシ一覧.配信ID` / `生活カレンダー.元チラシID` を追加。
- README / SETUP / DEVELOPMENT を配信ID方式へ更新。
