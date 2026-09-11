# LINE Notion Bot

LINEを入口に、家計簿・予算・カード利用通知・固定費/サブスク・メモ・Notion・Gemini AIをまとめて扱う個人向けBotです。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: 日常保守、障害切り分け、復旧
- `DEVELOPMENT.md`: 長期ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIとPostback設計ルール
- `PHASE1_TEST.md`: カード自動化テスト
- `PHASE2_TEST.md`: 月次・予算判断テスト
- `gas/README.md`: GAS固有設定

機能変更時はREADME.md / SETUP.md / DEVELOPMENT.mdを更新し、UI変更時はUI_DESIGN.mdも更新します。

---

# 主なLINEコマンド

```text
メニュー
支出 1200 ラーメン
今月
今日使える
ペース
予算提案
異常支出
年間予測
月締め
月次レビュー
貯金目標
予算一覧
週次レポート
固定費一覧
カード未処理
カードテスト
カード自動登録
メモ 牛乳を買う
メモ一覧
AI 今月の食費を分析して
AI Lite
AI Flash
AI Model
AI改善
```

---

# Phase 2 — 月次・予算判断

状態: **実装済み・要実機確認**

## 1日あたり使える額

```text
今日使える
```

今月の残り予算 ÷ 残り日数を表示します。予算未設定なら設定を案内します。

## 使いすぎペース

```text
ペース
```

月の経過率と予算消化率を比較し、現在ペースの月末支出予測を表示します。

## 予算提案

```text
予算提案
```

過去3か月の支出平均に約5%の余裕を加え、全体予算とジャンル別予算の目安を提案します。自動では書き換えません。

## 異常支出

```text
異常支出
```

過去約4か月の支出中央値と比較し、今月の大きく外れた支出候補を表示します。誤登録とは断定せず候補として扱います。

## 年間予測

```text
年間予測
年間予測 2026
```

今年の現在ペースから年間支出を予測します。過去年は実績を表示します。

## 月締め

```text
月締め
月締め 2026-08
```

引数なしなら前月をプレビューします。支出・件数・予算差額・上位ジャンルを確認した後、

```text
月締め確定 2026-08
```

で確定します。月別管理DBへ`締め済み`、`締め日時`、`確定支出`を記録します。カード未処理が残っている場合は警告します。

## 月次AIレビュー

```text
月次レビュー
月次レビュー 2026-08
```

対象月の家計簿集計だけを根拠に、選択中のGeminiモデルでレビューを生成します。`AI Lite / AI Flash` の設定をそのまま使います。

## 貯金目標

```text
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

目標額・現在額・期限を管理し、期限がある場合は月あたり必要額の目安も表示します。

---

# AIモデル切替

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLiteです。Render再起動・再デプロイ後もLiteへ戻ります。

---

# Phase 1 — カード自動化

カード会社メールをGASで検出し、未処理キューへ保存してLINEから分類できます。

主な機能:
- 過去分類からおすすめジャンル表示
- 同じ店の一括分類
- 条件を満たした店の安全な自動登録
- 家計簿DBとの重複確認
- 店名変更
- サブスクを固定費DBへ登録し次回以降検出除外
- 月末未処理チェック
- `カードテスト`によるテスト用未処理作成

自動登録条件:

```text
同じ店を同じジャンルへ3回以上手動分類
AND 一致率100%
AND 本人が自動登録ON
```

重複候補は勝手に削除せず、`それでも保存する / 重複として処理済みにする`で本人確認します。

---

# Phase 2で追加するNotion設定

月別管理DBへ:

| 名前 | 型 |
|---|---|
| `締め済み` | Checkbox |
| `締め日時` | Date |
| `確定支出` | Number |

貯金目標DB:

| 名前 | 型 |
|---|---|
| `目標名` | Title |
| `目標額` | Number |
| `現在額` | Number |
| `期限` | Date |
| `有効` | Checkbox |

Render環境変数:

```text
NOTION_SAVINGS_GOALS_DATABASE_ID
```

詳細は`SETUP.md`を参照してください。

---

# Phase 1関連Notion DB

カード未処理DB:
`GmailMessageID`(Title) / `カード`(Rich text) / `利用先`(Rich text) / `金額`(Number) / `利用日`(Date) / `通知済み`(Checkbox) / `登録日時`(Date)

カード学習ルールDB:
`店名キー`(Title) / `表示名`(Rich text) / `ジャンル`(Select) / `学習回数`(Number) / `一致回数`(Number) / `自動登録`(Checkbox) / `最終更新`(Date)

---

# GAS推奨トリガー

```text
checkCardEmails              → 1時間ごと
sendDailyMemoReminder        → 毎日 朝8時ごろ
sendDailyBudgetAlert         → 毎日 20時ごろ
sendDailyCardPendingReminder → 毎日 20〜21時ごろ
sendMonthEndCardCheck        → 毎日 21時ごろ
sendWeeklyFinanceReport      → 毎週日曜 20時ごろ
```

Phase 2では新しいGASトリガーは不要です。

# 保守

Phase 1は`PHASE1_TEST.md`、Phase 2は`PHASE2_TEST.md`、障害対応は`MAINTENANCE.md`を参照してください。

Phase 3はまだ開始していません。
