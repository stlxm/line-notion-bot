# FLYER_TEST.md

サミット ミナノ分倍河原店の通常チラシ・月間チラシ・Notion確認フロー・LINE日次通知の実機確認手順です。

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
gas/FlyerReview.gs
gas/FlyerReviewedNotify.gs
```

3ファイルを同じApps Scriptプロジェクトへ置きます。

---

# 2. Notion DB

## 特売カレンダー

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

主な項目:

```text
商品名
特売日
価格
容量・単位
店舗
備考
優先度
チラシURL
チラシ識別
識別キー
有効
更新日時
元チラシ名
元画像URL
確認状態
```

`特売日`のカレンダービューは作成済みで、`有効=true`を表示します。

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

# 4. チラシ一覧・画像取得テスト

最初に:

```text
testSummitFlyerCatalogParse
```

を実行します。

この段階ではNotionの確認状態を変更しません。

実行ログで確認:

```text
imageUrls
flyers
```

最低確認項目:

```text
[ ] Shufoo/公式からチラシ画像URLが1件以上取得できる
[ ] flyers が1件以上ある
[ ] チラシ名が画像/ページと対応している
[ ] 掲載期間が画像/ページと対応している
[ ] 商品名・価格・容量が画像と概ね一致する
[ ] dealの image_url が元画像と対応している
```

重要: このテストが成功するまでは自動トリガーを作りません。

---

# 5. 月間チラシ確認

月初の1か月チラシが掲載されている時期にログを確認します。

期待:

```text
type = 月間
```

目安として掲載期間20日以上を月間扱いします。

確認:

```text
[ ] 月初〜月末近くまでのチラシが別チラシとして取得される
[ ] type が 月間 になっている
[ ] start_date / end_date がチラシ記載期間と一致する
[ ] 月間チラシの商品が週次チラシと混同されていない
```

チラシ側に期間が読めない場合は、無理に月間と推測して登録しない設計です。

---

# 6. Notionへ確認待ちで同期

次に:

```text
testSummitFlyerCatalogAutomation
```

を実行します。

期待:

```text
チラシ一覧
  確認状態 = 確認待ち

特売カレンダー
  確認状態 = 確認待ち
  有効 = false
```

この時点では読み取り結果はまだ信用済みにしません。

---

# 7. 画像と抽出情報を確認

Notionで:

```text
チラシ一覧
→ 確認待ち
```

を開きます。

各チラシについて比較:

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
[ ] チラシ画像が正しい店舗のもの
[ ] チラシ名が合っている
[ ] 月間/週次/日替わりの分類が妥当
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

にします。

---

# 8. 確認状態を商品へ反映

Notionで状態変更後、Apps Scriptから:

```text
applyFlyerReviewsNow
```

を実行します。

期待:

確認済みチラシ由来:

```text
確認状態 = 確認済み
有効 = true
```

要修正チラシ由来:

```text
確認状態 = 要修正
有効 = false
```

確認待ち:

```text
有効 = false
```

のままです。

---

# 9. 確認済み商品のLINE通知テスト

```text
testTodayConfirmedSummitFlyerNotification
```

期待:
- 今日が対象日の商品だけ届く。
- `確認済み` だけ届く。
- `確認待ち` / `要修正` は通知されない。
- `有効=false` は通知されない。

月間チラシと週次チラシの両方に今日の特売があれば、確認済みの両方から候補が入ります。

---

# 10. 重複テスト

同じチラシで再度:

```text
testSummitFlyerCatalogAutomation
```

を実行します。

確認:

```text
[ ] 同じチラシ行が無制限に増えない
[ ] 同じ特売行が無制限に増えない
[ ] 確認済みだったチラシが勝手に確認待ちへ戻らない
```

---

# 11. 新しいチラシ更新テスト

新しいチラシが配信された後に日次処理またはテストを実行します。

期待:

```text
新しいチラシ
→ チラシ一覧へ確認待ち
→ LINEへ「新しいチラシを読み取りました」通知
→ 画像URLを表示
→ 商品はまだ有効化されない
```

画像と結果を確認してから確認済みにします。

---

# 12. 最終トリガー

全テストが正常なら一度だけ:

```text
installDailySummitFlyerReviewedTrigger
```

を実行します。

この関数は旧トリガー:

```text
runDailySummitFlyerAutomation
runDailySummitFlyerNotionAutomation
runDailySummitFlyerCatalogAutomation
```

を削除し、最終版:

```text
runDailySummitFlyerCatalogReviewedAutomation
```

を毎日6時台に登録します。

**運用ではこの確認済み版だけを使ってください。**

---

# 13. 日次処理

最終的な毎朝の流れ:

```text
Shufoo一覧 + 公式ページ確認
↓
変更なし → Gemini解析なし
変更あり → 新しいチラシ画像をGemini解析
↓
新チラシを確認待ちでNotionへ保存
↓
以前に確認状態を変更したチラシを商品へ反映
↓
期限切れ商品を無効化
↓
今日 + 確認済み + 有効=true の商品だけ取得
↓
LINE通知
```

新しいチラシは、その日の朝に解析されても確認するまでは日次特売通知へ入りません。

---

# 14. トラブルシューティング

## 画像が0件

`testSummitFlyerCatalogParse`のログを確認します。

Shufoo側のHTML/JavaScript/画像URL形式が変更された可能性があります。

## 月間チラシが出ない

- 実際に月間チラシが現在掲載されているか確認。
- 画像またはHTMLから掲載期間を読み取れているか確認。
- `start_date/end_date`をログで確認。

## Notion同期失敗

```text
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID
NOTION_FLYER_LIST_DATABASE_ID
```

とIntegration接続を確認します。

## 通知が0件

特売カレンダーで対象商品が:

```text
確認状態 = 確認済み
有効 = true
特売日 = 今日を含む
```

になっているか確認します。

---

# 15. 完了条件

```text
[ ] testSummitFlyerCatalogParse で画像とflyersを取得
[ ] 現在掲載中の月間チラシがある場合は月間として判定
[ ] 画像URLと抽出内容をNotionで比較できる
[ ] 新規データが確認待ち / 有効=false で入る
[ ] 確認済みへ変更して applyFlyerReviewsNow で有効化できる
[ ] 要修正は通知対象にならない
[ ] 確認済みだけLINEへ届く
[ ] 同一チラシの重複が増えない
[ ] installDailySummitFlyerReviewedTrigger を実行済み
```

ここまで通ったらPhase 2.7を実機確認完了とします。
