# GAS カード利用通知セットアップ

`gas/Code.gs` は Gmail のカード利用通知を検出し、Render 経由で Notion の「カード未処理キュー」へ保存したうえで、LINE にカード利用通知を Push します。

現在の基本フローは次の通りです。

```text
カード会社メール
  ↓
Gmail
  ↓
Google Apps Script / checkCardEmails
  ↓
Render /api/card-pending
  ↓
Notion カード未処理DBへ一時保存
  ↓
LINEへカード利用通知
  ↓
ユーザーがジャンルを選択
  ↓
Notion 家計簿DBへ保存
  ↓
カード未処理DBの該当ページをアーカイブ
  ↓
次の未処理カードを自動表示
```

未処理DBは履歴DBではなく、一時的なキューとして利用します。家計簿への保存が成功したカード、または「登録しない」を選んだカードはアーカイブされ、通常の未処理DB表示から消えます。

---

## 1. 必要な Script Properties

Apps Script の「プロジェクトの設定」→「スクリプト プロパティ」で次を設定してください。

| プロパティ | 内容 |
|---|---|
| `LINE_USER_ID` | 通知先の LINE User ID |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API の Channel Access Token |
| `RENDER_BASE_URL` | Render の URL。例 `https://xxxx.onrender.com` |
| `SCHEDULER_SECRET` | Render 側の `SCHEDULER_SECRET` と同じ値 |

秘密情報は `Code.gs` に直接書かないでください。

LINE Channel Access Token を過去にチャットや公開コードへ貼り付けたことがある場合は、LINE Developers で再発行し、Render と GAS の両方を新しい値へ更新してください。

---

## 2. 通常カード監視

実行関数:

```text
checkCardEmails
```

推奨トリガー:

```text
時間主導型
1時間おき
```

コードは Gmail 検索自体を少し広めに行い、各メッセージの受信日時を JavaScript で再判定します。

現在の実処理対象:

```text
直近2時間
```

1時間トリガーに対して2時間の重なりを持たせることで、Apps Script の実行時刻が多少ずれても取りこぼしにくくしています。

重複通知は Gmail Message ID を Script Properties に保持して抑止します。

---

## 3. 対応カード

現在の `Code.gs` は次を対象にしています。

- JCB
- 三井住友カード
- 楽天カード
- PayPayカード

カード会社によってメール受信日と実利用日が異なる場合があるため、本文に利用日が含まれる場合は本文の日付を優先します。

特に楽天カードは利用メールが後日届く場合があるため、メール受信日時をそのまま支出日にはしません。

---

## 4. カード利用通知後の操作

新しいカードメールを検知すると、まず未処理DBへ保存してから LINE 通知します。

LINE の通知には次の操作があります。

- `ジャンルを選ぶ` : 緑
- `店名を変更する` : 緑
- `登録しない` : 色なし / secondary

ジャンル選択肢も通常操作なので緑で表示します。

ジャンルを1件保存すると、その未処理ページはアーカイブされ、まだ未処理カードがあれば次の1件を自動表示します。

```text
未処理A
  ↓ ジャンル保存
Aを家計簿へ保存 + キューからアーカイブ
  ↓
未処理Bを自動表示
  ↓ ジャンル保存
Bを家計簿へ保存 + キューからアーカイブ
  ↓
...
```

`登録しない` を選んだ場合も、その項目はキューからアーカイブされて次へ進みます。家計簿DBには保存されません。

---

## 5. 未処理カードを後から処理する

LINE で次を送信します。

```text
カード未処理
```

現在残っている件数を表示し、最も古い未処理カードからジャンル選択を開始します。

メインメニューにも「カード未処理を確認」ボタンがあります。

---

## 6. 1日1回の未処理件数通知

`gas/FinanceReports.gs` に次の関数があります。

```text
sendDailyCardPendingReminder
```

Apps Script のトリガーで1日1回実行してください。

例:

```text
毎日 20時〜21時ごろ
```

未処理が0件なら LINE 通知は送りません。

未処理がある場合のみ、例えば次のように通知します。

```text
💳 ジャンル未選択のカード利用が 5 件あります。
「カード未処理」と送ると、1件ずつ続けて処理できます。
```

---

## 7. 2026年9月のカード履歴をまとめて取り込む

`Code.gs` に専用関数を用意しています。

```text
backfillSeptember2026
```

Apps Script エディタ上部の関数選択から `backfillSeptember2026` を選び、手動で実行してください。

処理内容:

1. 2026年9月の利用メール候補を Gmail から広めに検索
2. メール本文から実利用日を解析
3. 実利用日が `2026-09` のものだけ採用
4. 1件ずつ未処理DBへ保存
5. 過去取り込みでは1件ごとのLINE通知は送らない
6. 最後に「新しく何件追加したか」だけLINE通知
7. `カード未処理` から古いもの順にジャンルを登録

大量の過去通知が一気にLINEへ流れないようにしています。

### 注意

2026年9月10日時点で実行した場合、当然ながら9月11日〜30日の未来の利用メールはまだ存在しません。そのため今実行すると「9月1日〜現在までに届いていて、利用日が9月のもの」が主な対象になります。

9月を本当に丸ごと取り込みたい場合は、9月終了後にもう一度実行してください。楽天カードなど遅れて届く通知も考慮するなら、10月上旬にも再実行するのが安全です。

同じバックフィル処理を再実行したときの重複を抑えるため、バックフィル済み Gmail Message ID も Script Properties に保存します。

### 既に手動登録済みの支出がある場合

過去のカード通知から既に家計簿へ手動登録した支出がある場合は、バックフィル後の未処理一覧で同じ支出をもう一度保存しないよう注意してください。不要なものは `登録しない` でキューから外せます。

---

## 8. 任意の月を取り込む

汎用関数もあります。

```javascript
backfillCardEmailsForMonth(2026, 8)
```

のように Apps Script エディタから一時的なラッパー関数を作るか、コード上で対象年・月を指定して利用できます。

2026年9月については既に `backfillSeptember2026()` を用意しているため、そちらを使ってください。

---

## 9. 必要な Render 側設定

カード未処理キューを使うには Render に次を追加します。

```text
NOTION_CARD_PENDING_DATABASE_ID
```

値は Notion のカード未処理DBの Database ID です。

また、GAS と Render の通信には次を使用します。

```text
SCHEDULER_SECRET
```

GAS の Script Property と Render Environment で同じ値にしてください。

---

## 10. トラブルシューティング

### LINE通知が来ない

確認:

- `checkCardEmails` の実行ログ
- `LINE_USER_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `RENDER_BASE_URL`
- `SCHEDULER_SECRET`
- Render が起動しているか
- `NOTION_CARD_PENDING_DATABASE_ID` が正しいか
- Notion Integration が未処理DBへ接続されているか

### Render が401を返す

`SCHEDULER_SECRET` が Render と GAS で一致していません。

### 未処理DBへの保存に失敗する

DBのプロパティ名と型を確認してください。必要な構成は SETUP.md に記載しています。

### 同じカード通知が何度も来る

Script Properties の `PROCESSED_CARD_MESSAGE_IDS` を不用意に削除しないでください。

---

## 11. GAS と GitHub の同期について

GitHub の `gas/Code.gs` や `gas/FinanceReports.gs` を更新しても、通常のスタンドアロン Apps Script プロジェクトへ自動反映はされません。

GitHub 側で変更した後は、最新コードを Apps Script プロジェクトへコピーしてください。`clasp` 等の同期環境を別途構築している場合を除きます。
