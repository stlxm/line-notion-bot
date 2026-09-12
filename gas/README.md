# GAS セットアップ

GASはカード監視・定期通知・サミットのチラシ取得を担当します。

主なファイル:

```text
gas/Code.gs                 カード利用メール監視
gas/FinanceReports.gs       家計簿定期通知
gas/DailyMemo.gs            メモ通知
gas/FlyerDeals.gs           チラシ取得・共通Notion/LINE処理
gas/FlyerReview.gs          Shufooチラシ一覧・月間判定・確認待ち同期
gas/FlyerReviewedNotify.gs  確認済みだけの日次通知
```

---

# Script Properties

共通:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

チラシ用:

```text
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密情報はソースコード、GitHub、チャットへ直接書かないでください。

---

# サミット特売・チラシ一覧

対象:

```text
サミット ミナノ分倍河原店

公式:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufoo一覧:
https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

## 役割

`FlyerDeals.gs`:

```text
HTML / iframe / 画像URL取得
Gemini画像解析の共通関数
Notion API共通関数
LINE通知共通関数
```

`FlyerReview.gs`:

```text
Shufooチラシ一覧を取得
↓
複数のチラシ画像を解析
↓
月間 / 週次 / 日替わり / その他 に分類
↓
チラシ一覧DBへ確認待ちで保存
↓
商品を特売カレンダーへ 有効=false / 確認待ち で保存
```

`FlyerReviewedNotify.gs`:

```text
チラシ一覧の確認状態を商品へ反映
↓
確認済み + 有効=true + 今日対象だけ取得
↓
LINE通知
```

---

# Notion確認フロー

新しいチラシは自動で信用しません。

```text
新チラシ
↓
チラシ一覧 = 確認待ち
商品 = 確認待ち / 有効=false
↓
Notion「チラシ一覧 > 確認待ち」で確認
↓
画像URL / 掲載期間 / 抽出サマリーを照合
↓
正しい → 確認済み
誤り   → 要修正
```

手動ですぐ反映する場合:

```text
applyFlyerReviewsNow
```

確認済みのチラシ由来だけ商品が `有効=true` になります。

---

# 月間チラシ

月初に配信される長期チラシもShufoo一覧から取得します。

目安:

```text
掲載期間20日以上 → 月間
掲載期間4日以上  → 週次
1〜2日中心       → 日替わり
それ以外         → その他
```

Notion `チラシ一覧 > 月間チラシ` ビューで確認できます。

月間・週次・日替わりは同時に保持できます。

---

# 初回テスト

1. チラシ一覧・画像解析のみ:

```text
testSummitFlyerCatalogParse
```

2. Notionへ確認待ち同期:

```text
testSummitFlyerCatalogAutomation
```

3. Notionで画像と抽出内容を確認し、正しいチラシを `確認済み` に変更。

4. 状態反映:

```text
applyFlyerReviewsNow
```

5. 確認済みだけ通知:

```text
testTodayConfirmedSummitFlyerNotification
```

詳しくは `FLYER_TEST.md`。

---

# 最終日次トリガー

一度だけ:

```text
installDailySummitFlyerReviewedTrigger
```

を実行してください。

この関数は旧チラシトリガー:

```text
runDailySummitFlyerAutomation
runDailySummitFlyerNotionAutomation
runDailySummitFlyerCatalogAutomation
```

を削除し、最終版:

```text
runDailySummitFlyerCatalogReviewedAutomation
```

を毎日6時台へ設定します。

**運用では確認済み版だけを使います。**

---

# Gemini利用量

チラシ一覧・画像URL等から署名を作ります。

```text
変更なし → 画像解析しない
変更あり → Gemini画像解析
```

ただしShufoo/サイト側のHTMLに毎回変化する値が含まれる場合は署名が変わる可能性があります。実機テストでログを確認してください。

---

# 通常カード監視

```text
checkCardEmails → 1時間ごと
```

Gmail Message IDで同一メールの再処理を抑止します。

対応カード:
- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

---

# 定期通知

```text
runDailySummitFlyerCatalogReviewedAutomation → 毎日6時台
sendDailyMemoReminder                        → 毎日朝8時ごろ
sendDailyBudgetAlert                         → 毎日20時ごろ
sendDailyCardPendingReminder                 → 毎日20〜21時ごろ
sendMonthEndCardCheck                        → 毎日21時ごろ
sendWeeklyFinanceReport                      → 毎週日曜20時ごろ
```

---

# GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。

チラシ機能で今回コピーするファイル:

```text
gas/FlyerDeals.gs
gas/FlyerReview.gs
gas/FlyerReviewedNotify.gs
```

---

# トラブルシューティング

チラシ画像0件:
- `testSummitFlyerCatalogParse`のログを見る。
- Shufoo/公式のHTML・画像配信形式変更を確認。

月間判定できない:
- 掲載期間を画像/HTMLから読み取れているか確認。
- 月間チラシ自体が現在掲載中か確認。

Notion同期失敗:
- `NOTION_API_KEY`
- `NOTION_FLYER_DATABASE_ID`
- `NOTION_FLYER_LIST_DATABASE_ID`
- Integrationが両DBへ接続されているか

LINE通知0件:
- チラシ一覧が `確認済み` か
- 商品が `確認状態=確認済み / 有効=true` か
- 今日が `特売日` の範囲内か

LINE送信失敗:
- `LINE_USER_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`

詳細は `FLYER_TEST.md` を参照してください。
