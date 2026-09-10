// LINEカード利用通知 GAS
//
// Script Properties に以下を設定してください。
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN
//
// LINE_CHANNEL_ACCESS_TOKEN はソースコードへ直接書かないでください。

const SEARCH_INTERVAL_MINUTES = 1440; // 24時間
const LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push";

/**
 * 10分間隔トリガーで実行するメイン関数。
 * Gmailの検索条件は1日分を広めに取得し、msg.getDate()で24時間以内を厳密判定します。
 */
function checkCardEmails() {
  Logger.log("--- 処理開始 ---");

  const cutoff = new Date(Date.now() - SEARCH_INTERVAL_MINUTES * 60 * 1000);
  Logger.log(`[検索期限] ${cutoff}`);

  checkJCB(cutoff);
  checkSMBC(cutoff);
  checkRakuten(cutoff);
  checkPayPay(cutoff);

  Logger.log("--- 処理完了 ---");
}

/**
 * Script Properties から秘密情報を取得します。
 */
function getLineConfig() {
  const props = PropertiesService.getScriptProperties();
  const userId = props.getProperty("LINE_USER_ID");
  const accessToken = props.getProperty("LINE_CHANNEL_ACCESS_TOKEN");

  if (!userId || !accessToken) {
    throw new Error(
      "Script Properties に LINE_USER_ID と LINE_CHANNEL_ACCESS_TOKEN を設定してください。"
    );
  }

  return { userId, accessToken };
}

/**
 * カード利用をLINEへFlex Messageとして直接Pushします。
 */
function sendToLineBot(cardName, storeName, amount, dateStr) {
  Logger.log(`[LINE Flex送信] ${cardName}: ${storeName} - ¥${amount} (${dateStr})`);

  const config = getLineConfig();
  const safeCard = encodeURIComponent(cardName);
  const safeStore = encodeURIComponent(storeName);
  const safeAmount = encodeURIComponent(String(amount));
  const safeDate = encodeURIComponent(dateStr);

  const flexContents = {
    type: "bubble",
    header: {
      type: "box",
      layout: "vertical",
      contents: [
        { type: "text", text: "💳 カード利用検知", weight: "bold", color: "#1DB446", size: "sm" },
        { type: "text", text: `¥${Number(amount).toLocaleString("ja-JP")}`, weight: "bold", size: "xxl", margin: "md" }
      ]
    },
    body: {
      type: "box",
      layout: "vertical",
      contents: [
        {
          type: "box",
          layout: "baseline",
          contents: [
            { type: "text", text: "利用先", color: "#aaaaaa", size: "sm", flex: 2 },
            { type: "text", text: storeName, weight: "bold", color: "#666666", size: "sm", flex: 5, wrap: true }
          ]
        },
        {
          type: "box",
          layout: "baseline",
          contents: [
            { type: "text", text: "カード", color: "#aaaaaa", size: "sm", flex: 2 },
            { type: "text", text: cardName, color: "#666666", size: "sm", flex: 5, wrap: true }
          ],
          margin: "xs"
        },
        { type: "separator", margin: "lg" },
        { type: "text", text: "店名を確認して次へ進んでください", size: "xs", color: "#888888", margin: "lg", align: "center" }
      ]
    },
    footer: {
      type: "box",
      layout: "vertical",
      spacing: "sm",
      contents: [
        {
          type: "button",
          style: "primary",
          height: "sm",
          action: {
            type: "postback",
            label: "そのままジャンル選択へ",
            data: `action=card_select_cat&card=${safeCard}&store=${safeStore}&amount=${safeAmount}&date=${safeDate}`
          }
        },
        {
          type: "button",
          style: "secondary",
          height: "sm",
          action: {
            type: "postback",
            label: "店名を変更する",
            data: `action=card_change_store_start&card=${safeCard}&store=${safeStore}&amount=${safeAmount}&date=${safeDate}`
          }
        },
        {
          type: "button",
          style: "secondary",
          height: "sm",
          action: { type: "postback", label: "登録しない", data: "action=cancel_registration" }
        }
      ]
    }
  };

  const payload = {
    to: config.userId,
    messages: [{ type: "flex", altText: `カード利用: ${storeName} ¥${amount}`, contents: flexContents }]
  };

  const options = {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + config.accessToken },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    const res = UrlFetchApp.fetch(LINE_PUSH_URL, options);
    const status = res.getResponseCode();
    const body = res.getContentText();
    Logger.log(`LINEレスポンス: ${status} ${body}`);
    return status >= 200 && status < 300;
  } catch (e) {
    Logger.log("LINE送信エラー: " + e.toString());
    return false;
  }
}

