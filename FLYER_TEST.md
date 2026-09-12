# FLYER_TEST.md

サミット ミナノ分倍河原店のチラシ自動取得・Googleカレンダー登録・LINE日次通知の実機確認手順です。

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

この機能は `gas/FlyerDeals.gs` で動きます。GitHubへコミットしただけではApps Scriptへ自動反映されないため、必ずGASプロジェクトへ最新版をコピーしてください。

---

# 1. Script Properties

既存:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

追加:

```text
GEMINI_API_KEY
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
FLYER_CALENDAR_ID=<専用GoogleカレンダーのID>
```

`FLYER_CALENDAR_ID`を設定しない場合は、Apps Scriptを実行しているGoogleアカウントのデフォルトカレンダーへ登録されます。

推奨は「サミット特売」などの専用Googleカレンダーを作り、そのカレンダーIDを設定する方法です。

---

# 2. Apps Scriptのタイムゾーン

プロジェクト設定でタイムゾーンを次にしてください。

```text
(GMT+09:00) Tokyo
```

---

# 3. 解析だけテスト

Apps Scriptエディタで次を手動実行します。

```text
testSummitFlyerParse
```

初回は外部通信とGemini利用の権限確認が出る場合があります。

実行ログにJSONが表示され、`deals`配列に商品名・価格・対象日が入れば成功です。

例:

```json
{
  "deals": [
    {
      "product": "商品名",
      "price": "198円",
      "unit": "1パック",
      "start_date": "2026-09-12",
      "end_date": "2026-09-12",
      "notes": "税抜",
      "priority": 1
    }
  ]
}
```

チラシの内容やサイト側の配信方式によっては0件になることがあります。その場合は実行ログの `[チラシ取得失敗]` / `[画像取得失敗]` / `Gemini flyer analysis failed` を確認します。

---

# 4. カレンダー + LINEまでテスト

次を手動実行します。

```text
testSummitFlyerAutomation
```

期待結果:

1. Googleカレンダーに対象日の終日予定が作成される
2. タイトルが `🛒 サミット特売（○件）` になる
3. 説明欄に商品・価格・公式チラシURLが入る
4. LINEへ当日の特売一覧が届く

同じ日を再実行した場合、自動作成した同日の古いイベントを削除して作り直すため、重複予定は増えません。

---

# 5. 毎日自動実行

手動で一度だけ:

```text
installDailySummitFlyerTrigger
```

を実行します。

これで `runDailySummitFlyerAutomation` を毎日6時台に実行する時間主導型トリガーが作成されます。

Apps Scriptの時刻トリガーは指定時刻ちょうどではなく、指定した時間帯の中で実行されます。

---

# 6. 取得元

優先:

```text
サミット公式店舗ページ
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

公式ページのチラシ表示はiframe / JavaScript依存のため、画像を十分取得できない場合だけ次をフォールバックに使います。

```text
くふうトクバイ
https://tokubai.co.jp/サミット/7221
```

高頻度スクレイピングは行わず、日次実行を前提にしています。

---

# 7. Gemini利用量

チラシのページ・画像URL等から署名を作り、前回と同一なら保存済み解析結果を再利用します。

そのため、同じチラシが数日掲載されている間に毎日Gemini画像解析を繰り返す設計にはしていません。

新しいチラシへ切り替わった時だけ再解析する想定です。

---

# 8. データの扱い

チラシから読み取れる内容だけを登録し、不明な商品名・価格・日付を推測で補完しないようGeminiへ指示しています。

ただし画像読み取りには誤認識の可能性があります。LINE通知とカレンダーには必ず次の注意書きを付けます。

```text
価格・在庫は店頭表示を優先してください。
```

---

# 9. トラブルシューティング

## GEMINI_API_KEY が未設定

```text
Script Properties に GEMINI_API_KEY を設定してください。
```

Renderに設定しているキーをチャットへ貼らず、Apps ScriptのScript Propertiesへ直接設定してください。

## カレンダーが見つからない

`FLYER_CALENDAR_ID`を確認します。不要なら一旦削除するとデフォルトカレンダーを使います。

## LINE通知が失敗

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

を確認します。

## チラシが0件

サイト側のHTML/画像配信形式が変更された可能性があります。`testSummitFlyerParse`のログを確認し、`gas/FlyerDeals.gs`の画像URL抽出部分を更新します。

---

# 10. 実機確認完了条件

```text
[ ] testSummitFlyerParse で deals が取得できる
[ ] 商品名・価格・対象日がおおむねチラシと一致する
[ ] testSummitFlyerAutomation でGoogleカレンダーへ登録される
[ ] LINEへ当日の特売が届く
[ ] 2回実行してもカレンダー予定が重複しない
[ ] installDailySummitFlyerTrigger を実行済み
```
