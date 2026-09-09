# 統合アシスタント LINE Bot 構築・導入マニュアル（SETUP.md）

本書は、Notion・Gemini 3.6 Flash・LINE Messaging API・Google Apps Script (GAS)・Render を連携させ、高機能な「家計簿・メモ・ナレッジ検索・URL保存」統合アシスタントLINE Botをゼロから構築するための手順書です。

---

## 全体構成図と準備するもの

### システム全体像
1. LINE: ユーザーとの対話インターフェース（ボタン操作・手動入力・通知受信・カード型メニュー表示）
2. Render: Python (Flask) サーバーのホスティング（app.py, kakeibo.py, memo.py, menu.py, notion_helper.py）
3. Notion: データベース群（家計簿、月別管理、固定費マスタ、メモ、URL保存、検索用ナレッジ）
4. GAS (Google Apps Script): Gmailのクレカ利用メール検知 & 月初固定費の自動一括登録タイマー
5. Gemini API: Notion内のナレッジベースを参照した自然言語自動回答
6. UptimeRobot: Render無料プランのスリープ防止（5分間隔ヘルスチェック）

### 必要なアカウント
* Notion アカウント
* LINE Developers アカウント
* GitHub アカウント
* Render アカウント
* Google アカウント（Gmail / Google AI Studio / GAS用）
* UptimeRobot アカウント

---

## Step 1: Notion データベースのセットアップ

以下のデータベース（DB）をNotion上に作成します。プロパティ名（列名）と型（Type）はコード側と厳密に紐づいているため、完全に一致させてください。

### 1. 家計簿（支出明細）DB
* DB名: 家計簿
* プロパティ設定:
  * 内容・店名: タイトル (Title)
  * 金額: 数値 (Number)
  * 日付: 日付 (Date)
  * ジャンル: セレクト (Select) -> オプション例: 食費, 日用品, 交通費, 娯楽
  * カード・支払方法: セレクト (Select) -> オプション例: 現金, JCB, 三井住友カード, PayPay, 楽天カード
  * 月別管理: リレーション (Relation) -> 後述の「月別管理DB」と接続

### 2. 月別管理 DB
* DB名: 月別管理
* プロパティ設定:
  * 年月: タイトル (Title) -> 例: 2026-09
  * 全体予算: 数値 (Number)
  * 食費予算: 数値 (Number) -> ※他のジャンル予算（例: 日用品予算）も必要に応じて作成
  * 家計簿: リレーション (Relation) -> 「家計簿（支出明細）DB」と接続

### 3. 固定費マスタ DB
* DB名: 固定費マスタ
* プロパティ設定:
  * 内容・店名: タイトル (Title)
  * 金額: 数値 (Number)
  * ジャンル: セレクト (Select) -> 例: 固定費, サブスク
  * カード・支払方法: セレクト (Select)
  * 有効: チェックボックス (Checkbox) -> チェックONの項目が自動登録対象

### 4. メモ DB
* DB名: メモ
* プロパティ設定:
  * メモ: タイトル (Title)
  * 日付: 日付 (Date)

### 5. URL保存 DB（後で見る用）
* DB名: 後で見るURL
* プロパティ設定:
  * URL: タイトル (Title)
  * 時間: テキスト (Rich Text)

