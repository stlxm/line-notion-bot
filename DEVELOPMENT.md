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

## 2026-09-12 重要修正 — 配信IDの検出をリンク+画像URLへ拡張

実機テストでは、一覧ページのURLとしては1件しか検出できなかったが、同じページ内の画像URLには複数の配信IDが存在した。

確認できた画像URL由来ID例:

```text
2187006858976
9783726841844
3487936841840
4441736841834
```

Shufoo画像URL形式:

```text
.../c/YYYY/MM/DD/c/<配信ID>/img/image1_00.jpg
```

原因は2つあった。

```text
1. 個別ページリンクだけを探索していた
2. {id, url} のオブジェクト配列に文字列用 uniqueStrings_ を使っていたため、
   全要素が [object Object] 扱いになり最初の1件だけ残っていた
```

修正後:

```text
Shufoo一覧/公式/iframe
↓
個別リンクから配信ID抽出
+
画像URLから配信ID抽出
↓
ID文字列をキーに重複除去
↓
配信IDごとに個別ページ取得
↓
画像URLの配信IDが一致する画像だけを優先
↓
配信IDごとにGemini個別解析
```

チラシ名は表示用であり、同一性判定には使わない。

Geminiを使わない軽量検出テストを追加:

```text
testSummitShufooDeliveryIds
```

Notion:

```text
チラシ一覧
+ 配信ID Rich text

生活カレンダー
+ 元チラシID Rich text
```

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
- 3日: `その他`
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
3. testSummitShufooDeliveryIds を実行（Gemini消費なし）
4. 候補配信ID / 検出した配信ID を確認
5. 9783726841844 / 4441736841834 / 3487936841840 等が別IDとして出ることを確認
6. IDが揃ったら testSummitLifeFlyerParse
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
- `配信ID` 単位の個別取得・個別Gemini解析へ変更。
- 画像URLからも配信IDを抽出するよう改善。
- オブジェクト配列を `uniqueStrings_` に渡して1件に潰していたバグを修正。
- `testSummitShufooDeliveryIds` を追加。
- `チラシ一覧.配信ID` / `生活カレンダー.元チラシID` を追加。
- README / SETUP / DEVELOPMENT を更新。