/**
 * 検索結果の各メッセージを処理します。
 */
function processCardThreads(query, cutoff, cardName, amountRegex, storeRegex) {
  Logger.log(`[${cardName}] Gmail検索: ${query}`);
  const threads = GmailApp.search(query, 0, 20);
  Logger.log(`[${cardName}] ヒットしたスレッド数: ${threads.length}`);

  let messageCount = 0;
  let unreadCount = 0;
  let inRangeCount = 0;
  let parsedCount = 0;

  threads.forEach(thread => {
    thread.getMessages().forEach(msg => {
      messageCount++;
      Logger.log(
        `[${cardName}] 候補メール: ` +
        `未読=${msg.isUnread()} / 日時=${msg.getDate()} / ` +
        `From=${msg.getFrom()} / 件名=${msg.getSubject()}`
      );

      if (!msg.isUnread()) return;
      unreadCount++;

      if (msg.getDate().getTime() < cutoff.getTime()) {
        Logger.log(`[期間外スキップ] ${cardName}: ${msg.getDate()} / ${msg.getSubject()}`);
        return;
      }
      inRangeCount++;

      const body = msg.getPlainBody();
      const amountMatch = body.match(amountRegex);
      const storeMatch = body.match(storeRegex);

      if (!amountMatch || !storeMatch) {
        Logger.log(
          `[解析失敗] ${cardName}: ${msg.getSubject()} / ` +
          `金額=${amountMatch ? "OK" : "NG"} / 店名=${storeMatch ? "OK" : "NG"}`
        );
        return;
      }
      parsedCount++;

      const amount = amountMatch[1].replace(/,/g, "");
      const store = storeMatch[1].trim();
      const dateStr = Utilities.formatDate(msg.getDate(), "JST", "yyyy-MM-dd");

      if (sendToLineBot(cardName, store, amount, dateStr)) {
        msg.markRead();
        Logger.log(`[処理成功] ${cardName}: ${store} ¥${amount}`);
      } else {
        Logger.log(`[送信失敗・未読維持] ${cardName}: ${store} ¥${amount}`);
      }
    });
  });

  Logger.log(
    `[${cardName}] 集計: スレッド=${threads.length}, ` +
    `メール=${messageCount}, 未読=${unreadCount}, ` +
    `24時間以内=${inRangeCount}, 解析成功=${parsedCount}`
  );
}

function checkJCB(cutoff) {
  Logger.log("JCBチェック中...");
  const query = 'from:mail@qa.jcb.co.jp subject:"JCBカード／ショッピングご利用のお知らせ" is:unread newer_than:1d';
  processCardThreads(
    query,
    cutoff,
    "JCB",
    /(?:【)?(?:ご利用金額|利用金額)(?:】)?[：:\s ]*([\d,]+)[\s ]*円/,
    /(?:【)?(?:ご利用先|利用先)(?:】)?[：:\s ]*([^\r\n]+)/
  );
}

function checkSMBC(cutoff) {
  Logger.log("三井住友チェック中...");
  const query = 'from:statement@vpass.ne.jp subject:"ご利用のお知らせ【三井住友カード】" is:unread newer_than:1d';
  processCardThreads(
    query,
    cutoff,
    "三井住友カード",
    /(?:◇)?(?:利用金額|ご利用金額)[：:\s ]*([\d,]+)[\s ]*円/,
    /(?:◇)?(?:利用先|ご利用先|利用店名)[：:\s ]*([^\r\n]+)/
  );
}

function checkRakuten(cutoff) {
  Logger.log("楽天チェック中...");
  const query = 'from:info@mail.rakuten-card.co.jp subject:"カード利用のお知らせ(本人ご利用分)" is:unread newer_than:1d';
  processCardThreads(
    query,
    cutoff,
    "楽天カード",
    /(?:■)?(?:利用金額|ご利用金額)[：:\s ]*([\d,]+)[\s ]*円/,
    /(?:■)?(?:利用先|ご利用先|利用店名)[：:\s ]*([^\r\n]+)/
  );
}

function checkPayPay(cutoff) {
  Logger.log("PayPayチェック中...");
  const query = 'subject:"【PayPayカード】ご利用のお知らせ" is:unread newer_than:1d';
  processCardThreads(
    query,
    cutoff,
    "PayPay",
    /(?:利用金額|ご利用金額)[：:\s ]*([\d,]+)[\s ]*円/,
    /(?:利用先|ご利用先)[：:\s ]*([^\r\n]+)/
  );
}
