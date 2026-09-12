# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Googleカレンダー・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
- `FLYER_TEST.md`: サミットチラシ自動化テスト
- `gas/README.md`: GAS詳細

---

# 1. 必要サービス

GitHub / Render / LINE Developers / Notion / Gmail / Google Apps Script / Google Calendar / Google AI Studio

Notion IntegrationはBotが使うすべてのDBへ接続し、読み取り・作成・更新を許可します。

---

# 2. Notion DB仕様

## 家計簿DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `日付` | Date |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `月別管理` | Relation |

環境変数: `NOTION_KAKEIBO_DATABASE_ID`

## 月別管理DB

既存項目:

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算`など | Number |

Phase 2Bで追加:

| 名前 | 型 | 用途 |
|---|---|---|
| `締め済み` | Checkbox | 月締め済みか |
| `締め日時` | Date | 月締め確定日時 |
| `確定支出` | Number | 月締め時の支出合計 |

環境変数: `NOTION_MONTHLY_DATABASE_ID`

## 固定費DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

環境変数: `NOTION_FIXED_DATABASE_ID`

カード未処理で`サブスク`を選ぶとこのDBへ登録/更新されます。`有効=true`の同一カード＋同一正規化店名は次回以降のカード検出から除外されます。

## カード未処理DB

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

環境変数: `NOTION_CARD_PENDING_DATABASE_ID`

## カード学習ルールDB

| 名前 | 型 |
|---|---|
| `店名キー` | Title |
| `表示名` | Rich text |
| `ジャンル` | Select |
| `学習回数` | Number |
| `一致回数` | Number |
| `自動登録` | Checkbox |
| `最終更新` | Date |

環境変数: `NOTION_CARD_RULES_DATABASE_ID`

## 貯金目標DB（Phase 2C）

| 名前 | 型 | 必須 |
|---|---|---|
| `目標名` | Title | 必須 |
| `目標額` | Number | 必須 |
| `現在額` | Number | 必須 |
| `期限` | Date | 任意 |
| `有効` | Checkbox | 必須 |

環境変数:

```text
NOTION_SAVINGS_GOALS_DATABASE_ID=<Database ID>
```

このDBが未設定でも、Phase 2A・2Bと年間予測は利用できます。

## メモDB

`メモ` Title / `日付` Date。環境変数: `NOTION_MEMO_DATABASE_ID`

## URL保存DB

`URL` Title。環境変数: `NOTION_URL_DATABASE_ID`

## AI改善ログDB

`質問` Title / `AI回答` Rich text / `期待する回答` Rich text / `登録日時` Date。

環境変数: `NOTION_AI_FEEDBACK_DATABASE_ID`

---

# 3. Render環境変数

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
NOTION_API_KEY
NOTION_PAGE_URL
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
NOTION_CARD_RULES_DATABASE_ID
NOTION_SAVINGS_GOALS_DATABASE_ID
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

`NOTION_SAVINGS_GOALS_DATABASE_ID`は貯金目標を使わない場合のみ省略可能です。

---

# 4. Gemini AIモデル

LINE AIはコード上でLiteから開始します。

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
AI 質問   → 選択中モデルで回答
```

`月次レビュー`も選択中モデルを使います。Render再起動・再デプロイ後はLiteへ戻ります。

---

# 5. 目的ベースのヘルプ

追加設定は不要です。Renderを最新mainで再デプロイすると利用できます。

```text
？
ヘルプ
おすすめ
何したい 節約したい
コマンド
```

- `？` / `ヘルプ`: 目的別Flexを表示
- `おすすめ`: 現在のカード未処理、予算、支出ペース、異常支出、メモなどから最大3件提案
- `何したい ○○`: キーワードベースで関連機能を提案
- `コマンド`: 全コマンド一覧

この案内機能はGeminiを使いません。

---

# 6. Phase 2

Phase 2は3ブロックに分けて導入・確認します。

## Phase 2A — 日々の家計判断

追加DB不要。

