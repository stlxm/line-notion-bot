# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `PHASE2_TEST.md`: Phase 2実機テスト
- `gas/README.md`: GAS詳細

---

# 1. 必要サービス

GitHub / Render / LINE Developers / Notion / Gmail / Google Apps Script / Google AI Studio

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

新規DBを作成します。

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

このDBが未設定でも、Phase 2A・2Bと年間予測は利用できます。使えないのは貯金目標だけです。

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

# 5. Phase 2

Phase 2は3ブロックに分けて導入・確認します。

## Phase 2A — 日々の家計判断

追加DB不要。

```text
今日使える
ペース
異常支出
```

- `今日使える`: 残り予算÷残り日数
- `ペース`: 月経過率と予算消化率を比較
- `異常支出`: 過去約4か月の中央値から外れた候補を表示

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

月締めは終了済みの月だけ実行できます。今月・未来月は不可です。

通常の`月締め確定`はカード未処理があると停止します。未処理を確認済みで意図的に締める場合だけ`月締め確定強制`を使います。

プレビューだけではNotionを書き換えません。

`予算提案`は過去3か月平均+約5%の余裕を表示するだけで、自動で予算を書き換えません。

## Phase 2C — 将来予測・目標

```text
年間予測
年間予測 2026
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

貯金目標だけ専用DBが必要です。

一覧:

```text
家計判断
```

でPhase 2のコマンド一覧を確認できます。

---

# 6. GAS

Apps Scriptへ最新版をコピー:

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
```

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

GitHubの`.gs`は通常GASへ自動同期されません。

Phase 2では新しいGASファイル・トリガーはありません。

---

# 7. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

---

# 8. Phase 1カード自動化

`カードテスト`で本物の未処理がなくてもテスト可能です。通常の未処理キュー・家計簿保存・カード学習を通るため、保存したテスト行はNotionへ実際に残ります。

自動登録条件:

```text
同じジャンルへ3回以上手動分類
AND 一致率100%
AND 本人が自動登録ON
```

重複候補は本人確認を優先し、自動削除しません。

---

# 9. Postback制限

LINE Postback `data`は300文字以内。未処理カードでは店名・金額等を埋め込まず`pending_id`と最小限の値だけ送ります。

---

# 10. 導入確認

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

Phase 2は2A → 2B → 2Cの順で確認します。

最低確認:

```text
2A: 今月の全体予算を設定
2B: 月別管理DBへ 締め済み / 締め日時 / 確定支出 を追加
2C: 貯金目標を使うならDB作成 + NOTION_SAVINGS_GOALS_DATABASE_ID
Renderを最新mainで再デプロイ
```

---

# 11. トラブル時

Render Logsの最初のTracebackを確認してください。

Phase 2で多い設定ミス:
- 月締め失敗 → 月別管理DBの3プロパティ名・型を確認
- 月締め停止 → カード未処理件数を確認
- 貯金目標が未設定表示 → `NOTION_SAVINGS_GOALS_DATABASE_ID`を確認
- 貯金目標登録失敗 → Integrationが貯金目標DBへ接続されているか確認
- 月次レビュー失敗 → `GEMINI_API_KEY`と`AI Model`を確認
- 今日使える/ペースで予算未設定 → 月別管理DBの`全体予算`を設定

詳細は`MAINTENANCE.md`。

---

# 12. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。
