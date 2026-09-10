# LINE Notion Bot セットアップガイド

この文書は、LINE・Notion・Gemini・Gmail・Google Apps Script・Render を連携し、このBotをゼロから構築し、AIを使わなくても日常保守できるようにするための手順書です。

関連文書:

- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期開発ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UI・Postback設計ルール
- `gas/README.md`: GAS詳細

---

# 1. 全体構成

```text
LINE
↓
Render / Flask
├─ 家計簿・予算・メモ
├─ カード未処理キュー
├─ 固定費 / サブスク判定
├─ Notion API
└─ Gemini AI

カード会社メール
↓
Gmail
↓
Google Apps Script
↓
Render /api/card-pending
↓
固定費DB照合
├─ 一致あり → 検出除外・通知しない
└─ 一致なし → カード未処理DB → LINE通知
```

---

# 2. 必要サービス

- GitHub
- Render
- LINE Developers / Messaging API
- Notion
- Gmail
- Google Apps Script
- Google AI Studio / Gemini API

---

# 3. Notion Integration

1. NotionでIntegrationを作成する。
2. Internal Integration Secretを取得する。
3. Botが使うすべてのDBへIntegrationを接続する。
4. 書き込みが必要なDBでは更新権限も許可する。
5. Database IDをRender環境変数へ設定する。

---

# 4. Notion DB仕様

## 4.1 家計簿DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `日付` | Date |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `月別管理` | Relation |

ジャンルには `サブスク` を用意しておくことを推奨します。UI側でもサブスクを必ず表示します。

## 4.2 月別管理DB

| 名前 | 型 |
|---|---|
| `年月` | Title |
| `全体予算` | Number |
| `食費予算` など | Number |

## 4.3 固定費DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

環境変数:

```text
NOTION_FIXED_DATABASE_ID
```

カード未処理で `サブスク` を選ぶと、このDBへ保存されます。

同じ `カード・支払方法` と同じ正規化店名が既に有効レコードとして存在する場合は、新規ページを重複作成せず既存レコードを更新します。

`有効=true` の一致レコードは、次回以降のカード検出除外ルールとしても使います。

除外解除:

```text
固定費DBで該当レコードの「有効」をOFF
```

すると次回以降は再び通常のカード検出対象になります。

## 4.4 メモDB

| 名前 | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

## 4.5 URL保存DB

| 名前 | 型 |
|---|---|
| `URL` | Title |

## 4.6 AI改善ログDB

| 名前 | 型 |
|---|---|
| `質問` | Title |
| `AI回答` | Rich text |
| `期待する回答` | Rich text |
| `登録日時` | Date |

## 4.7 カード未処理DB

| 名前 | 型 |
|---|---|
| `GmailMessageID` | Title |
| `カード` | Rich text |
| `利用先` | Rich text |
| `金額` | Number |
| `利用日` | Date |
| `通知済み` | Checkbox |
| `登録日時` | Date |

環境変数:

```text
NOTION_CARD_PENDING_DATABASE_ID
```

タイトル列はコードで自動検出できますが、管理上は `GmailMessageID` を推奨します。

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
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
```

---

# 6. Google Apps Script

GitHubの最新版を同じApps Scriptプロジェクトへコピーします。

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

今回のサブスク除外機能はRender側で判定するため、GASへ新しいScript Propertyを追加する必要はありません。

---

# 7. GASトリガー

```text
checkCardEmails              → 1時間ごと
sendDailyCardPendingReminder → 毎日 20〜21時ごろ
sendDailyMemoReminder        → 毎日 朝8時ごろ
sendDailyBudgetAlert         → 毎日 20時ごろ
sendWeeklyFinanceReport      → 毎週日曜日 20時ごろ
```

---

# 8. カード未処理の操作

LINEで:

```text
カード未処理
```

表示するジャンルのルール:

```text
通常ジャンル → 表示
サブスク     → 必ず表示
固定費       → 表示しない
```

ジャンルは2列表示です。

`サブスク` を選んだ場合:

```text
固定費DBの既存一致を確認
↓
一致あり → 金額・ジャンル・有効状態を更新
一致なし → 固定費DBへ新規登録
↓
今回分を家計簿へ保存
↓
未処理キューからアーカイブ
↓
次の未処理を表示
```

固定費DBへの登録確認に失敗した場合は、安全のため家計簿保存も進めず未処理を残します。これにより除外ルールだけ中途半端に作られることを防ぎます。

---

# 9. 今後のカード検出除外

GASがカードメールを解析した後、Renderの `/api/card-pending` で固定費DBを照合します。

一致条件:

```text
カード名が一致
AND
正規化店名が一致
AND
固定費DBの有効=true
```

一致した場合:

```text
カード未処理DBへ入れない
LINE通知しない
GASでは処理済み扱いにする
```

金額は除外判定条件に使いません。サブスク料金が値上げしても、同じカード・同じ店なら除外できます。

既に未処理DBへ入っている過去分には遡って自動適用しません。

---

# 10. 2026年9月バックフィル

Apps Scriptで:

```text
backfillSeptember2026
```

を手動実行します。

既に固定費DBの有効レコードに一致するカード利用は、Render側で未処理キューへの追加対象から外れます。

---

# 11. LINE Postback 300文字対策

未処理カードのボタンには長い店名を埋め込まず、`pending_id` を中心に短いPostbackを使用します。

```text
ジャンル選択 → action + pending_id + cat
店名変更     → action + pending_id
登録しない   → action + pending_id
```

Render側でNotionから実データを再取得します。

---

# 12. 動作確認

Render再デプロイ後、サブスク候補の未処理カードで確認します。

```text
1. カード未処理 を送る
2. ジャンル一覧に「サブスク」がある
3. 「固定費」は出ていない
4. サブスクを押す
5. 固定費DBにレコードが作成または更新される
6. 今回分が家計簿DBへ保存される
7. 未処理から消えて次へ進む
```

次回同じカード + 同じ店のメールが来た場合:

```text
未処理DBへ入らない
LINE通知されない
```

除外解除テスト:

```text
固定費DBの有効をOFF
↓
次回は通常カード検出へ戻る
```

---

# 13. トラブル時

固定費/サブスク関連でおかしい場合は次を確認します。

1. `NOTION_FIXED_DATABASE_ID` が正しいか
2. 固定費DBのIntegration接続があるか
3. `内容・店名 / 金額 / ジャンル / カード・支払方法 / 有効` の型が正しいか
4. Render Logsに `固定費マスタ` または `固定費除外ルール` エラーがないか
5. 除外したいレコードが `有効=true` か
6. カード名が家計簿側と固定費DB側で同じ表記か

詳細は `MAINTENANCE.md` を参照してください。

---

# 14. 開発管理

長期開発の現在地は `DEVELOPMENT.md` を唯一の基準にします。

機能追加ごとに README.md / SETUP.md / DEVELOPMENT.md を更新し、UI変更時は UI_DESIGN.md も更新します。

---

# 15. セキュリティ

秘密値はGitHub、README、Issue、チャットへ貼らないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
```