### 6. インテグレーション（APIキー）の発行とDB接続
1. Notion Integrations (https://www.notion.so/my-integrations) へアクセスし、新規インテグレーションを作成して NOTION_API_KEY（secret_...）を取得します。
2. 作成した各データベースページの右上メニュー ... > コネクトを追加 から、作成したインテグレーションを接続します。
3. 各データベースページのURLから 32桁のデータベースID を控えます。
   * 例: https://www.notion.so/myworkspace/a1b2c3d4e5f6...?v=... の a1b2c3d4e5f6... の部分

---

## Step 2: LINE Messaging API のセットアップ

1. LINE Developers Console (https://developers.line.biz/console/) にログインし、プロバイダーおよび「Messaging API」チャネルを作成します。
2. チャネル基本設定: LINE_CHANNEL_SECRET を取得して控えます。
3. Messaging API設定:
   * 「チャネルアクセストークン（長期）」を発行し、LINE_CHANNEL_ACCESS_TOKEN を控えます。
   * 「応答メッセージ」を不可にし、「Webhookの利用」を有効（ON）にします。
   * ※ Webhook URLはRenderデプロイ後に設定します。

---

## Step 3: Google Gemini API キーの取得

1. Google AI Studio (https://aistudio.google.com/) にアクセスします。
2. 「Get API key」から新しいAPIキーを発行し、GEMINI_API_KEY を控えます。

---

## Step 4: GitHub & Render へのデプロイ

### 1. GitHubリポジトリの準備
以下の5つのPythonファイルと依存ライブラリ指定ファイルを自身のGitHubリポジトリにコミット/Pushします。

* app.py (メイン処理・ルーティング・LINE受信用)
* kakeibo.py (家計簿・予算残高・固定費管理用)
* memo.py (メモ追加・一覧・削除処理用)
* menu.py (カード型機能選択メニューUI用)
* notion_helper.py (Notion参照・Gemini検索回答・URL保存・対話型データ追加用)
* requirements.txt (依存関係)

#### requirements.txt の内容:
Flask
requests
gunicorn
line-bot-sdk
google-genai

### 2. Render での Web サービス作成
1. Render Dashboard (https://dashboard.render.com/) で New > Web Service を選択し、対象のGitHubリポジトリを接続します。
2. 基本設定:
   * Runtime: Python 3
   * Build Command: pip install -r requirements.txt
   * Start Command: gunicorn app:app
   * Instance Type: Free

### 3. 環境変数の設定 (Environment Variables)
Renderの Environment タブで以下の環境変数を設定します。

| Key | 設定内容 |
|---|---|
| LINE_CHANNEL_ACCESS_TOKEN | LINEのチャネルアクセストークン（長期） |
| LINE_CHANNEL_SECRET | LINEのチャネルシークレット |
| GEMINI_API_KEY | Google AI Studioで取得したAPIキー |
| NOTION_API_KEY | Notionインテグレーションシークレット |
| NOTION_KAKEIBO_DATABASE_ID | 家計簿DBの32桁ID |
| NOTION_MONTHLY_DATABASE_ID | 月別管理DBの32桁ID |
| NOTION_FIXED_DATABASE_ID | 固定費マスタDBの32桁ID |
| NOTION_MEMO_DATABASE_ID | メモDBの32桁ID |
| NOTION_URL_DATABASE_ID | URL保存DBの32桁ID |
| NOTION_DATABASE_IDS | Geminiが参照検索するDBのID（カンマ区切りで複数指定可） |
| NOTION_PAGE_URL | （任意）NotionのショートカットURL |

設定後、Save Changes を押すと自動でビルド＆デプロイが始まります。
デプロイ完了後、Render上で発行されたURL（例: https://your-app-name.onrender.com）をコピーし、LINE Developers の Webhook URL に https://your-app-name.onrender.com/callback と設定します。

---

## Step 5: GAS (Google Apps Script) の設定

Gmailでのクレジットカード利用通知検知、および毎月1日の固定費自動一括登録を行うGASを設定します。

1. Google Apps Script (https://script.google.com/) にアクセスし、新規プロジェクトを作成します。
2. 以下のコードを Code.gs に貼り付け、RENDER_URL を自身のRenderのURLに書き換えます。

const RENDER_URL = "https://your-app-name.onrender.com"; // RenderのURLに置き換え

// 1. クレジットカード利用通知メールの検知（10分間隔トリガー用）
function checkCreditCardMails() {
  const query = 'is:unread (from:jcb.co.jp OR from:vpass.ne.jp OR from:paypay-card.co.jp OR from:rakuten-card.co.jp) "利用"';
  const threads = GmailApp.search(query);

  for (const thread of threads) {
    const messages = thread.getMessages();
    for (const msg of messages) {
      if (msg.isUnread()) {
        const body = msg.getPlainBody();
        const date = Utilities.formatDate(msg.getDate(), "JST", "yyyy-MM-dd");
        
        let cardName = "クレジットカード";
        if (body.includes("JCB")) cardName = "JCB";
        else if (body.includes("三井住友")) cardName = "三井住友カード";
        else if (body.includes("PayPay")) cardName = "PayPayカード";
        else if (body.includes("楽天")) cardName = "楽天カード";

        const amountMatch = body.match(/([0-9,]+)\s*円/);
        const amount = amountMatch ? amountMatch[1].replace(/,/g, "") : "0";

        const storeMatch = body.match(/利用先[：:\s]*([^\r\n]+)/);
        const storeName = storeMatch ? storeMatch[1].trim() : "カード利用";

        const payload = {
          "events": [{
            "type": "message",
            "replyToken": "00000000000000000000000000000000",
            "source": {"userId": "SYSTEM_GAS"},
            "message": {
              "type": "text",
              "text": `CARD_NOTIFY|${cardName}|${storeName}|${amount}|${date}`
            }
          }]
        };

        UrlFetchApp.fetch(`${RENDER_URL}/callback`, {
          "method": "post",
          "contentType": "application/json",
          "payload": JSON.stringify(payload)
        });

        msg.markRead();
      }
    }
  }
}

// 2. 毎月1日の固定費自動一括登録（月1回タイマー用）
function triggerMonthlyFixedExpenses() {
  UrlFetchApp.fetch(`${RENDER_URL}/api/register-fixed`, {
    "method": "post"
  });
}

3. トリガー（タイマー）の設定:
   * 左メニューの トリガー (時計アイコン) > トリガーを追加
   * 機能1: checkCreditCardMails / 時間主導型 / 分ベースのタイマー / 10分おき
   * 機能2: triggerMonthlyFixedExpenses / 時間主導型 / 月ベースのタイマー / 毎月1日の午前9時〜10時

---

## Step 6: UptimeRobot（常時稼働・スリープ対策）の設定

Renderの無料プランは15分間アクセスがないとスリープするため、外部から定期的にヘルスチェックを行います。

1. UptimeRobot (https://uptimerobot.com/) にログインします。
2. Add New Monitor を押します。
   * Monitor Type: HTTP(s)
   * Friendly Name: Notion LINE Bot
   * URL (or IP): https://your-app-name.onrender.com/
   * Monitoring Interval: 5 minutes
3. 保存すると、5分間隔でトップページ（GET /）へアクセスが飛び、24時間常時即答できる状態が維持されます。

---

## 動作確認・機能一覧

LINEでBotと友達になり、以下のコマンドを送信して動作確認を行ってください。

* 機能メニュー呼び出し: メニュー または 機能
* 手動支出入力: 支出 1200 ラーメン
* 予算設定: 予算 100000 や 予算 食費 30000
* 固定費の一括登録・確認: 固定費 / 固定費一覧
* 固定費のLINE追加: 固定費追加 ジム会費 8000 固定費 三井住友カード
* メモ機能: メモ 卵を買う -> メモ一覧 -> メモ削除
* 後で見るURL: https://example.com
* 汎用データ追加: データ追加
* AIナレッジ検索: 今月の食費の合計は？ など自由に質問
