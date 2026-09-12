# FLYER_TEST.md

サミット ミナノ分倍河原店のチラシ自動取得・Notion特売カレンダー登録・LINE日次通知の実機確認手順です。

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

この機能は `gas/FlyerDeals.gs` 1ファイルで動きます。GitHubへコミットしただけではApps Scriptへ自動反映されないため、最新版をGASプロジェクトへコピーしてください。

---

# 1. Notion特売カレンダーDB

新しいデータベースを1つ作成します。

| 名前 | 型 |
|---|---|
| `商品名` | Title |
| `特売日` | Date |
| `価格` | Rich text |
| `容量・単位` | Rich text |
| `店舗` | Select |
| `備考` | Rich text |
| `優先度` | Number |
| `チラシURL` | URL |
| `チラシ識別` | Rich text |
| `識別キー` | Rich text |
| `有効` | Checkbox |
| `更新日時` | Date |

`特売日`を使ったカレンダービューを追加してください。

Notion IntegrationをこのDBへ接続し、読み取り・作成・更新を許可します。

---

# 2. Script Properties

既存:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

追加必須:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密値はチャットやGitHubへ貼らず、Apps Scriptの「プロジェクトの設定 → スクリプト プロパティ」へ直接設定してください。

---

# 3. Apps Scriptのタイムゾーン

```text
(GMT+09:00) Tokyo
```

に設定してください。

---

# 4. 解析だけテスト

```text
testSummitFlyerParse
```

実行ログの `deals` 配列に商品名・価格・対象日が入れば解析成功です。この段階ではNotionもLINEも変更しません。

---

# 5. Notion + LINEまでテスト

```text
testSummitFlyerAutomation
```

期待結果:

1. 最新チラシがNotion DBへ登録される
2. 同じ商品・価格・期間を再実行しても重複ページが増えず、既存ページが更新される
3. `特売日`のカレンダービューに商品が表示される
4. LINEへ当日の特売一覧が届く
5. 通知内容はNotionを読み直した結果と一致する

---

# 6. LINE通知だけテスト

Notion登録済みデータから通知だけ確認する場合:

```text
testTodaySummitFlyerNotification
```

Gemini画像解析は行いません。

---

# 7. 毎日自動実行

一度だけ:

```text
installDailySummitFlyerTrigger
```

を実行します。

以降は毎日6時台に `runDailySummitFlyerAutomation` が実行されます。

処理順:

```text
サミット公式店舗ページを取得
↓
iframe / 公開フォールバックからチラシ候補を取得
↓
新しいチラシならGeminiで商品名・価格・対象日を抽出
↓
Notion特売カレンダーDBへ同期
↓
Notionから今日の特売を再取得
↓
LINE通知
```

---

# 8. 重複・旧チラシ

`店舗 + 商品 + 価格 + 容量 + 特売期間`から`識別キー`を作るため、同一特売の重複登録を防ぎます。

新しいチラシへ切り替わった場合、今日以降に残っている旧チラシ行は `有効=false` にします。過去データは履歴として残します。

Notionの通常ビューでは `有効 = true` のフィルターを追加すると、現在有効な特売だけ表示できます。

---

# 9. 取得元

優先:

```text
サミット公式店舗ページ
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

公式ページからチラシ画像を十分取得できない場合は、同店舗の公開チラシページをフォールバックとして使います。

高頻度取得はせず、日次実行を前提にしています。

---

# 10. Gemini利用量

チラシページ・画像URL等から署名を作り、前回と同一なら保存済み解析結果を再利用します。

```text
同じチラシ → Gemini画像解析なし
新しいチラシ → Gemini画像解析
```

---

# 11. トラブルシューティング

## Notionへ登録できない

確認:

```text
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID
```

DBのプロパティ名・型が上表と完全一致しているか、IntegrationがDBへ接続されているか確認してください。

## LINE通知が失敗

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

を確認します。

## チラシが0件

`testSummitFlyerParse`の実行ログを確認し、サイト側のHTML/画像配信形式変更を確認します。

---

# 12. 実機確認完了条件

```text
[ ] testSummitFlyerParse で deals が取得できる
[ ] 商品名・価格・対象日がおおむねチラシと一致する
[ ] testSummitFlyerAutomation でNotionへ登録される
[ ] 同じ内容を2回実行しても重複ページが増えない
[ ] 新チラシ切替時に旧未来データが有効=falseになる
[ ] Notionカレンダービューに特売が表示される
[ ] testTodaySummitFlyerNotification でLINEへ当日特売が届く
[ ] installDailySummitFlyerTrigger を実行済み
```
