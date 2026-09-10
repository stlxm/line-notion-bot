# GAS カード利用通知セットアップ

`gas/Code.gs` は Gmail のカード利用通知を検出し、LINEへ直接 Flex Message を Push します。

## なぜこの方式にするのか

以前のGASでは `CARD_NOTIFY|JCB|...` のようなテキストをBot自身がLINEへPushしていました。

しかし、Bot自身が送ったPush MessageはLINE Webhookの `MessageEvent` として `app.py` に戻ってこないため、`app.py` 側の `if user_message.startswith("CARD_NOTIFY|")` は実行されません。

新しいGASでは、最初のカード通知をFlex MessageとしてLINE Messaging APIへ直接送ります。ユーザーがFlex内のボタンを押すと、既存の `app.py` のPostback処理へ入り、その後のジャンル選択・店名変更・キャンセル処理は既存コードをそのまま利用します。

## 1. LINE Channel Access Tokenを再発行

LINE Channel Access Tokenをチャットやコードへ貼り付けた場合、そのトークンは公開済みとして扱い、LINE Developers Consoleから再発行してください。

再発行後、Render側の `LINE_CHANNEL_ACCESS_TOKEN` も新しい値へ更新してください。

## 2. GASのコードを置き換える

Google Apps Scriptの既存コードを `gas/Code.gs` の内容へ置き換えてください。

コード内にLINE User IDやChannel Access Tokenを直接記述する必要はありません。

## 3. Script Propertiesを設定する

Google Apps Scriptで以下を開きます。

- プロジェクトの設定
- スクリプト プロパティ
- スクリプト プロパティを追加

次の2項目を登録します。

| プロパティ | 値 |
|---|---|
| `LINE_USER_ID` | Flex Messageを送るLINE User ID |
| `LINE_CHANNEL_ACCESS_TOKEN` | 再発行したLINE Channel Access Token |

## 4. 一度手動実行する

GASエディタ上部の関数選択で `checkCardEmails` を選び、一度実行してください。

初回のみGmail・外部通信などの権限承認が求められます。

実行ログで以下のような表示を確認します。

```text
--- 処理開始 ---
JCBチェック中...
楽天チェック中...
...
LINEレスポンス: 200 ...
--- 処理完了 ---
```

カード利用メールが24時間以内に存在する場合、LINEへ `CARD_NOTIFY|...` の文字列ではなくFlex Messageが届きます。

## 5. 10分トリガーを設定する

Apps Scriptの「トリガー」から `checkCardEmails` を時間主導型・10分おきで実行するよう設定してください。

## メール期間判定について

Gmail検索の `newer_than:` で使用する `m` は minutes（分）ではなく months（月）です。

そのため以前の `newer_than:1440m` は1440分ではありません。

新コードではGmail検索を `newer_than:1d` とし、さらに各メールについて次の条件で24時間以内かを厳密に判定します。

```javascript
const cutoff = new Date(Date.now() - SEARCH_INTERVAL_MINUTES * 60 * 1000);

if (msg.getDate().getTime() < cutoff.getTime()) {
  return;
}
```

Gmail検索はスレッド単位で結果を返すため、スレッド内に古い未読メッセージが含まれていても、この二重チェックによって処理対象から除外されます。

## LINE通知後の流れ

1. Gmailでカード利用通知を受信
2. GASがメールを検出
3. GASがLINEへ最初のFlex MessageをPush
4. 「そのままジャンル選択へ」を押す
5. LINE Webhook → Render `app.py`
6. `card_select_cat` Postback処理
7. `kakeibo.create_card_notify_flex()` でジャンル選択Flexを返信
8. ジャンルを選択
9. Notion家計簿DBへ保存
10. 当月の予算状況をLINEへ返信

## 注意

新コードはLINEへの送信に成功した場合だけメールを既読にします。送信失敗時は未読のまま残るため、次回トリガーで再試行できます。
