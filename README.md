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

チラシの「名前」ではなく、Shufoo URLの次の部分を1チラシの識別子として扱います。

```text
/t/asp_iframe/shop/264241/<配信ID>/
```

さらに、Shufooの店舗ページが個別リンクを1件しか返さない場合でも、チラシ画像URLの次の部分から配信IDを検出します。

```text
.../c/YYYY/MM/DD/c/<配信ID>/img/image1_00.jpg
```

同じ店舗でも配信IDが違えば別チラシです。GASはリンクと画像URLの両方から配信IDを列挙し、各配信IDのページを個別取得してGemini解析します。

Geminiを使わず、配信ID検出だけ確認するテスト:

```text
testSummitShufooDeliveryIds
```

## Gemini解析の再試行と部分同期防止

Liteモデルは同じ画像でも1回目のJSONが不完全になる場合があります。現在は次の安全策を入れています。

```text
通常解析
↓
日付なし / 商品0件なら失敗扱い
↓
その配信IDだけ temperature=0 の厳密プロンプトで1回再試行
↓
商品日付からチラシ期間を復元できる場合は救済
↓
検出した全配信IDが解析できたときだけNotion同期
```

5件検出して3件しか解析できない場合のような部分成功では、Notionへの同期を中止します。

## GASファイル

```text
gas/FlyerDeals.gs
gas/FlyerLifeCalendar.gs
```

`FlyerLifeCalendar.gs` が取得・解析・Notion同期の本体、`FlyerDeals.gs` は共通ヘルパーとLINE通知を担当します。

## LINE通知の優先順位

```text
1〜7日間の特売 → 🔥 今日・短期特売
8日以上         → 📅 月間・長期特売
```

同じ商品・価格・容量が月間特価と短期特売の両方にある場合は、短期側を優先します。通知上限は20件です。

2026-09-12の実機ログでは、通知対象114件に対する整理後件数が83件→67件→68件と変化しました。件数だけでなく、誤統合を避けながら実用上の重複を減らすことを優先しています。

一部の強い言い換えは通知上で複数残る場合がありますが、Notion元データを安全のため自動削除せず、既知の軽微な表示揺れとして許容します。

日次運用:

```text
runDailySummitLifeCalendarAutomation
```

`installDailySummitLifeCalendarTrigger` 実行後、Apps Scriptのトリガー画面で上記関数が登録済みであることを実機確認しています。

## Notion「生活カレンダー」

Database ID:

```text
684f959e451047389505a95ed368a7d6
```

主な共通項目:

| 名前 | 型 |
|---|---|
| `予定名` | Title |
| `日付` | Date |
| `種類` | Select |
| `金額` | Number |
| `内容` | Rich text |
| `有効` | Checkbox |
| `更新日時` | Date |

チラシ由来の特売では `価格 / 容量・単位 / 店舗 / 元チラシID / 元チラシ名 / 元画像URL / 確認状態` も保存します。

## Notion「チラシ一覧」

Database ID:

```text
fdd0c0ce50974273b9b88f5272858e90
```

---

# 迷ったときの案内

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

# AIモデル切替

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLiteです。チラシも `FLYER_GEMINI_MODEL` 未設定なら `gemini-3.5-flash-lite` を使います。

---

# GAS推奨トリガー

```text
checkCardEmails                         → 1時間ごと
runDailySummitLifeCalendarAutomation    → 毎日 朝6時台（登録確認済み）
sendDailyMemoReminder                   → 毎日 朝8時ごろ
sendDailyBudgetAlert                    → 毎日 20時ごろ
sendDailyCardPendingReminder            → 毎日 20〜21時ごろ
sendMonthEndCardCheck                   → 毎日 21時ごろ
sendWeeklyFinanceReport                 → 毎週日曜 20時ごろ
```

---

# 開発ロードマップ

今後の機能開発は、以前の100機能案からユーザーが選んだ **48機能** を正本とします。番号と正式名、進捗、実装順は `DEVELOPMENT.md` を基準にします。途中で追加した補助フェーズは、この48機能を置き換えません。

次の開発対象は **Phase 3A — 入力強化** です。

```text
#32 レシート入力
#33 複数品目レシート分類
#34 自然文家計簿入力
#36 よく使う支出テンプレート
```

Phase 3は、選択済み機能を次の順で進めます。

```text
Phase 3A: #32 #33 #34 #36
Phase 3B: #37 直前登録取り消し / #38 直前登録修正
Phase 3C: #39 家計簿検索 / #40 条件付き検索 / #45 店別ランキング / #46 小額支出積み上げ分析
```

Phase 4〜7も、100案から選んだ番号・正式名に沿って実装します。詳細は `DEVELOPMENT.md` を参照してください。

---

# 保守・テスト

Phase 1: `PHASE1_TEST.md`

Phase 2: `PHASE2_TEST.md`

チラシ・生活カレンダー: `FLYER_TEST.md`

障害対応: `MAINTENANCE.md`
