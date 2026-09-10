# LINE Notion Bot

LINEを入口に、家計簿・予算・カード利用通知・カード未処理キュー・固定費/サブスク・メモ・Notion・Gemini AIをまとめて扱う個人向けBotです。

## ドキュメント

- `SETUP.md`: 初期構築、環境変数、Notion DB、GAS、Render設定
- `MAINTENANCE.md`: AIなしでも行える日常保守、障害切り分け、復旧
- `DEVELOPMENT.md`: 長期ロードマップ、進捗、次回再開位置
- `UI_DESIGN.md`: LINE UIとPostback設計ルール
- `PHASE1_TEST.md`: カード自動化の実機確認手順
- `gas/README.md`: GAS固有の設定

機能変更時はREADME.md / SETUP.md / DEVELOPMENT.mdを更新し、UI変更時はUI_DESIGN.mdも更新します。

---

# 現在の主な操作

```text
メニュー
支出 1200 ラーメン
今月
予算一覧
予算アラート
週次レポート
固定費一覧
カード未処理
カード自動登録
メモ 牛乳を買う
メモ一覧
AI 今月の食費を分析して
AI改善
```

Geminiは`AI `を明示した質問だけで使用します。

---

# カード自動化 — Phase 1

Phase 1はコード実装完了です。LINE / Notion / GASの実環境確認が必要なため、状態は「実装済み・要実機確認」です。

## 通常フロー

```text
カード会社メール
↓
GAS checkCardEmails
↓
Render /api/card-pending
↓
固定費/サブスク除外
↓
安全な自動登録ルールがONなら自動保存
または
Notion カード未処理DBへ保存
↓
LINE通知
↓
おすすめジャンル / 店名変更 / 同じ店まとめ処理 / 登録しない
↓
家計簿へ保存
↓
未処理をアーカイブ
↓
次の未処理を自動表示
```

## ジャンル学習とおすすめ

カード未処理を手動分類すると`カード学習ルール`DBへ学習します。同じ正規化店名の過去分類があれば、次回のカード画面でおすすめを`★ジャンル`として先頭表示します。Geminiは使いません。

## 同じ店をまとめて分類

同じカード＋同じ正規化店名の未処理が複数ある場合、`同じ店 N件をまとめる`を表示します。ジャンルを1回選んでまとめて処理できます。

保存失敗や重複候補は勝手に消さず未処理へ残します。

## 安全な自動登録

自動登録は勝手にONになりません。

```text
同じ店を同じジャンルに3回以上手動分類
AND 一致率100%
AND ユーザーが自動登録ONを明示
```

条件を満たした店だけ、カード画面または`カード自動登録`からONにできます。ON後の新着利用は家計簿へ自動保存し、LINEへ自動登録通知を送ります。

自動登録結果自身は学習回数を増やしません。

## 重複ガード / 速報・確定候補の照合

カード保存時に次を家計簿DBと比較します。

```text
利用日
金額
カード・支払方法
正規化した店名
```

一致した場合は「重複候補」として止め、本人が選びます。

```text
それでも保存する
重複として処理済みにする
```

重要: 同日・同額・同店でも正当な複数利用があり得るため、**別Gmail Message IDというだけで自動削除・自動統合はしません**。速報/確定メールらしい同一取引も候補として照合し、曖昧な場合は本人確認を優先します。

## サブスク

カードジャンルでは`固定費`を表示せず、`サブスク`だけ表示します。

`サブスク`を選ぶと固定費DBへ登録/更新し、今回分は家計簿へ保存します。次回以降、同じカード＋同じ正規化店名はカード検出から除外され、未処理にもLINE通知にも出ません。

解除は固定費DBの該当レコードで`有効`をOFFにします。

## 月末未処理チェック

GASの`sendMonthEndCardCheck`を1日1回実行します。Render側で月末か判定し、月末だけ未処理0件または残件数をLINE通知します。

---

# Notion DB

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

## カード学習ルールDB

| 名前 | 型 |
|---|---|
| `店名キー` | Title |
| `表示名` | Rich text |
| `ジャンル` | Select |
| `学習回数` | Number |
| `一致回数` | Number |
| `自動登録` | Checkbox |
| `最終更新` | Date |

## 固定費DB

| 名前 | 型 |
|---|---|
| `内容・店名` | Title |
| `金額` | Number |
| `ジャンル` | Select |
| `カード・支払方法` | Select |
| `有効` | Checkbox |

---

# Phase 1追加環境変数

```text
NOTION_CARD_RULES_DATABASE_ID
CARD_AUTO_REGISTER_MIN_MATCHES=3
```

その他の全環境変数と作成手順は`SETUP.md`を参照してください。

# GAS推奨トリガー

```text
checkCardEmails              → 1時間ごと
sendDailyMemoReminder        → 毎日 朝8時ごろ
sendDailyBudgetAlert         → 毎日 20時ごろ
sendDailyCardPendingReminder → 毎日 20〜21時ごろ
sendMonthEndCardCheck        → 毎日 21時ごろ
sendWeeklyFinanceReport      → 毎週日曜 20時ごろ
```

# 2026年9月カード履歴

```text
backfillSeptember2026
```

をGASで手動実行します。途中まで処理済みなら残りから続行できます。

# 保守

Phase 1導入確認は`PHASE1_TEST.md`、障害対応は`MAINTENANCE.md`を参照してください。

Phase 2はまだ開始していません。次回はPhase 1の実機結果確認後、ユーザー指示があった場合だけ開始します。
