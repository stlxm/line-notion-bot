# DEVELOPMENT.md

このファイルはLINE Notion Botの長期開発メモ・進捗管理・次回再開位置の基準です。

## 運用ルール

- 機能追加時は README.md / SETUP.md / DEVELOPMENT.md を更新する。
- UI変更時は UI_DESIGN.md も更新する。
- 実機未確認のものは「実装済み・要実機確認」とする。
- LINE Postback dataは300文字以内。
- Gemini不要な処理はPython / Notion / GASで行う。
- 自動処理よりデータ保全を優先する。
- 大きいPhaseはA/B/Cへ細分化し、各ブロックごとにテスト可能な状態で止める。

---

# Phase 0 — 開発基盤

状態: 完了

- DEVELOPMENT / MAINTENANCE / UI_DESIGN
- README / SETUP役割分離
- Postback 300文字ルール

---

# Phase 1 — カード入力をほぼ自動化

状態: **実装完了・要実機確認**

実装済み:
- 店名正規化・ジャンル学習・おすすめ
- 同じ店の一括分類
- 3回以上100%一致+本人ONだけの自動登録
- 家計簿重複ガード
- 速報/確定候補照合
- サブスク→固定費DB→次回検出除外
- 月末未処理チェック
- `カードテスト`

安全仕様:
- 曖昧な重複候補は自動削除しない。
- 自動登録は本人が明示ONするまで有効化しない。

---

# AIモデル運用

状態: **実装済み・要実機確認**

```text
AI Lite   → gemini-3.5-flash-lite
AI Flash  → gemini-3.6-flash
AI Model  → 現在モデル確認
```

既定はLite。月次レビューも選択中モデルを使う。

---

# Phase 2 — 月次・予算判断

状態: **実装完了・要実機確認**

## Phase 2A — 日々の家計判断

```text
今日使える
ペース
異常支出
```

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

安全仕様:
- 月締めは終了済み月のみ。
- 通常確定はカード未処理があると停止。
- 強制確定は明示コマンドのみ。

## Phase 2C — 将来予測・目標

```text
年間予測
貯金目標
貯金目標追加 旅行 300000 50000 2027-03-31
貯金更新 旅行 80000
```

---

# Phase 2.5 — 目的ベースの案内

状態: **実装完了・要実機確認**

```text
？
ヘルプ
おすすめ
何したい 節約したい
コマンド
```

仕様:
- `？ / ヘルプ`: 目的別Flex。
- `おすすめ`: 状況から最大3件。
- `何したい ○○`: Pythonキーワード判定。
- `コマンド`: 全一覧。
- Geminiは使わない。

---

# Phase 2.6 — サミット特売Notionカレンダー

状態: **実装完了・要実機確認**

対象店舗:

```text
サミット ミナノ分倍河原店
https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
```

実装ファイル:
- `gas/FlyerDeals.gs`: 公式ページ/チラシ画像取得、公開フォールバック、Gemini画像解析、Notion同期、重複防止、LINE通知、日次トリガー
- `FLYER_TEST.md`: 実機確認

処理:

```text
最新チラシ確認
↓
新しいチラシならGeminiで商品・価格・期間を構造化
↓
Notion特売カレンダーDBへ同期
↓
Notionから今日分を再取得
↓
LINE通知
```

Notion DB:
- `商品名` Title
- `特売日` Date
- `価格` Rich text
- `容量・単位` Rich text
- `店舗` Select
- `備考` Rich text
- `優先度` Number
- `チラシURL` URL
- `チラシ識別` Rich text
- `識別キー` Rich text
- `有効` Checkbox
- `更新日時` Date

安全仕様:
- 同一の店舗+商品+価格+単位+期間は`識別キー`で重複防止。
- 新チラシ切替時、今日以降に残る旧チラシ行は`有効=false`。
- 過去データは履歴として残す。
- 同じチラシはキャッシュを再利用してGemini再解析を抑える。
- 毎朝の通知は解析結果を直接使わず、Notionを読み直して送る。
- Googleカレンダーは使用しない。

実機確認順:

```text
1. 特売カレンダーDB作成
2. Integrationを接続
3. GAS Script Propertiesへ NOTION_API_KEY / NOTION_FLYER_DATABASE_ID / GEMINI_API_KEY を設定
4. FlyerDeals.gs をApps Scriptへコピー
5. testSummitFlyerParse
6. testSummitFlyerAutomation
7. testTodaySummitFlyerNotification
8. installDailySummitFlyerTrigger
```

---

# Phase 3 — 入力・修正・検索

状態: **未着手**

対象: #32, #33, #34, #36, #37, #38, #39, #40, #45, #46

今後Phase 3も量が多ければ3A / 3B / 3Cへ細分化して実装する。

---

# Phase 4 — メモ・URL

状態: 未着手

---

# Phase 5 — AI品質

状態: 未着手

---

# Phase 6 — 信頼性

状態: 未着手

---

# Phase 7 — 特殊家計・出力

状態: 未着手

---

# 次に再開する場所

Phase 3へ勝手に進まない。次回はPhase 2.6の実機確認から再開する。

```text
1. Notion特売カレンダーDBを作成
2. GASへ FlyerDeals.gs をコピー
3. Script Propertiesを設定
4. FLYER_TEST.mdを上から確認
5. Notion重複防止と旧チラシ無効化を確認
6. 毎朝LINE通知を確認
7. 問題なければPhase 2.6を完了扱いへ変更
8. ユーザー指示があった場合だけPhase 3開始
```

---

# 変更履歴

## 2026-09-12

- Phase 2を2A / 2B / 2Cへ細分化。
- Phase 2.5として目的ベース案内を追加。
- サミット特売自動化を追加。
- 当初のGoogleカレンダー案からNotion特売カレンダーDB方式へ変更。
- チラシ機能を`gas/FlyerDeals.gs` 1ファイルへ統合。
- 新チラシ切替時に旧未来データを`有効=false`へ変更する仕様を追加。
- 同一特売の重複防止を追加。
- 通知前にNotionを読み直す設計へ変更。
- `FLYER_TEST.md` / README / SETUP / gas/READMEを最終構成へ更新。

## 2026-09-11

- Phase 1カード自動化を実装。
- AI Lite / Flash切替を追加。
- Phase 2 LINEコマンドを接続。