```text
今日使える
ペース
異常支出
```

## Phase 2B — 月次判断

月別管理DBへ`締め済み / 締め日時 / 確定支出`が必要です。

```text
予算提案
月締め
月締め YYYY-MM
月締め確定 YYYY-MM
月締め確定強制 YYYY-MM
月次レビュー
月次レビュー YYYY-MM
```

月締めは終了済みの月だけ実行できます。通常の`月締め確定`はカード未処理があると停止します。

## Phase 2C — 将来予測・目標

```text
年間予測
年間予測 2026
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

貯金目標だけ専用DBが必要です。

---

# 7. サミット特売カレンダー・LINE日次通知

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

Apps Scriptへ `gas/FlyerDeals.gs` を追加します。

## Script Properties

既存:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
```

追加必須:

```text
GEMINI_API_KEY
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
FLYER_CALENDAR_ID=<Google Calendar ID>
```

`GEMINI_API_KEY`はチャットやGitHubへ貼らず、Apps Scriptの「プロジェクトの設定 → スクリプト プロパティ」へ直接設定してください。

`FLYER_CALENDAR_ID`が未設定ならデフォルトカレンダーを使用します。専用の「サミット特売」カレンダーを作って、そのIDを設定する運用を推奨します。

## Apps Scriptタイムゾーン

```text
(GMT+09:00) Tokyo
```

に設定してください。

## 初回テスト

解析だけ:

```text
testSummitFlyerParse
```

カレンダー + LINEまで:

```text
testSummitFlyerAutomation
```

## 毎日自動実行

一度だけ:

```text
installDailySummitFlyerTrigger
```

を実行すると `runDailySummitFlyerAutomation` を毎日6時台に実行するトリガーを作成します。

動作:

```text
公式店舗ページ
↓
チラシiframe/画像を取得
↓
必要な場合だけ同店舗のトクバイページへフォールバック
↓
Geminiで特売商品・価格・対象日を抽出
↓
Googleカレンダーへ日別の終日イベント1件として登録
↓
当日分をLINEへ通知
```

同一チラシはキャッシュを再利用し、毎日Geminiで画像解析し直さないようにしています。

詳細テストは `FLYER_TEST.md` を参照してください。

---

# 8. GAS

Apps Scriptへ最新版をコピー:

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
gas/FlyerDeals.gs
```

カード/定期通知用 Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

チラシ用に `GEMINI_API_KEY` を追加します。

GitHubの`.gs`は通常GASへ自動同期されません。

---

# 9. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `runDailySummitFlyerAutomation` | 毎日6〜7時台 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

---

# 10. Phase 1カード自動化

`カードテスト`で本物の未処理がなくてもテスト可能です。

自動登録条件:

```text
同じジャンルへ3回以上手動分類
AND 一致率100%
AND 本人が自動登録ON
```

重複候補は本人確認を優先し、自動削除しません。

---

# 11. Postback制限

LINE Postback `data`は300文字以内。未処理カードでは店名・金額等を埋め込まず`pending_id`と最小限の値だけ送ります。

---

# 12. 導入確認

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

チラシ: `FLYER_TEST.md`

案内機能:

```text
？
おすすめ
何したい 旅行のために貯金したい
コマンド
```

---

# 13. トラブル時

Render系はRender Logsの最初のTracebackを確認してください。

チラシ自動化はApps Scriptの実行ログを確認します。

主な確認:
- `GEMINI_API_KEY`未設定 → Script Propertiesを確認
- カレンダーが見つからない → `FLYER_CALENDAR_ID`を確認、または一旦削除してデフォルトカレンダーを使用
- LINE通知失敗 → `LINE_USER_ID` / `LINE_CHANNEL_ACCESS_TOKEN`を確認
- チラシ0件 → `testSummitFlyerParse`を実行し、サイト側の配信形式変更を確認
- Geminiエラー → `FLYER_GEMINI_MODEL`を確認

詳細は`FLYER_TEST.md` / `MAINTENANCE.md`。

---

# 14. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。
