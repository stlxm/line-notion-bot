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

`FlyerDeals.gs` は共通ヘルパー + LINE通知、`FlyerLifeCalendar.gs` は取得・解析・Notion同期本体です。

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

通知コードも `予定名` / `日付` を読みます。旧名 `商品名` / `特売日` は使いません。

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

# 4. 配信ID検出テスト（Geminiを使わない）

```text
testSummitShufooDeliveryIds
```

実機で確認済みの5ID:

```text
3342326844037
9783726841844
3487936841840
4441736841834
2187006858976
```

---

# 5. 配信IDごとの解析確認

```text
testSummitLifeFlyerParse
```

各 `flyerPages` について `id / url / imageUrls`、各 `flyers` について `id / type / start_date / end_date / deals` を確認します。

---

# 6. 種別確認

```text
20日以上 → 月間
3〜19日  → 週次
1〜2日   → 日替わり
判定不能 → その他
```

`2187006858976` は実機で `2026-09-12〜2026-09-14` の3日間チラシとして確認済みなので `週次` です。

---

# 7. Notionへ同期

```text
testSummitLifeFlyerSync
```

安全条件:

```text
detected == analyzed
missing == []
```

実機成功例:

```text
detected=5
analyzed=5
missing=[]
flyers=5
deals=57
```

1IDでも解析失敗した場合はNotionへ部分同期しないのが正常です。

---

# 8. 画像と抽出情報を確認

Notionの `チラシ一覧 → 確認待ち` で、配信ID・画像URL・元URL・種別・掲載期間・抽出件数・抽出サマリーを比較します。

正しければ `確認済み`、誤りがあれば `要修正` にします。

---

# 9. 確認状態を生活カレンダーへ反映

```text
applyLifeFlyerReviewsNow
```

期待:

```text
確認済み配信ID由来:
種類 = 特売
確認状態 = 確認済み
有効 = true
```

---

# 10. LINE通知テスト

```text
testTodaySummitFlyerNotification
```

期待ログ:

```text
[Notion今日分] YYYY-MM-DD / 元=N件 / 重複整理後=M件
```

2026-09-12 実機経過:

```text
元=114件 → 83件
元=114件 → 67件
```

次回は第2段階の重複整理を反映後、67件からさらに減るか、少なくとも代表的な重複が消えることを確認します。

期待LINE:

```text
🛒 サミット ミナノ分倍河原店
【YYYY-MM-DD の特売】

🔥 今日・短期特売
・...
  12日・13日限り

📅 月間・長期特売
・...
```

確認:

```text
[ ] 今日が対象日の特売だけ届く
[ ] 確認済み / 有効=true だけ届く
[ ] 1〜7日間の短期特売が先に出る
[ ] 8日以上の月間・長期特売は後ろに出る
[ ] 「12日・13日限り」等の備考が短期欄に出る
[ ] 350ml×24 と 500ml×24 等の別容量は別商品として残る
```

## 第2段階の重複整理確認

次の組み合わせが通知上で1件になることを確認します。

```text
マルちゃん ソースやきそば / 108円 / 3食入
マルちゃんソースやきそば / 108円 / 3食

お刺身サーモン (切り落とし) / 999円 / 6切入、1パック
刺身用サーモン各種 / 999円 / 6切入 1パック
```

安全条件:

```text
完全正規化商品名一致
または
同じ商品ファミリー + 同じ元画像 + 同じ対象期間

かつ
価格一致
かつ
容量/個数に矛盾なし
```

Notion元データは削除しません。LINE通知表示だけを整理します。

---

# 11. 重複テスト

通知前重複整理はNotion行を削除せず、LINE表示だけを整理します。既存Notionデータは安全のため自動削除しません。

---

# 12. 最終トリガー

通知テストまで正常後、一度だけ:

```text
installDailySummitLifeCalendarTrigger
```

最終入口:

```text
runDailySummitLifeCalendarAutomation
```

---

# 13. 完了条件

```text
[ ] 5配信IDを正しく検出
[ ] 5IDすべて解析成功
[ ] 2187006858976 が 2026-09-12〜2026-09-14 で同期
[ ] チラシ一覧で画像と抽出内容を確認
[ ] 確認済みを生活カレンダーへ反映
[ ] testTodaySummitFlyerNotification で短期特売が先頭
[ ] マルちゃんソースやきそばの 3食入/3食 が1件
[ ] 999円・6切のサーモン表記揺れが1件
[ ] 別容量商品は別件で残る
[ ] 月間・長期特売が後半に表示
[ ] installDailySummitLifeCalendarTrigger を実行済み
```

ここまで通ったらPhase 2.7を実機確認完了とします。
