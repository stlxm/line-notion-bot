# FLYER_TEST.md

サミット ミナノ分倍河原店のチラシ自動取得・Notion特売カレンダー登録・LINE日次通知の実機確認手順です。

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

この機能は `gas/FlyerDeals.gs` の取得/解析機能と `gas/FlyerNotion.gs` のNotion同期機能を組み合わせて動きます。GitHubへコミットしただけではApps Scriptへ自動反映されないため、両方をGASプロジェクトへコピーしてください。

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
| `チラシURL` | URL |
| `優先度` | Number |
| `識別キー` | Rich text |
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

実行ログの`deals`配列に商品名・価格・対象日が入れば解析成功です。

---

# 5. Notion同期だけテスト

```text
testSummitFlyerNotionSyncOnly
```

期待結果:

1. 期限切れの特売ページがアーカイブされる
2. 今日以降の特売がNotion DBへ登録される
3. 同じ商品・価格・期間を再実行しても重複ページが増えず、既存ページが更新される
4. `特売日`のカレンダービューに商品が表示される

Notion APIでは完全削除ではなく`archived=true`としてアーカイブします。通常のDB・カレンダービューからは消えます。

---

# 6. Notion + LINEまでテスト

```text
testSummitFlyerNotionAutomation
```

期待結果:

1. 期限切れページが整理される
2. 最新チラシがNotionへ同期される
3. LINEへ当日の特売一覧が届く

---

# 7. 毎日自動実行

一度だけ:

```text
installDailySummitFlyerNotionTrigger
```

を実行します。

この関数は旧Googleカレンダー版の`runDailySummitFlyerAutomation`トリガーが存在すれば削除し、`runDailySummitFlyerNotionAutomation`を毎日6時台に実行するトリガーだけを作成します。

処理順:

```text
期限切れNotionページをアーカイブ
↓
サミット公式店舗ページを取得
↓
必要な場合だけ同店舗トクバイへフォールバック
↓
Geminiで商品名・価格・対象日を抽出
↓
Notion特売カレンダーDBへ同期
↓
今日の特売をLINE通知
```

---

# 8. 期限切れだけ手動整理

```text
cleanupExpiredSummitFlyerPages
```

`特売日`の終了日が今日より前ならアーカイブします。終了日がない単日特売は開始日を終了日として扱います。

---

# 9. 取得元

優先:

```text
サミット公式店舗ページ
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

公式ページからチラシ画像を十分取得できない場合だけ、同店舗のトクバイページをフォールバックに使います。

高頻度取得はせず、日次実行を前提にしています。

---

# 10. Gemini利用量

チラシページ・画像URL等から署名を作り、前回と同一なら保存済み解析結果を再利用します。同じチラシが続く間に毎日同じ画像をGeminiへ送り直さない設計です。

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

`testSummitFlyerParse`のログを確認し、サイト側のHTML/画像配信形式変更を確認します。

---

# 12. 実機確認完了条件

```text
[ ] testSummitFlyerParse で deals が取得できる
[ ] 商品名・価格・対象日がおおむねチラシと一致する
[ ] testSummitFlyerNotionSyncOnly でNotionへ登録される
[ ] 同じ内容を2回実行しても重複ページが増えない
[ ] 期限切れページがDB/カレンダービューから消える
[ ] testSummitFlyerNotionAutomation でLINEへ当日特売が届く
[ ] installDailySummitFlyerNotionTrigger を実行済み
```
