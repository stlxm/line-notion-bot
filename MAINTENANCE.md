# MAINTENANCE.md

この文書は、AIを使わなくてもLINE Notion Botを自分で保守・復旧できるようにするための運用手順書です。

## 1. まず確認する場所

不具合が起きたら、次の順で確認します。

1. LINEでBotが返信するか
2. Renderの最新デプロイが成功しているか
3. Render LogsにPython例外が出ていないか
4. GASの実行履歴にエラーがないか
5. Notion Integrationが対象DBへ接続されているか
6. Render EnvironmentとGAS Script Propertiesの名前・値が一致しているか

## 2. ファイルの役割

- `app.py`: LINE Webhook、コマンド、Render API
- `menu.py`: メニュー
- `ui.py`: 共通Flex Message
- `kakeibo.py`: 家計簿、予算、固定費
- `card_queue.py`: カード未処理キュー
- `card_rules.py`: 開発中のカード店名正規化・ジャンル学習エンジン。現時点ではLINEフロー未接続
- `budget.py`: 月次予算集計
- `insights.py`: ダッシュボード、アラート、週次レポート
- `memo.py`: メモ
- `notion_helper.py`: 汎用Notion操作、AI用DB選択
- `ai_engine.py`: AI最終回答
- `ai_feedback.py`: AI改善ログ
- `gas/Code.gs`: Gmailカード通知
- `gas/FinanceReports.gs`: 家計簿系定期通知
- `gas/DailyMemo.gs`: メモ定期通知
- `README.md`: 現在の機能
- `SETUP.md`: 構築方法
- `DEVELOPMENT.md`: 開発進捗と次回再開位置
- `UI_DESIGN.md`: UIルール

重要: `card_rules.py` はPhase 1の基盤だけ先に作成済みですが、まだ `app.py` から呼ばれていません。`DEVELOPMENT.md` で「接続済み」になるまでは、カード学習DBを作らなくても現在のBot機能には影響しません。

## 3. Renderで確認する環境変数

秘密値そのものをREADMEやGitHubへ書かないでください。

LINE:

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
```

Notion:

```text
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
```

Gemini:

```text
GEMINI_API_KEY
GEMINI_MODEL
```

定期API:

```text
SCHEDULER_SECRET
```

Phase 1接続後に追加予定:

```text
NOTION_CARD_RULES_DATABASE_ID
CARD_AUTO_REGISTER_MIN_MATCHES
```

現時点では未接続なので必須ではありません。

## 4. GAS Script Properties

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
```

`SCHEDULER_SECRET` はRenderとGASで完全一致させます。

## 5. よくあるHTTPエラー

### Render 401

原因候補:

- GASの `SCHEDULER_SECRET` とRenderが違う
- ヘッダー `X-API-KEY` が送られていない

### Render 500 + Notion validation_error

例:

```text
"金額 is not a property that exists"
```

原因:

- Notionのプロパティ名違い
- Database IDが別DBを指している

対処:

1. Renderで対象の `NOTION_*_DATABASE_ID` を確認
2. Notion DBの列名をSETUP.mdと比較
3. 列の型も確認

### Notion 401 / unauthorized

- `NOTION_API_KEY` を確認
- IntegrationがDBへ接続されているか確認

### Notion 404

- Database ID / Page IDが間違っている
- Integrationから対象が見えない

### Gemini 429

レート / クォータ制限です。連続再実行を避けます。

### Gemini 503 / 504

一時的な混雑やタイムアウトの可能性があります。現在のコードは一部リトライします。

## 6. カード通知が来ない

GASの `checkCardEmails` を手動実行し、実行ログを確認します。

正常系:

```text
[解析成功] ...
[Render] /api/card-pending: 200 ...
LINEレスポンス: 200
```

確認項目:

- 対象メールの差出人 / 件名が変わっていないか
- `RENDER_BASE_URL` が正しいか
- Renderが起動しているか
- `NOTION_CARD_PENDING_DATABASE_ID` が正しいか
- カード未処理DBにIntegrationが接続されているか

## 7. カード未処理がおかしい

未処理DBの推奨プロパティ:

```text
GmailMessageID  Title
カード           Rich text
利用先           Rich text
金額             Number
利用日           Date
通知済み         Checkbox
登録日時         Date
```

タイトル列名はコードが自動検出できますが、管理上 `GmailMessageID` を推奨します。

保存 / 登録しない後はアーカイブされます。Notion APIでは完全削除ではありません。

## 8. 9月分を再取り込みする場合

GASから:

```text
backfillSeptember2026
```

を手動実行します。

同じGmail Message IDは再取り込み抑止されます。途中までジャンル処理済みでも、残った未処理だけ続けて処理できます。

## 9. GASコードを更新したのに変わらない

GitHubの `gas/*.gs` はApps Scriptへ自動同期されません。

GitHubを更新したら、Apps Script側へ最新コードをコピーしてください。将来 `clasp` を導入した場合はこの手順を変更します。

## 10. LINEメニューが壊れた

Flex Messageのよくある原因:

- labelが長すぎる
- 1メッセージのJSONが大きすぎる
- postback dataが長すぎる
- `contents` の構造がLINE Flex仕様に合っていない

UIを変更するときは `UI_DESIGN.md` のルールを優先します。

## 11. 安全な修正手順

1. 変更前に現在のGitHub `main` を確認
2. `DEVELOPMENT.md` の再開位置を確認
3. 1つの目的ごとに修正
4. Renderデプロイログを確認
5. LINEで該当機能を1回テスト
6. GAS変更時はApps Scriptへコピー
7. README / SETUP / DEVELOPMENTを更新
8. UI変更時はUI_DESIGNも更新

## 12. 復旧の考え方

コード変更後に重大な不具合が出た場合は、GitHubの直前の正常コミットを確認し、変更差分を戻します。秘密値はGitHubに入っていないため、通常はRender EnvironmentやGAS Script Propertiesを触らずコードだけ戻せます。

## 13. セキュリティ

以下をチャット・README・GitHub Issue・ソースへ貼らないでください。

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
NOTION_API_KEY
GEMINI_API_KEY
SCHEDULER_SECRET
```

漏えいしたアクセストークンは再発行し、RenderとGASの両方を更新します。

## 14. 開発を再開するとき

必ず `DEVELOPMENT.md` の「次に再開する場所」を読みます。

完了したら:

- 状態を更新
- 次の再開位置を更新
- README.mdを現在仕様に更新
- SETUP.mdに新しいDB / 環境変数 / トリガーがあれば追記

これを守れば、長期間空いても再開できます。
