# LINE Notion Bot セットアップガイド

この文書は、LINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotをゼロから構築し、AIなしでも保守できるようにするための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期開発ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`: Phase 1実機テスト
- `gas/README.md`: GAS詳細

---

# 1. 全体構成

```text
カード会社メール
↓
Gmail
↓
GAS checkCardEmails
↓
Render /api/card-pending
├─ 固定費/サブスク除外
├─ 安全な自動登録判定
└─ カード未処理DB
     ↓
     LINEで分類
     ├─ おすすめジャンル
     ├─ 同じ店をまとめて分類
     ├─ 重複候補確認
     ├─ 店名変更
     ├─ サブスク登録
     └─ 登録しない
```

---

# 2. 必要サービス

GitHub / Render / LINE Developers / Notion / Gmail / Google Apps Script / Google AI Studio

---

# 3. Notion Integration

Botが使うすべてのDBへ同じIntegrationを接続し、読み取り・作成・更新を許可します。DBを作り直した場合はDatabase IDも変わるため、Render環境変数を更新してください。

---

# 4. Notion DB仕様

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

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算`など | Number |

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

カード未処理で`サブスク`を選ぶとこのDBへ登録/更新されます。`有効=true`の同一カード＋同一正規化店名は、次回以降カード検出から除外されます。解除は`有効`をOFFにします。

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

Title列名は自動検出できますが`GmailMessageID`推奨です。

## カード学習ルールDB

Phase 1のおすすめジャンル・自動登録に必要です。

| 名前 | 型 | 用途 |
|---|---|---|
| `店名キー` | Title | 正規化店名 |
| `表示名` | Rich text | 表示用店名 |
| `ジャンル` | Select | 推奨ジャンル |
| `学習回数` | Number | 手動分類回数 |
| `一致回数` | Number | 現ジャンル一致回数 |
| `自動登録` | Checkbox | 本人が明示ONした場合のみtrue |
| `最終更新` | Date | 最終学習日時 |

Render:

```text
NOTION_CARD_RULES_DATABASE_ID=<Database ID>
CARD_AUTO_REGISTER_MIN_MATCHES=3
```

`CARD_AUTO_REGISTER_MIN_MATCHES`は省略可能で、未設定時3です。カード学習ルールDBを`NOTION_DATABASE_IDS`へ重複登録する必要はありません。

## メモDB

`メモ` Title / `日付` Date。環境変数: `NOTION_MEMO_DATABASE_ID`

## URL保存DB

`URL` Title。環境変数: `NOTION_URL_DATABASE_ID`

## AI改善ログDB

| 名前 | 型 |
|---|---|
| `質問` | Title |
| `AI回答` | Rich text |
| `期待する回答` | Rich text |
| `登録日時` | Date |

環境変数: `NOTION_AI_FEEDBACK_DATABASE_ID`

---

# 5. Render環境変数

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
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

`GEMINI_MODEL` は互換用に残していますが、LINEのAI検索はコード上でLiteから開始します。Renderの`GEMINI_MODEL`が以前の`gemini-3.6-flash`のままでも、LINE AIの初期選択はLiteです。

---

# 6. Gemini AIモデル切替

LINE AIの初期モデル:

```text
gemini-3.5-flash-lite
```

LINEコマンド:

```text
AI Lite   → gemini-3.5-flash-lite へ切替
AI Flash  → gemini-3.6-flash へ切替
AI Model  → 現在の選択を確認
AI 質問   → 選択中モデルで回答
```

モデル選択はRenderプロセスのメモリに保持されます。Renderの再起動・再デプロイ後は`gemini-3.5-flash-lite`へ戻ります。

Google側でモデルIDが変更・廃止された場合は`ai_engine.py`の`LITE_MODEL` / `FLASH_MODEL`と、このSETUP.mdを同時更新してください。

---

# 7. GAS

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

---

# 8. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時 |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

`sendMonthEndCardCheck`は毎日実行しても、Render側が月末以外は通知しません。

---

# 9. Phase 1カード自動化

## テスト用カード

本物のカード未処理が0件でも、LINEから次を送るとテストできます。

```text
カードテスト
```

管理者だけが利用できます。1回送るたびに`Phase1テストショップ`のテスト用未処理カードを1件作成し、通常のジャンル選択画面を表示します。

テスト用カードはGmailやカード会社メールを使いません。通常の未処理キュー・家計簿保存・カード学習をそのまま通します。

注意:
- ジャンルを保存すると家計簿DBへ実際にテスト行が追加されます。
- 学習ルールDBにも`Phase1テストショップ`が保存されます。
- 保存したくない場合は`登録しない`を選びます。
- テスト後に不要ならNotion側でテスト行を削除/アーカイブしてください。

## 学習・おすすめ

カード未処理を手動分類するとカード学習ルールDBへ保存され、次回同じ正規化店名で`★ジャンル`が先頭表示されます。

## 同じ店まとめ処理

同じカード＋同じ正規化店名が複数未処理なら`同じ店 N件をまとめる`が表示されます。保存成功分だけキューから消え、重複候補・保存失敗は未処理に残ります。

## 自動登録

```text
同じジャンルへ3回以上手動分類
AND 一致率100%
AND 本人が自動登録ON
```

管理コマンド:

```text
カード自動登録
```

自動登録結果は学習回数を増やしません。家計簿に重複候補がある場合は自動処理せず通常確認へ回します。

## 重複候補 / 速報・確定候補

保存時に以下を家計簿DBと比較します。

```text
日付 + 金額 + カード + 正規化店名
```

一致したら本人確認:

```text
それでも保存する
重複として処理済みにする
```

別Gmail Message IDの同日同額取引を自動削除・自動統合しません。正当な複数利用を失わないためです。速報/確定らしい取引も候補として確認し、曖昧な場合は本人判断を優先します。

## サブスク

カードジャンルでは`固定費`非表示、`サブスク`必須表示。サブスク選択後は固定費DBへ登録され、次回同じカード＋同じ店をカード検出から除外します。

---

# 10. 2026年9月バックフィル

GASで:

```text
backfillSeptember2026
```

を手動実行します。途中まで処理済みなら残りから続行できます。

---

# 11. Postback制限

LINE Postback `data`は300文字以内。未処理カードでは店名・金額等を埋め込まず`pending_id`と最小限の値だけ送ります。

---

# 12. 導入確認

`PHASE1_TEST.md`を上から実行してください。

本物の未処理がない場合は、最初にLINEで`カードテスト`を送ればテスト用未処理を作れます。

---

# 13. トラブル時

1. Render最新デプロイ成功を確認。
2. Render Logsの最初のTracebackを確認。
3. `NOTION_CARD_RULES_DATABASE_ID`を確認。
4. カード学習ルールDBの7プロパティ名・型を確認。
5. Integrationが家計簿・固定費・カード未処理・カード学習ルールDBに接続されているか確認。
6. 最新`FinanceReports.gs`をGASへコピーしたか確認。
7. `SCHEDULER_SECRET`がGAS/Renderで一致しているか確認。

AI関連の確認:
- `AI Lite`送信後に`gemini-3.5-flash-lite`と表示されるか
- `AI Flash`送信後に`gemini-3.6-flash`と表示されるか
- 切替後の`AI 質問内容`が正常に回答されるか

詳細は`MAINTENANCE.md`。

---

# 14. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。
