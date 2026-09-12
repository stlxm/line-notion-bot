# FLYER_TEST.md

サミット ミナノ分倍河原店の通常チラシ・月間チラシ・Notion確認フロー・生活カレンダー・LINE日次通知の実機確認手順です。

対象:

```text
公式:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufooチラシ一覧:
https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

GitHubのGASファイルはApps Scriptへ自動反映されません。

---

# 1. Apps Scriptへコピーするファイル

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

この2ファイルを同じApps Scriptプロジェクトへ置きます。

`FlyerReview.gs` / `FlyerReviewedNotify.gs` は途中版なのでコピーしません。

---

# 2. Notion DB

## 生活カレンダー

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

共通項目:

```text
予定名
日付
種類
金額
内容
有効
更新日時
```

種類:

```text
特売 / 家計 / 引き落とし / 給料 / メモ / 予定 / その他
```

チラシ由来の特売では以下も使います。

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

ビュー `生活カレンダー` は `日付` を基準に `有効=true` を表示します。

## チラシ一覧

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

項目:

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

ビュー:

```text
確認待ち
月間チラシ
```

Notion Integrationを両DBへ接続してください。

---

# 3. Script Properties

必須:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

`NOTION_FLYER_DATABASE_ID` は名前を互換維持していますが、現在は生活カレンダーDBを指します。

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密値はチャットやGitHubへ貼らず、Apps Scriptのスクリプトプロパティへ直接設定します。

Apps Scriptタイムゾーン:

```text
(GMT+09:00) Tokyo
```

---

# 4. 画像取得・解析だけテスト

最初に:

```text
testSummitLifeFlyerParse
```

を実行します。

この段階ではNotionへ登録しません。

実行ログで確認:

```text
imageUrls
flyers
```

確認項目:

```text
[ ] チラシ画像URLが1件以上取得できる
[ ] flyers が1件以上ある
[ ] チラシ名が画像/ページと対応している
[ ] 掲載期間が画像/ページと対応している
[ ] 商品名・価格・容量が画像と概ね一致する
[ ] dealの image_url が元画像と対応している
```

ここが通るまでは自動トリガーを作りません。

---

# 5. 月間チラシ確認

月初の1か月チラシが掲載されている場合:

```text
type = 月間
```

になることを確認します。

目安:

```text
20日以上 → 月間
4日以上  → 週次
1〜2日   → 日替わり
```

確認:

```text
[ ] 月間チラシが別チラシとして取得される
[ ] start_date / end_date が画像記載期間と一致する
[ ] 月間チラシ商品が週次/日替わりと混同されていない
```

---

# 6. Notionへ確認待ちで同期

```text
testSummitLifeFlyerSync
```

期待:

```text
チラシ一覧
  確認状態 = 確認待ち

生活カレンダー
  種類 = 特売
  確認状態 = 確認待ち
  有効 = false
```

---

# 7. 画像と抽出情報を確認

Notionで:

```text
チラシ一覧
→ 確認待ち
```

を開きます。

比較:

```text
画像URL / 画像一覧
元URL
チラシ名
種別
掲載期間
抽出件数
抽出サマリー
```

確認ポイント:

```text
[ ] 正しい店舗のチラシ画像
[ ] チラシ名が合っている
[ ] 月間/週次/日替わり分類が妥当
[ ] 掲載期間が合っている
[ ] 抽出商品が画像に実在する
[ ] 価格が合っている
[ ] 容量・単位が合っている
[ ] 日替わり商品の日付が合っている
```

正しければ:

```text
確認状態 → 確認済み
```

誤りがあれば:

```text
確認状態 → 要修正
```

---

# 8. 確認状態を生活カレンダーへ反映

Notionで状態変更後:

```text
applyLifeFlyerReviewsNow
```

期待:

確認済みチラシ由来:

```text
種類 = 特売
確認状態 = 確認済み
有効 = true
```

要修正:

```text
確認状態 = 要修正
有効 = false
```

確認待ちは `有効=false` のままです。

---

# 9. LINE通知テスト

```text
testTodayLifeCalendarFlyerNotification
```

期待:
- 今日が対象日の特売だけ届く。
- `種類=特売` だけ届く。
- `確認済み` だけ届く。
- `確認待ち / 要修正` は届かない。
- `有効=false` は届かない。

---

# 10. 重複テスト

同じチラシで再度:

```text
testSummitLifeFlyerSync
```

確認:

```text
[ ] 同じチラシが無制限に増えない
[ ] 同じ特売予定が無制限に増えない
[ ] 確認済みが勝手に確認待ちへ戻らない
```

---

# 11. 最終トリガー

全テスト正常後、一度だけ:

```text
installDailySummitLifeCalendarTrigger
```

を実行します。

旧チラシ系トリガーを削除し、最終版:

```text
runDailySummitLifeCalendarAutomation
```

を毎日6時台に登録します。

---

# 12. 日次処理

```text
Shufoo一覧 + 公式ページ確認
↓
変更なし → Gemini解析なし
変更あり → 画像解析
↓
新チラシを確認待ちでチラシ一覧へ保存
↓
生活カレンダーへ 種類=特売 / 有効=false で保存
↓
以前の確認状態を反映
↓
期限切れ特売を無効化
↓
今日 + 種類=特売 + 確認済み + 有効=true を取得
↓
LINE通知
```

新しいチラシは、確認するまで日次特売通知へ入りません。

---

# 13. 完了条件

```text
[ ] testSummitLifeFlyerParse で画像とflyersを取得
[ ] 月間チラシがある場合は月間として判定
[ ] testSummitLifeFlyerSync で確認待ち登録
[ ] 画像URLと抽出内容をNotionで比較できる
[ ] 確認済みへ変更して applyLifeFlyerReviewsNow で有効化
[ ] 生活カレンダーに 種類=特売 で表示
[ ] 要修正は通知対象にならない
[ ] testTodayLifeCalendarFlyerNotification で確認済みだけLINEへ届く
[ ] 同一チラシ・特売の重複が増えない
[ ] installDailySummitLifeCalendarTrigger を実行済み
```

ここまで通ったらPhase 2.7を実機確認完了とします。
