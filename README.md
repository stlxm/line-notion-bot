# LINE Notion Bot

LINEを入口に、家計簿・予算・カード利用通知・固定費/サブスク・メモ・Notion・Gemini AIをまとめて扱う個人向けBotです。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: 日常保守、障害切り分け、復旧
- `DEVELOPMENT.md`: 長期ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIとPostback設計ルール
- `PHASE1_TEST.md`: カード自動化テスト
- `PHASE2_TEST.md`: 月次・予算判断テスト
- `FLYER_TEST.md`: サミットチラシ・生活カレンダー実機テスト
- `gas/README.md`: GAS固有設定

機能変更時はREADME.md / SETUP.md / DEVELOPMENT.mdを更新し、UI変更時はUI_DESIGN.mdも更新します。

---

# 毎月1日の予算設定案内

状態: **実装済み・要実機確認**

毎月1日朝6時台に、LINEへ次のFlexを送ります。

```text
📅 毎月の予算設定
今月の全体予算を設定しますか？

[設定する]
[後でする]
```

`設定する` は既存のPostback `action=start_monthly_budget_input` に接続し、今月の全体予算を数字で入力後、Notionの月別管理DBへ保存します。

GAS:

```text
sendMonthlyBudgetNotice
```

手動テスト:

```text
testMonthlyBudgetNotice
```

毎月1日6時台のトリガー作成:

```text
installMonthlyBudgetNoticeTrigger
```

旧関数名 `triggerMonthlyBudgetNotice` / `testMonthlyNotice` も互換ラッパーとして残しています。

**LINE User ID / Channel Access Tokenはソースへ直書きせず、GAS Script Propertiesを使います。**

---

# 貸し借り管理

状態: **実装済み・要Render設定/実機確認**

Notionの `貸し借り管理` DBへ、貸した・借りた金額と精算状態を家計簿とは別に記録します。家計簿へ自動計上しないため、貸し借りによる二重計上を避けます。

```text
貸した 田中 3000 ランチ代
借りた 田中 2000
貸し借り一覧
精算 田中 3000
```

`精算` は相手+金額が未精算レコードに1件だけ一致するときだけ更新します。同額が複数ある場合は誤更新防止のため自動精算しません。

Render環境変数:

```text
NOTION_LOAN_DATABASE_ID=f9b2c4eb59ea4c13b968f8d9b48663bc
```

---

# 「この機能ある？」案内 + 機能追加要望

状態: **実装済み・要Render設定/実機確認**

LINEで機能名を聞くと、実装済みなら使い方、ロードマップ済みなら予定フェーズを返します。未知の機能なら `機能追加要望` DBへ自動記録します。

自然な聞き方にも対応します。

```text
機能確認 レシート入力
レシート入力ってできる？
貸し借りってある？
貸し借りの記録ってできる？
お金の貸し借りってできる？
```

判定:

```text
実装済み → 使い方を返す
ロードマップ済み・未実装 → 予定を返す（重複要望は作らない）
未知の機能 → 機能追加要望DBへ登録
```

同じ要望名が再度来た場合は新規行を増やさず `回数` を増やします。

Render環境変数:

```text
NOTION_FEATURE_REQUEST_DATABASE_ID=76e4fe5d248e4fd1a48f45e9bdd59e8c
```

---

# サミットチラシ → Notion生活カレンダー

状態: **Phase 2.7 実装完了・実機確認済み・日次トリガー運用中**

対象店舗:

```text
サミット ミナノ分倍河原店
公式: https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
Shufoo店舗ID: 264241
```

Notionは役割を2つに分けます。

```text
チラシ一覧
→ 元資料・配信ID・画像・掲載期間・抽出結果・確認状態を管理

生活カレンダー
→ 実際に日付で見る予定を管理
   特売は「種類=特売」として登録
```

生活カレンダーは将来、特売以外にも家計・引き落とし・給料・メモ・通常予定を載せられる汎用DBです。

## Shufooは配信ID単位で扱う

```text
/t/asp_iframe/shop/264241/<配信ID>/
```

画像URLからも配信IDを検出します。

```text
.../c/YYYY/MM/DD/c/<配信ID>/img/image1_00.jpg
```

Geminiを使わず配信IDだけ確認:

```text
testSummitShufooDeliveryIds
```

## Gemini解析の安全策

```text
通常解析
↓
日付なし / 商品0件なら失敗扱い
↓
その配信IDだけ厳密再試行
↓
検出した全配信IDが解析できたときだけNotion同期
```

## GASファイル

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

## LINE通知の優先順位

```text
1〜7日間の特売 → 🔥 今日・短期特売
8日以上         → 📅 月間・長期特売
```

通知上限は20件です。Notion元データは安全のため自動削除しません。

日次運用:

```text
runDailySummitLifeCalendarAutomation
```

---

# 迷ったときの案内

```text
？
ヘルプ
おすすめ
何したい 節約したい
機能確認 レシート入力
コマンド
```

---

# 主なLINEコマンド

```text
メニュー
？
おすすめ
何したい 節約したい
機能確認 レシート入力
コマンド
家計判断
支出 1200 ラーメン
貸した 田中 3000 ランチ代
借りた 田中 2000
貸し借り一覧
精算 田中 3000
今月
予算設定
予算一覧
今日使える
ペース
予算提案
異常支出
年間予測
月締め
月次レビュー
貯金目標
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

# AIモデル切替

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLiteです。

---

# GAS推奨トリガー

```text
checkCardEmails                         → 1時間ごと
sendMonthlyBudgetNotice                 → 毎月1日 朝6時台
runDailySummitLifeCalendarAutomation    → 毎日 朝6時台（登録確認済み）
sendDailyMemoReminder                   → 毎日 朝8時ごろ
sendDailyBudgetAlert                    → 毎日 20時ごろ
sendDailyCardPendingReminder            → 毎日 20〜21時ごろ
sendMonthEndCardCheck                   → 毎日 21時ごろ
sendWeeklyFinanceReport                 → 毎週日曜 20時ごろ
```

---

# 開発ロードマップ

100機能案から選んだ48機能を正本として進めます。詳細は `DEVELOPMENT.md`。

現在はPhase 3より先に、次を実機確認します。

```text
Phase 2.8 毎月1日の予算設定案内
Phase 2.9 貸し借り管理（#89系を先行）
Phase 2.10 機能ナビ + 機能追加要望収集
```

その後:

```text
Phase 3A
#32 レシート入力
#33 複数品目レシート分類
#34 自然文家計簿入力
#36 よく使う支出テンプレート
```

---

# 保守・テスト

Phase 1: `PHASE1_TEST.md`

Phase 2 / 毎月1日予算通知 / 貸し借り / 機能ナビ: `PHASE2_TEST.md`

チラシ・生活カレンダー: `FLYER_TEST.md`

障害対応: `MAINTENANCE.md`
