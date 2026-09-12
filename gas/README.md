# GAS セットアップ

GASはカード監視・定期通知・サミットのチラシ取得を担当します。

主なファイル:

```text
gas/Code.gs                  カード利用メール監視
gas/FinanceReports.gs        家計簿定期通知
gas/DailyMemo.gs             メモ通知
gas/FlyerDeals.gs            チラシ取得・共通Notion/LINE処理
gas/FlyerLifeCalendar.gs     Shufoo一覧・月間判定・確認フロー・生活カレンダー同期
```

`FlyerReview.gs` / `FlyerReviewedNotify.gs` は途中版のため使用しません。

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

`NOTION_FLYER_DATABASE_ID` は互換名を残しており、現在はNotionの `生活カレンダー` を指します。

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

秘密情報はソースコード、GitHub、チャットへ直接書かないでください。

---

# サミットチラシ → 生活カレンダー

対象:

```text
サミット ミナノ分倍河原店

公式:
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer

Shufoo一覧:
https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore
```

役割:

`FlyerDeals.gs`:

```text
HTML / iframe / 画像URL取得
Notion API共通関数
LINE通知共通関数
```

`FlyerLifeCalendar.gs`:

```text
Shufooチラシ一覧を取得
↓
複数チラシを画像解析
↓
月間 / 週次 / 日替わり / その他 に分類
↓
チラシ一覧DBへ確認待ちで保存
↓
生活カレンダーへ 種類=特売 / 有効=false で保存
↓
チラシ一覧の確認状態を反映
↓
確認済み + 有効=true + 今日対象の特売だけLINE通知
```

---

# Notion確認フロー

```text
新チラシ
↓
チラシ一覧 = 確認待ち
生活カレンダー = 種類=特売 / 確認待ち / 有効=false
↓
Notion「チラシ一覧 > 確認待ち」で画像と抽出内容を照合
↓
正しい → 確認済み
誤り   → 要修正
```

手動ですぐ反映:

```text
applyLifeFlyerReviewsNow
```

確認済み由来だけ `有効=true` になります。

---

# 月間チラシ

目安:

```text
掲載期間20日以上 → 月間
掲載期間4日以上  → 週次
1〜2日           → 日替わり
それ以外         → その他
```

Notion `チラシ一覧 > 月間チラシ` で確認します。

---

# 初回テスト

1. 解析だけ:

```text
testSummitLifeFlyerParse
```

2. Notionへ確認待ち同期:

```text
testSummitLifeFlyerSync
```

3. Notionで画像と抽出内容を確認し、正しいチラシを `確認済み` に変更。

4. 状態反映:

```text
applyLifeFlyerReviewsNow
```

5. 確認済み特売だけ通知:

```text
testTodayLifeCalendarFlyerNotification
```

詳細は `FLYER_TEST.md`。

---

# 最終日次トリガー

一度だけ:

```text
installDailySummitLifeCalendarTrigger
```

最終入口:

```text
runDailySummitLifeCalendarAutomation
```

を毎日6時台へ設定します。旧チラシトリガーはインストール関数が削除します。

---

# 通常カード監視

```text
checkCardEmails → 1時間ごと
```

対応カード:
- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

---

# 定期通知

```text
runDailySummitLifeCalendarAutomation → 毎日6時台
sendDailyMemoReminder               → 毎日朝8時ごろ
sendDailyBudgetAlert               → 毎日20時ごろ
sendDailyCardPendingReminder       → 毎日20〜21時ごろ
sendMonthEndCardCheck              → 毎日21時ごろ
sendWeeklyFinanceReport            → 毎週日曜20時ごろ
```

---

# GASとGitHubの同期

GitHubの`.gs`更新はApps Scriptへ自動反映されません。

チラシ機能でコピーするのは:

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

---

# トラブルシューティング

チラシ画像0件:
- `testSummitLifeFlyerParse` のログを見る。
- Shufoo/公式のHTML・画像配信形式変更を確認。

Notion同期失敗:
- `NOTION_API_KEY`
- `NOTION_FLYER_DATABASE_ID`
- `NOTION_FLYER_LIST_DATABASE_ID`
- Integrationが生活カレンダー/チラシ一覧の両DBへ接続されているか

LINE通知0件:
- チラシ一覧が `確認済み` か
- 生活カレンダーが `種類=特売 / 確認状態=確認済み / 有効=true` か
- 今日が `日付` の範囲内か

LINE送信失敗:
- `LINE_USER_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`

詳細は `FLYER_TEST.md` を参照してください。
