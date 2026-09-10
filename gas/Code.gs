// LINEカード利用通知 GAS
//
// Script Properties に以下を設定してください。
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN
//
// LINE_CHANNEL_ACCESS_TOKEN はソースコードへ直接書かないでください。

const SEARCH_INTERVAL_MINUTES = 1440; // 24時間
const GMAIL_SEARCH_DAYS = 2;           // Gmail検索は少し広め。最終判定は上の分数で行う
const LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push";
const PROCESSED_IDS_KEY = "PROCESSED_CARD_MESSAGE_IDS";
const MAX_PROCESSED_IDS = 200;

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

function getLineConfig() {
  const props = PropertiesService.getScriptProperties();
  const userId = props.getProperty("LINE_USER_ID");
  const accessToken = props.getProperty("LINE_CHANNEL_ACCESS_TOKEN");

  if (!userId || !accessToken) {
    throw new Error("Script Properties に LINE_USER_ID と LINE_CHANNEL_ACCESS_TOKEN を設定してください。");
  }

  return { userId, accessToken };
}

function getProcessedMessageIds() {
  const raw = PropertiesService.getScriptProperties().getProperty(PROCESSED_IDS_KEY);
  if (!raw) return [];
  try {
    const ids = JSON.parse(raw);
    return Array.isArray(ids) ? ids : [];
  } catch (e) {
    return [];
  }
}

function rememberProcessedMessageId(messageId) {
  const props = PropertiesService.getScriptProperties();
  const ids = getProcessedMessageIds().filter(id => id !== messageId);
  ids.push(messageId);
  const trimmed = ids.slice(-MAX_PROCESSED_IDS);
  props.setProperty(PROCESSED_IDS_KEY, JSON.stringify(trimmed));
}

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

function normalizeUsageDate(rawDate, fallbackDate) {
  if (!rawDate) {
    return Utilities.formatDate(fallbackDate, "JST", "yyyy-MM-dd");
  }

  const m = String(rawDate).match(/(20\d{2})[\/\-年](\d{1,2})[\/\-月](\d{1,2})/);
  if (!m) {
    return Utilities.formatDate(fallbackDate, "JST", "yyyy-MM-dd");
  }

  return `${m[1]}-${String(m[2]).padStart(2, "0")}-${String(m[3]).padStart(2, "0")}`;
}

function processCardThreads(query, cutoff, cardName, amountRegex, storeRegex, usageDateRegex) {
  Logger.log(`[${cardName}] Gmail検索: ${query}`);
  const threads = GmailApp.search(query, 0, 20);
  Logger.log(`[${cardName}] ヒットしたスレッド数: ${threads.length}`);

  const processedIds = new Set(getProcessedMessageIds());
  let messageCount = 0;
  let withinWindowCount = 0;
  let parsedCount = 0;
  let duplicateCount = 0;

  threads.forEach(thread => {
    thread.getMessages().forEach(msg => {
      messageCount++;
      const messageId = msg.getId();

      Logger.log(
        `[${cardName}] 候補メール: 日時=${msg.getDate()} / 既読=${!msg.isUnread()} / From=${msg.getFrom()} / 件名=${msg.getSubject()}`
      );

      if (msg.getDate().getTime() < cutoff.getTime()) {
        Logger.log(`[期間外スキップ] ${cardName}: ${msg.getDate()} / ${msg.getSubject()}`);
        return;
      }
      withinWindowCount++;

      if (processedIds.has(messageId)) {
        duplicateCount++;
        Logger.log(`[重複スキップ] ${cardName}: messageId=${messageId}`);
        return;
      }

      const body = msg.getPlainBody();
      const amountMatch = body.match(amountRegex);
      const storeMatch = body.match(storeRegex);
      const usageDateMatch = usageDateRegex ? body.match(usageDateRegex) : null;

      if (!amountMatch || !storeMatch) {
        Logger.log(`[解析失敗] ${cardName}: ${msg.getSubject()}`);
        Logger.log(`[解析状態] 金額=${!!amountMatch} / 利用先=${!!storeMatch}`);
        return;
      }

      const amount = amountMatch[1].replace(/,/g, "");
      const store = storeMatch[1].trim();
      const dateStr = normalizeUsageDate(usageDateMatch ? usageDateMatch[1] : null, msg.getDate());
      parsedCount++;

      Logger.log(`[解析成功] ${cardName}: 店名=${store} / 金額=${amount} / 利用日=${dateStr}`);

      if (sendToLineBot(cardName, store, amount, dateStr)) {
        rememberProcessedMessageId(messageId);
        processedIds.add(messageId);
        msg.markRead();
        Logger.log(`[処理成功] ${cardName}: ${store} ¥${amount}`);
      } else {
        Logger.log(`[送信失敗・再試行対象] ${cardName}: ${store} ¥${amount}`);
      }
    });
  });

  Logger.log(
    `[${cardName}] 集計: スレッド=${threads.length}, メール=${messageCount}, 24時間以内=${withinWindowCount}, 重複=${duplicateCount}, 解析成功=${parsedCount}`
  );
}

function checkJCB(cutoff) {
  Logger.log("JCBチェック中...");
  const query = `from:mail@qa.jcb.co.jp subject:"JCBカード／ショッピングご利用のお知らせ" newer_than:${GMAIL_SEARCH_DAYS}d`;

  processCardThreads(
    query,
    cutoff,
    "JCB",
    /(?:【)?(?:ご利用金額|利用金額)(?:】)?[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:【)?(?:ご利用先|利用先)(?:】)?[：:\s　]*([^\r\n]+)/,
    /(?:【)?(?:ご利用日時|利用日時|ご利用日|利用日)(?:\([^\)]*\))?(?:】)?[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

function checkSMBC(cutoff) {
  Logger.log("三井住友チェック中...");
  const query = `from:statement@vpass.ne.jp subject:"ご利用のお知らせ【三井住友カード】" newer_than:${GMAIL_SEARCH_DAYS}d`;

  processCardThreads(
    query,
    cutoff,
    "三井住友カード",
    /(?:◇)?(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:◇)?(?:利用先|ご利用先|利用店名)[：:\s　]*([^\r\n]+)/,
    /(?:◇)?(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

function checkRakuten(cutoff) {
  Logger.log("楽天チェック中...");
  const query = `from:info@mail.rakuten-card.co.jp subject:"カード利用のお知らせ(本人ご利用分)" newer_than:${GMAIL_SEARCH_DAYS}d`;

  processCardThreads(
    query,
    cutoff,
    "楽天カード",
    /(?:■)?(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:■)?(?:利用先|ご利用先|利用店名)[：:\s　]*([^\r\n]+)/,
    /(?:■)?(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

function checkPayPay(cutoff) {
  Logger.log("PayPayチェック中...");
  const query = `subject:"【PayPayカード】ご利用のお知らせ" newer_than:${GMAIL_SEARCH_DAYS}d`;

  processCardThreads(
    query,
    cutoff,
    "PayPay",
    /(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:利用先|ご利用先)[：:\s　]*([^\r\n]+)/,
    /(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}
