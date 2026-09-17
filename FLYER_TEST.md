# FLYER_TEST.md

サミット ミナノ分倍河原店の通常チラシ・月間チラシ・生活カレンダー・LINE日次通知の実機確認手順です。

状態: **Phase 2.7 基本機能は実機確認済み / 手動確認廃止の自動反映モードは要切替確認**

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
gas/FlyerAutoMode.gs
```

役割:

```text
FlyerDeals.gs        共通ヘルパー + LINE通知
FlyerLifeCalendar.gs 取得・解析・Notion同期本体
FlyerAutoMode.gs     手動確認をなくす自動有効化 + 新日次入口
```

---

# 2. Notion DB

## 生活カレンダー

```text
Database ID: 684f959e451047389505a95ed368a7d6
```

主な項目:

```text
予定名 / 日付 / 種類 / 価格 / 容量・単位 / 店舗 / 備考
優先度 / チラシURL / チラシ識別 / 識別キー
元チラシID / 元チラシ名 / 元画像URL / 確認状態 / 有効 / 更新日時
```

`確認状態` と `有効` の列は互換性のため残しますが、日常運用でユーザーが変更する必要はありません。

## チラシ一覧

```text
Database ID: fdd0c0ce50974273b9b88f5272858e90
```

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

---

# 4. これまでの実機確認

配信ID検出:

```text
3342326844037
9783726841844
3487936841840
4441736841834
2187006858976
```

解析・同期成功:

```text
detected=5
analyzed=5
missing=[]
flyers=5
deals=57
```

`2187006858976` は `2026-09-12〜2026-09-14` の3日間チラシとして同期済み。

通知では短期特売優先・重複整理まで実機確認済みです。

---

# 5. 手動確認フロー廃止

旧仕様:

```text
新規チラシ
↓
確認待ち
↓
Notionで手動で確認済みに変更
↓
生活カレンダー / LINE通知へ反映
```

新仕様:

```text
新規チラシ
↓
Gemini解析成功
↓
Notionへ同期
↓
自動で確認済み / 有効=true
↓
生活カレンダー / LINE通知へ反映
```

ユーザーがNotionで確認済みに変更する作業はありません。

---

# 6. 日次トリガー切替

Apps Scriptへ `FlyerAutoMode.gs` を追加した後、1回だけ実行:

```text
installDailySummitLifeCalendarAutoTrigger
```

この関数は旧チラシ系日次トリガーを削除し、次を毎日6時台に登録します。

```text
runDailySummitLifeCalendarAutoAutomation
```

---

# 7. 自動反映モードの軽量テスト

Gemini再解析なしで確認できます。

```text
testSummitLifeCalendarAutoMode
```

確認:

```text
[ ] 既存の掲載中「確認待ち」チラシが確認済みになる
[ ] 掲載中の生活カレンダー特売が有効=trueになる
[ ] 今日の特売通知が届く
[ ] Notionで手動操作しなくても動く
```

その後LINEで:

```text
特売情報
```

確認:

```text
[ ] 確認状態を手動変更していなくても今日の特売が表示される
[ ] 1〜7日間の短期特売が先頭
[ ] 月間・長期特売が後ろ
[ ] 最大20件
```

---

# 8. 保守時テスト

配信ID確認（Gemini不要）:

```text
testSummitShufooDeliveryIds
```

解析確認:

```text
testSummitLifeFlyerParse
```

同期確認:

```text
testSummitLifeFlyerSync
```

自動有効化 + 今日通知:

```text
testSummitLifeCalendarAutoMode
```

Gemini無料枠を消費するため、同期・解析テストは必要時だけ行います。

---

# 9. 完了条件

```text
[x] 複数配信IDを検出
[x] 全ID解析成功時だけNotion同期
[x] チラシ一覧と生活カレンダー連携
[x] 短期特売を月間特価より先に通知
[x] 通知前の重複整理
[x] LINE「特売情報」動作
[ ] FlyerAutoMode.gsをApps Scriptへ反映
[ ] 自動反映トリガーへ切替
[ ] 手動確認なしで日次通知まで動作確認
```
