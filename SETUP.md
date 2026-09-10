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
├─ 家計簿重複照合
├─ 未処理同一取引照合
├─ 安全な自動登録
└─ カード未処理DB
     ↓
     LINEで分類
     ├─ おすすめジャンル
     ├─ 同じ店をまとめて分類
     ├─ 店名変更
     ├─ サブスク登録
     └─ 登録しない
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

Title列名は自動検出できますが、`GmailMessageID`を推奨します。

## カード学習ルールDB

Phase 1のおすすめジャンル・自動登録に必要です。新しくDBを1つ作成してください。

| 名前 | 型 | 用途 |
|---|---|---|
| `店名キー` | Title | 正規化した店名。コードが自動保存 |
| `表示名` | Rich text | 人が読む店名 |
| `ジャンル` | Select | 現在のおすすめジャンル |
| `学習回数` | Number | 手動分類した総回数 |
| `一致回数` | Number | 現在ジャンルへの連続/一致回数 |
| `自動登録` | Checkbox | ユーザーが明示ONした場合のみtrue |
| `最終更新` | Date | 最終学習日時 |

環境変数:

```text
NOTION_CARD_RULES_DATABASE_ID=<このDBのDatabase ID>
CARD_AUTO_REGISTER_MIN_MATCHES=3
```

`CARD_AUTO_REGISTER_MIN_MATCHES`は省略可能で、未設定時3です。

重要: `カード学習ルール` DBは`NOTION_DATABASE_IDS`へ重複登録する必要はありません。

## メモDB

| 名前 | 型 |
|---|---|
| `メモ` | Title |
| `日付` | Date |

環境変数: `NOTION_MEMO_DATABASE_ID`

## URL保存DB

| 名前 | 型 |
|---|---|
| `URL` | Title |

環境変数: `NOTION_URL_DATABASE_ID`

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

Phase 1で追加必須なのは`NOTION_CARD_RULES_DATABASE_ID`です。`CARD_AUTO_REGISTER_MIN_MATCHES`は通常3のままで問題ありません。

---

# 6. Google Apps Script

Apps ScriptへGitHub最新版をコピーします。

```text
gas/Code.gs
gas/FinanceReports.gs
gas/DailyMemo.gs
```

GitHubの`.gs`は自動同期されません。GitHubで変更した場合はApps Script側にもコピーしてください。

Script Properties:

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

---

# 7. GASトリガー

| 関数 | 推奨 |
|---|---|
| `checkCardEmails` | 1時間ごと |
| `sendDailyCardPendingReminder` | 毎日20〜21時 |
| `sendMonthEndCardCheck` | 毎日21時ごろ |
| `sendDailyMemoReminder` | 毎日朝8時 |
| `sendDailyBudgetAlert` | 毎日20時 |
| `sendWeeklyFinanceReport` | 毎週日曜20時 |

`sendMonthEndCardCheck`は毎日呼んでも、Render側が月末以外は何も通知しません。月末だけ未処理0件または残件数を通知します。

---

# 8. Phase 1の動作

## おすすめジャンル

カード未処理を手動分類すると、店名とジャンルがカード学習ルールDBへ保存されます。次回同じ正規化店名のカードを開くとおすすめが`★ジャンル`として先頭に出ます。

## 同じ店をまとめる

同じカード＋同じ正規化店名が複数未処理にある場合、`同じ店 N件をまとめる`ボタンが表示されます。押してジャンルを1つ選ぶと対象をまとめて処理します。

## 自動登録

次をすべて満たしたときだけONにできます。

```text
同じ店を同じジャンルに3回以上手動分類
一致率100%
ユーザーが自動登録ONを押す
```

管理画面:

```text
カード自動登録
```

OFFにも戻せます。

## 重複確認

家計簿保存前に以下を一致確認します。

```text
日付 + 金額 + カード + 正規化店名
```

一致した場合は自動保存せず、`それでも保存する`または`重複として処理済みにする`を選びます。

## 速報/確定の照合

Gmail Message IDが異なっても、同日・同額・同カード・同一正規化店名なら同一取引として照合します。未処理にすでにあれば新しい未処理を作らず、家計簿にすでにあれば再キューしません。

## サブスク

カードジャンルでは`固定費`を表示せず、`サブスク`を必ず表示します。サブスク選択後は固定費DBへ登録され、次回同じカード＋店の検出から除外されます。

---

# 9. 2026年9月バックフィル

Apps Scriptで一度だけ:

```text
backfillSeptember2026
```

既存の未処理・家計簿・固定費ルールとの照合がRender側で働くため、Phase 1導入後の再取り込みでも重複を抑止しやすくなっています。ただし実データに同日同額の正当な複数利用がある場合は重複確認画面で判断してください。

---

# 10. LINE Postback制限

Postback `data` は300文字以内です。未処理カードでは店名・金額などを埋め込まず、`pending_id`と最小限の選択値だけを送ります。

---

# 11. Phase 1導入後の確認

`PHASE1_TEST.md`を上から実施してください。最低限:

```text
1. Render最新デプロイ成功
2. カード学習ルールDB作成・Integration接続
3. NOTION_CARD_RULES_DATABASE_ID設定
4. gas/FinanceReports.gsをGASへコピー
5. sendMonthEndCardCheckトリガー追加
6. カード未処理で通常保存
7. おすすめ表示
8. 同じ店まとめ処理
9. 重複確認
10. 自動登録ON/OFF
```

---

# 12. トラブル時

最短確認:

1. Render最新デプロイが成功しているか
2. Render Logsの最初のTraceback行
3. `NOTION_CARD_RULES_DATABASE_ID`が設定されているか
4. カード学習ルールDBの7プロパティ名・型が完全一致しているか
5. Integrationが家計簿・固定費・カード未処理・カード学習ルールDBすべてに接続されているか
6. GASへ最新版`FinanceReports.gs`をコピーしたか
7. `SCHEDULER_SECRET`がRenderとGASで一致しているか

詳細は`MAINTENANCE.md`を参照してください。

---

# 13. セキュリティ

次の秘密値をGitHub、README、Issue、チャットへ貼らないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
```
