# FLYER_TEST.md

サミット ミナノ分倍河原店の通常チラシ・月間チラシ・Notion確認フロー・生活カレンダー・LINE日次通知の実機確認手順です。

対象:

```text
公式:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufoo店舗ID:
264241
```

GitHubのGASファイルはApps Scriptへ自動反映されません。

---

# 1. Apps Scriptへコピーするファイル

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

この2ファイルを同じApps Scriptプロジェクトへ置きます。

---

# 2. Notion DB

## 生活カレンダー

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

チラシ由来の特売では以下を使います。

```text
予定名
日付
種類
価格
容量・単位
店舗
備考
優先度
チラシURL
チラシ識別
識別キー
元チラシID
元チラシ名
元画像URL
確認状態
有効
更新日時
```

## チラシ一覧

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

項目:

```text
チラシ名
配信ID
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

未設定でもチラシ解析は `gemini-3.5-flash-lite` を使用します。

---

# 4. 最重要: 配信ID検出テスト

まずApps Scriptの `FlyerLifeCalendar.gs` をGitHub最新版で上書きしてから:

```text
testSummitLifeFlyerParse
```

を実行します。

実行ログの先頭に:

```text
検出した配信ID: [...]
```

が出ます。

今回の修正ではチラシ名ではなく、Shufoo URLの:

```text
/t/asp_iframe/shop/264241/<配信ID>/
```

を1チラシとして扱います。

確認済みの別配信ID例:

```text
9783726841844
4441736841834
```

現在9月1日からのチラシが3種類掲載されている場合の期待:

```text
[ ] 検出した配信IDが3件
[ ] 9783726841844 が含まれる
[ ] 4441736841834 が含まれる
[ ] 3件目も別IDとして表示される
```

ここで1件しか出ない場合はGeminiの問題ではなく、Shufoo一覧HTMLからのID抽出側を追加修正します。

---

# 5. 配信IDごとの画像・解析確認

同じ `testSummitLifeFlyerParse` の続きで、各 `flyerPages` を確認します。

```text
id
url
imageUrls
```

さらに `flyers` では:

```text
id
type
start_date
end_date
deals
```

を確認します。

期待:

```text
[ ] 配信IDごとに別オブジェクト
[ ] 各IDに対応する画像URLが入る
[ ] 月間チラシと別種類のチラシが混ざらない
[ ] 商品名・価格・容量・日付が画像と概ね一致
```

---

# 6. 種別確認

名前ではなく掲載期間を基準にします。

```text
20日以上 → 月間
4〜19日  → 週次
1〜2日   → 日替わり
その他   → その他
```

確認:

```text
[ ] 同じ9月1日開始でも配信IDが違えば別チラシ
[ ] 月間チラシはtype=月間
[ ] 他の種類を月間チラシと統合していない
```

---

# 7. Notionへ確認待ちで同期

```text
testSummitLifeFlyerSync
```

期待:

```text
チラシ一覧
  配信IDごとに1行
  確認状態 = 確認待ち

生活カレンダー
  種類 = 特売
  元チラシID = 該当配信ID
  確認状態 = 確認待ち
  有効 = false
```

現在3チラシなら、チラシ一覧には3つの別配信IDが見えるのが正常です。

---

# 8. 画像と抽出情報を確認

Notionで:

```text
チラシ一覧
→ 確認待ち
```

を開きます。

比較:

```text
配信ID
画像URL / 画像一覧
元URL
種別
掲載期間
抽出件数
抽出サマリー
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

# 9. 確認状態を生活カレンダーへ反映

```text
applyLifeFlyerReviewsNow
```

期待:

確認済み配信ID由来:

```text
種類 = 特売
元チラシID = 確認済み配信ID
確認状態 = 確認済み
有効 = true
```

要修正:

```text
確認状態 = 要修正
有効 = false
```

---

# 10. LINE通知テスト

```text
testTodayLifeCalendarFlyerNotification
```

期待:
- 今日が対象日の特売だけ届く。
- `確認済み` だけ届く。
- 複数の確認済み配信IDに今日対象の商品があれば両方から入る。
- `確認待ち / 要修正 / 有効=false` は届かない。

---

# 11. 重複テスト

同じチラシで再度:

```text
testSummitLifeFlyerSync
```

確認:

```text
[ ] 同じ配信IDのチラシ一覧行が無制限に増えない
[ ] 同じ配信ID+商品+価格+期間の予定が無制限に増えない
[ ] 別配信IDは別行として保持される
[ ] 確認済みが勝手に確認待ちへ戻らない
```

---

# 12. 最終トリガー

全テスト正常後、一度だけ:

```text
installDailySummitLifeCalendarTrigger
```

を実行します。

最終版:

```text
runDailySummitLifeCalendarAutomation
```

を毎日6時台に登録します。

---

# 13. 完了条件

```text
[ ] testSummitLifeFlyerParse で現在の配信ID数を正しく検出
[ ] 9783726841844 と 4441736841834 を別チラシとして認識
[ ] 現在3種類なら3つ目も別IDとして認識
[ ] 各IDの画像と商品情報が対応
[ ] testSummitLifeFlyerSync で配信IDごとに確認待ち登録
[ ] 画像と抽出内容をNotionで比較できる
[ ] 確認済みへ変更して applyLifeFlyerReviewsNow で有効化
[ ] 生活カレンダーに元チラシID付きで表示
[ ] 確認済みだけLINEへ届く
[ ] installDailySummitLifeCalendarTrigger を実行済み
```

ここまで通ったらPhase 2.7を実機確認完了とします。
