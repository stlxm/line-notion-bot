# LINE Notion Bot セットアップガイド

この文書はLINE・Notion・Gemini・Gmail・Google Apps Script・Renderを連携し、このBotを構築・保守するための手順書です。

関連文書:
- `README.md`: 現在利用できる機能
- `MAINTENANCE.md`: 障害切り分け、復旧、日常保守
- `DEVELOPMENT.md`: 長期ロードマップと進捗
- `UI_DESIGN.md`: LINE UI・Postback設計
- `PHASE1_TEST.md`, `PHASE2_TEST.md`, `PHASE3_TEST.md`, `PHASE5_TEST.md`, `FLYER_TEST.md`
- `gas/README.md`: GAS詳細

---

# 1. 主要Notion DB

```text
メモDB: 3d60efb323d08089b369df4e332d7e36
後で見るURL DB: 3d40efb323d0806b927ce286e442add6
AI改善ログ DB: 3d70efb323d0806faa10ed0ec36351cb
貸し借り管理DB: f9b2c4eb59ea4c13b968f8d9b48663bc
機能追加要望DB: 76e4fe5d248e4fd1a48f45e9bdd59e8c
生活カレンダーDB: 684f959e451047389505a95ed368a7d6
チラシ一覧DB: fdd0c0ce50974273b9b88f5272858e90
```

Phase 4でメモDBへ追加済み:

```text
期限 Date
分類 Select: 買い物 / やること / 予定 / アイデア / その他
完了 Checkbox
```

後で見るURL DBへ追加済み:

```text
ページタイトル Rich text
カテゴリ Select: 記事 / 買い物 / 動画 / SNS / 資料 / その他
ドメイン Rich text
保存日時 Date
```

AI改善ログ DBへ追加済み:

```text
評価 Select: 👍 / 👎 / 改善
参照DB Rich text
根拠 Rich text
```

---

# 2. Render環境変数

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
NOTION_LOAN_DATABASE_ID
NOTION_FEATURE_REQUEST_DATABASE_ID
NOTION_FLYER_DATABASE_ID
NOTION_DATABASE_IDS
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

特売:

```text
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
```

旧 `3d90efb323d080b5999bed1820a6665e` は削除済みDBなので使用しません。

GitHub更新後はRenderを最新版へ再デプロイしてください。

---

# 3. メニュー仕様

`メニュー` は開発フェーズ名ではなく、機能単位で表示します。

```text
案内・入口
家計簿・入力
予算・分析
月次・固定費・貯金
修正・取り消し
カード
貸し借り
メモ・買い物
特売・あとで見る
AI
Notion・データ
```

`Phase4` / `Phase5` のような開発用ラベルはメニューに表示しません。

メニューはFlex carouselなので横スワイプしてカテゴリを移動します。

---

# 4. 未認識コマンド

未認識入力で毎回メニューFlexを自動表示しない設計です。

```text
「ヘルプ」か「メニュー」と送ってください。
```

必要なときだけユーザーがメニューを開きます。

---

# 5. `コマンド` 一覧

`コマンド` と送ると、実装済みコマンドをカテゴリ別にまとめて表示します。

対象:

```text
案内
家計簿入力・確認
予算・分析
月次
固定費
貯金目標
修正・取り消し
貸し借り
カード
メモ・買い物
特売・URL
AI
Notion
```

新しいコマンドを追加した場合は、`help_guide.py` の `command_list_text()` にも追加します。

---

# 6. Phase 4

```text
メモ 住民票を明日までに提出
メモ レポートを金曜までに出す
メモ一覧
買い物 牛乳
買い物リスト
買った 牛乳
https://example.com/
```

メモ期限は、今日 / 明日 / 明後日 / N日後 / 曜日 / 今週中 / 来週中 / 今月末 / 来月末 / 9月20日 / YYYY-MM-DD などを認識します。期限が書かれていなければ自動推測しません。

URL取得先がJavaScript必須・ログイン必須・Bot拒否の場合、タイトルを取得できないことがあります。その場合でもURL本体は保存します。

---

# 7. Phase 5

```text
AI 今月の食費を分析して
AI評価 👍
AI評価 👎
AI改善
DBヘルスチェック
```

AI回答の後ろに `【参照DB】` と `【根拠】` を付け、さらに `👍 良い / 👎 改善したい` の評価ボタンを表示します。

---

# 8. 貸し借り

```text
貸した
貸した 田中 3000 ランチ代
借りた
借りた 田中 2000
貸し借り一覧
精算
精算 田中 3000
```

単独コマンドは入力形式の案内用です。

---

# 9. GAS Script Properties

```text
LINE_USER_ID
LINE_CHANNEL_ACCESS_TOKEN
RENDER_BASE_URL
SCHEDULER_SECRET
GEMINI_API_KEY
NOTION_API_KEY
NOTION_FLYER_DATABASE_ID=684f959e451047389505a95ed368a7d6
NOTION_FLYER_LIST_DATABASE_ID=fdd0c0ce50974273b9b88f5272858e90
```

任意:

```text
FLYER_GEMINI_MODEL=gemini-3.5-flash-lite
```

## サミットチラシの自動反映モード

Notionで `確認待ち → 確認済み` に手動変更する運用は廃止しています。

Apps Scriptへ次の3ファイルを配置してください。

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
gas/FlyerAutoMode.gs
```

`FlyerAutoMode.gs` は既存の取得・解析処理を利用し、解析成功後に自動で `確認済み / 有効=true` へ反映します。旧仕様で確認待ちのまま残った掲載中データも自動有効化します。

旧日次トリガーから切り替えるため、1回だけ実行:

```text
installDailySummitLifeCalendarAutoTrigger
```

この関数は旧チラシ日次トリガーを削除し、次を毎日6時台に登録します。

```text
runDailySummitLifeCalendarAutoAutomation
```

軽量確認:

```text
testSummitLifeCalendarAutoMode
```

このテストはGemini再解析をせず、現在のNotionデータの自動有効化と今日の通知だけを確認します。

---

# 10. AIモデル

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

---

# 11. 現在の開発順

```text
Phase 4 — 主要実装済み・要実機確認
Phase 5 — 主要実装済み・要実機確認
Phase 3C — 次
Phase 6
Phase 7
```

---

# 12. セキュリティ

秘密値をGitHub、README、Issue、チャットへ貼らないでください。

Channel Access Tokenをチャットやコードへ貼り付けた場合は、そのトークンを再発行し、RenderとGAS Script Propertiesの両方を新しい値へ更新してください。
