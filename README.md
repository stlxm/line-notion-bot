# LINE Notion Bot

LINEを入口に、家計簿・予算・カード利用通知・固定費/サブスク・メモ・Notion・Gemini AIをまとめて扱う個人向けBotです。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: 日常保守、障害切り分け、復旧
- `DEVELOPMENT.md`: 長期ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIとPostback設計ルール
- `PHASE1_TEST.md`: カード自動化テスト
- `PHASE2_TEST.md`: 月次・予算判断テスト
- `FLYER_TEST.md`: サミットチラシ自動化テスト
- `gas/README.md`: GAS固有設定

機能変更時はREADME.md / SETUP.md / DEVELOPMENT.mdを更新し、UI変更時はUI_DESIGN.mdも更新します。

---

# サミット特売Notionカレンダー・毎日通知

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

`gas/FlyerDeals.gs` 1ファイルで次を自動化します。

```text
サミット公式店舗ページを確認
↓
チラシiframe / 画像候補を取得
↓
必要時のみ公開フォールバックを利用
↓
新しいチラシだけGeminiで画像認識
↓
商品名・価格・容量・対象日を構造化
↓
Notion特売カレンダーDBへ同期
↓
Notionから今日の特売を読み直す
↓
当日の特売をLINEへ毎朝通知
```

Googleカレンダーは使用しません。Notion DBが特売情報の正本です。

Notionでは`特売日`をDateプロパティにし、カレンダービューで確認します。期間特売はDateの開始〜終了として1ページで管理します。

同じ `店舗 + 商品 + 価格 + 容量 + 特売期間` は `識別キー` で重複を防ぎます。新しいチラシへ切り替わった場合、今日以降に残る旧チラシ行は `有効=false` にし、過去分は履歴として残します。

同じチラシが続く間は保存済み解析結果を再利用し、毎日同じ画像をGeminiへ送り直しません。

初回設定・テストは `FLYER_TEST.md` を参照してください。

---

# 迷ったときの案内

従来の長いヘルプ一覧ではなく、目的と状況からコマンドを探せます。

```text
？
ヘルプ
おすすめ
何したい 節約したい
コマンド
```

- `？` / `ヘルプ`: 目的から選ぶ
- `おすすめ`: 現在の状態を見て最大3件提案
- `何したい ○○`: 自由文から関連コマンドを提案
- `コマンド`: 全コマンドを一覧表示

`おすすめ` と `何したい` はGeminiを使わずPythonのルール判定で動きます。

---

# 主なLINEコマンド

```text
メニュー
？
おすすめ
何したい 節約したい
コマンド
家計判断
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

状態: **実装完了・要実機確認**

量が多いため、Phase 2は3ブロックに分割しています。

## Phase 2A — 日々の家計判断

```text
今日使える
ペース
異常支出
```

追加DBは不要です。

## Phase 2B — 月次判断

```text
予算提案
月締め
月締め YYYY-MM
月締め確定 YYYY-MM
月締め確定強制 YYYY-MM
月次レビュー
月次レビュー YYYY-MM
```

月締めは終了済みの月だけ対象です。通常の`月締め確定`はカード未処理があると停止します。

## Phase 2C — 将来予測・目標

```text
年間予測
年間予測 2026
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

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

特売カレンダーDB:

| 名前 | 型 |
|---|---|
| `商品名` | Title |
| `特売日` | Date |
| `価格` | Rich text |
| `容量・単位` | Rich text |
| `店舗` | Select |
| `備考` | Rich text |
| `優先度` | Number |
| `チラシURL` | URL |
| `チラシ識別` | Rich text |
| `識別キー` | Rich text |
| `有効` | Checkbox |
| `更新日時` | Date |

---

# AIモデル切替

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLiteです。月次レビューも選択中モデルを使います。

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

---

# GAS推奨トリガー

```text
checkCardEmails                    → 1時間ごと
runDailySummitFlyerAutomation      → 毎日 朝6時台
sendDailyMemoReminder              → 毎日 朝8時ごろ
sendDailyBudgetAlert               → 毎日 20時ごろ
sendDailyCardPendingReminder       → 毎日 20〜21時ごろ
sendMonthEndCardCheck              → 毎日 21時ごろ
sendWeeklyFinanceReport            → 毎週日曜 20時ごろ
```

---

# 保守・テスト

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

チラシ自動化: `FLYER_TEST.md`

障害対応: `MAINTENANCE.md`

Phase 3はまだ開始していません。
