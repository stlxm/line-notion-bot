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

## 家計簿・予算

```text
支出 1200 ラーメン
今月
予算一覧
予算アラート
週次レポート
予算 100000
予算 食費 30000
固定費一覧
固定費
```

## メモ

```text
メモ 牛乳を買う
メモ一覧
メモ削除
```

## AI

```text
AI 今月の食費を分析して
AI改善
```

Geminiは`AI `を明示した質問だけで使用します。

---

# カード自動化 — Phase 1

Phase 1はコード実装完了です。LINE / Notion / GASの実環境確認が必要なため、運用上の状態は「実装済み・要実機確認」です。

## 通常フロー

```text
カード会社メール
↓
GAS checkCardEmails
↓
Render /api/card-pending
↓
固定費/サブスク除外・重複照合
↓
安全な自動登録ルールがONなら自動保存
または
Notion カード未処理DBへ一時保存
↓
LINE通知
↓
おすすめジャンル / 店名変更 / 一括分類 / 登録しない
↓
家計簿へ保存
↓
未処理をアーカイブ
↓
次の未処理を自動表示
```

## ジャンル学習

ユーザーがカード未処理を手動分類すると、`カード学習ルール` DBへ店名とジャンルを学習します。同じ正規化店名の過去分類があれば、次回のカード画面でおすすめジャンルを`★`付きで先頭表示します。

学習はGeminiを使いません。

## 同じ店をまとめて分類

同じカード＋同じ正規化店名の未処理が複数ある場合、カード画面に`同じ店 N件をまとめる`が表示されます。ジャンルを1回選ぶと対象をまとめて処理します。

各取引は保存前に家計簿重複チェックを行い、すでに家計簿にある取引は再保存せず照合済みとして未処理から除きます。保存に失敗したものは未処理に残ります。

## 安全な自動登録

自動登録は勝手にONになりません。

条件:

```text
同じ店を同じジャンルに3回以上分類
かつ
一致率100%
かつ
ユーザーが自動登録ONを明示
```

条件を満たすとカード画面または`カード自動登録`からONにできます。ON後の同一店は新着カード検知時に家計簿へ自動登録され、LINEへ「自動登録しました」と通知します。

自動登録結果自身は学習回数を増やしません。誤ったルールが自己強化されるのを防ぐためです。

## 自動登録ルール管理

```text
カード自動登録
```

学習済みの店、ジャンル、一致回数、自動登録ON/OFFを表示します。ONのルールはここからOFFにできます。

Render環境変数:

```text
NOTION_CARD_RULES_DATABASE_ID
CARD_AUTO_REGISTER_MIN_MATCHES
```

`CARD_AUTO_REGISTER_MIN_MATCHES`は未設定時3です。

## 家計簿の完全重複ガード

カードを保存する直前に、家計簿DBで次を照合します。

```text
利用日
金額
カード・支払方法
正規化した店名
```

一致する支出があれば自動保存せず、LINEで次の選択を出します。

```text
それでも保存する
重複として処理済みにする
```

このため、同じ取引を誤って二重登録しにくくなっています。

## 速報 / 確定明細の照合

Gmail Message IDが違っても、同日・同額・同カード・同一正規化店名なら同一取引候補として扱います。

- まだ未処理なら既存の未処理へ照合し、新しいキューを増やしません。
- すでに家計簿へ保存済みなら新しい未処理を作りません。

カード会社メール本文に「速報/確定」を示す専用IDがないケースでも、取引内容による二重抑止が働きます。

## サブスク

カードジャンルでは`固定費`を表示せず、`サブスク`だけ表示します。

`サブスク`を選ぶと固定費DBへ登録/更新し、今回分は家計簿へ保存します。次回以降、同じカード＋同じ正規化店名はカード検出から除外され、未処理にもLINE通知にも出ません。

解除は固定費DBの該当レコードで`有効`をOFFにします。

## 月末未処理チェック

GASの`sendMonthEndCardCheck`を1日1回実行します。Render側で月末か判定し、月末だけ以下のどちらかを通知します。

```text
未処理0件 → 完了通知
未処理あり → 残件数を警告
```

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

# 2026年9月カード履歴バックフィル

GASで一度だけ:

```text
backfillSeptember2026
```

実利用日が2026-09のメールを未処理へ入れます。途中まで処理済みなら残りだけ続行できます。

---

# Render環境変数

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
ADMIN_USER_ID
NOTION_API_KEY
NOTION_KAKEIBO_DATABASE_ID
NOTION_MONTHLY_DATABASE_ID
NOTION_FIXED_DATABASE_ID
NOTION_MEMO_DATABASE_ID
NOTION_URL_DATABASE_ID
NOTION_AI_FEEDBACK_DATABASE_ID
NOTION_CARD_PENDING_DATABASE_ID
NOTION_CARD_RULES_DATABASE_ID
NOTION_DATABASE_IDS
NOTION_PAGE_URL
GEMINI_API_KEY
GEMINI_MODEL
SCHEDULER_SECRET
CARD_AUTO_REGISTER_MIN_MATCHES
```

# GAS推奨トリガー

```text
checkCardEmails              → 1時間ごと
sendDailyMemoReminder        → 毎日 朝8時ごろ
sendDailyBudgetAlert         → 毎日 20時ごろ
sendDailyCardPendingReminder → 毎日 20〜21時ごろ
sendMonthEndCardCheck        → 毎日 21時ごろ
sendWeeklyFinanceReport      → 毎週日曜 20時ごろ
```

# 保守

不具合時は`MAINTENANCE.md`を参照してください。Phase 1の確認は`PHASE1_TEST.md`の順に実行します。

Phase 2はまだ開始していません。次回開発は`DEVELOPMENT.md`のPhase 2開始位置から行います。
