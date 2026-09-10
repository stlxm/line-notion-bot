// LINEカード利用通知 GAS
//
// Script Properties に以下を設定してください。
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN
//   RENDER_BASE_URL       例: https://xxxx.onrender.com
//   SCHEDULER_SECRET      Render側と同じ値
//
// 秘密情報はソースコードへ直接書かないでください。

const SEARCH_INTERVAL_MINUTES = 120; // 通常監視は直近2時間を対象
const GMAIL_SEARCH_DAYS = 2;         // Gmail検索は広め。最終判定は上の2時間
const LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push";
const PROCESSED_IDS_KEY = "PROCESSED_CARD_MESSAGE_IDS";
const BACKFILL_IDS_KEY = "BACKFILLED_CARD_MESSAGE_IDS";
const MAX_PROCESSED_IDS = 400; // Script Properties 1値のサイズを大きくしすぎない

function checkCardEmails() {
  Logger.log("--- 通常カード監視 開始 ---");

  const cutoff = new Date(Date.now() - SEARCH_INTERVAL_MINUTES * 60 * 1000);
  Logger.log(`[検索期限] ${cutoff}`);

  checkJCB(cutoff);
  checkSMBC(cutoff);
  checkRakuten(cutoff);
  checkPayPay(cutoff);

  Logger.log("--- 通常カード監視 完了 ---");
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

function getRenderConfig() {
  const props = PropertiesService.getScriptProperties();
  const baseUrl = (props.getProperty("RENDER_BASE_URL") || "").replace(/\/$/, "");
  const secret = props.getProperty("SCHEDULER_SECRET") || "";

  if (!baseUrl || !secret) {
    throw new Error("Script Properties に RENDER_BASE_URL と SCHEDULER_SECRET を設定してください。");
  }

  return { baseUrl, secret };
}

function callRenderApi_(path, payload) {
  const config = getRenderConfig();
  const response = UrlFetchApp.fetch(config.baseUrl + path, {
    method: "post",
    contentType: "application/json",
    headers: { "X-API-KEY": config.secret },
    payload: JSON.stringify(payload || {}),
    muteHttpExceptions: true,
  });

  const status = response.getResponseCode();
  const body = response.getContentText();
  Logger.log(`[Render] ${path}: ${status} ${body}`);

  if (status < 200 || status >= 300) {
    throw new Error(`${path} の呼び出しに失敗しました: ${status} ${body}`);
  }

  return body ? JSON.parse(body) : {};
}

function getStoredIds_(key) {
  const raw = PropertiesService.getScriptProperties().getProperty(key);
  if (!raw) return [];
  try {
    const ids = JSON.parse(raw);
    return Array.isArray(ids) ? ids : [];
  } catch (e) {
    return [];
  }
}

function rememberId_(key, messageId) {
  const props = PropertiesService.getScriptProperties();
  const ids = getStoredIds_(key).filter(id => id !== messageId);
  ids.push(messageId);
  props.setProperty(key, JSON.stringify(ids.slice(-MAX_PROCESSED_IDS)));
}

function getProcessedMessageIds() {
  return getStoredIds_(PROCESSED_IDS_KEY);
}

function rememberProcessedMessageId(messageId) {
  rememberId_(PROCESSED_IDS_KEY, messageId);
}

function enqueuePendingCard_(messageId, cardName, storeName, amount, dateStr) {
  return callRenderApi_("/api/card-pending", {
    message_id: messageId,
    card: cardName,
    store: storeName,
    amount: Number(amount),
    date: dateStr,
  });
}

function markPendingNotified_(pendingId) {
  if (!pendingId) return;
  try {
    callRenderApi_("/api/card-pending-notified", { pending_id: pendingId });
  } catch (e) {
    Logger.log("通知済み更新エラー: " + e.toString());
  }
}

function sendToLineBot(cardName, storeName, amount, dateStr, pendingId, pendingCount) {
  Logger.log(`[LINE Flex送信] ${cardName}: ${storeName} - ¥${amount} (${dateStr})`);

  const config = getLineConfig();
  const safeCard = encodeURIComponent(cardName);
  const safeStore = encodeURIComponent(storeName);
  const safeAmount = encodeURIComponent(String(amount));
  const safeDate = encodeURIComponent(dateStr);
  const safePendingId = encodeURIComponent(pendingId || "");

  const countText = pendingCount > 1
    ? `未処理キューに追加しました。現在 ${pendingCount} 件あります。`
    : "未処理キューに追加しました。";

  const flexContents = {
    type: "bubble",
    size: "mega",
    header: {
      type: "box",
      layout: "vertical",
      contents: [
        { type: "text", text: "💳 カード利用を検知", weight: "bold", color: "#1DB446", size: "sm" },
        { type: "text", text: `¥${Number(amount).toLocaleString("ja-JP")}`, weight: "bold", size: "xxl", margin: "md" }
      ]
    },
    body: {
      type: "box",
      layout: "vertical",
      contents: [
        { type: "text", text: "利用先", color: "#aaaaaa", size: "xs" },
        { type: "text", text: storeName, weight: "bold", color: "#444444", size: "md", wrap: true, margin: "xs" },
        { type: "text", text: `カード: ${cardName}`, color: "#666666", size: "sm", wrap: true, margin: "md" },
        { type: "text", text: `利用日: ${dateStr}`, color: "#666666", size: "sm", wrap: true, margin: "xs" },
        { type: "separator", margin: "lg" },
        { type: "text", text: countText, size: "xs", color: "#888888", margin: "lg", wrap: true }
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
            label: "ジャンルを選ぶ",
            data: `action=card_select_cat&card=${safeCard}&store=${safeStore}&amount=${safeAmount}&date=${safeDate}&pending_id=${safePendingId}`
          }
        },
        {
          type: "button",
          style: "primary",
          height: "sm",
          action: {
            type: "postback",
            label: "店名を変更する",
            data: `action=card_change_store_start&card=${safeCard}&store=${safeStore}&amount=${safeAmount}&date=${safeDate}&pending_id=${safePendingId}`
          }
        },
        {
          type: "button",
          style: "secondary",
          height: "sm",
          action: {
            type: "postback",
            label: "登録しない",
            data: `action=skip_card_pending&pending_id=${safePendingId}`
          }
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

function pushTextToLine_(text) {
  const config = getLineConfig();
  const response = UrlFetchApp.fetch(LINE_PUSH_URL, {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + config.accessToken },
    payload: JSON.stringify({
      to: config.userId,
      messages: [{ type: "text", text: text }]
    }),
    muteHttpExceptions: true,
  });
  Logger.log(`[LINE text] ${response.getResponseCode()} ${response.getContentText()}`);
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

function processCardThreads(query, cutoff, cardName, amountRegex, storeRegex, usageDateRegex, options) {
  options = options || {};
  const notify = options.notify !== false;
  const targetMonth = options.targetMonth || null;
  const ignoreNormalProcessed = options.ignoreNormalProcessed === true;
  const backfillMode = options.backfillMode === true;
  const maxThreads = options.maxThreads || 20;

  Logger.log(`[${cardName}] Gmail検索: ${query}`);
  const threads = GmailApp.search(query, 0, maxThreads);
  Logger.log(`[${cardName}] ヒットしたスレッド数: ${threads.length}`);

  const processedIds = new Set(getProcessedMessageIds());
  const backfilledIds = new Set(getStoredIds_(BACKFILL_IDS_KEY));
  let messageCount = 0;
  let parsedCount = 0;
  let createdCount = 0;
  let duplicateCount = 0;

  threads.forEach(thread => {
    thread.getMessages().forEach(msg => {
      messageCount++;
      const messageId = msg.getId();

      if (cutoff && msg.getDate().getTime() < cutoff.getTime()) {
        return;
      }

      if (backfillMode && backfilledIds.has(messageId)) {
        duplicateCount++;
        return;
      }

      if (!ignoreNormalProcessed && processedIds.has(messageId)) {
        duplicateCount++;
        return;
      }

      const body = msg.getPlainBody();
      const amountMatch = body.match(amountRegex);
      const storeMatch = body.match(storeRegex);
      const usageDateMatch = usageDateRegex ? body.match(usageDateRegex) : null;

      if (!amountMatch || !storeMatch) {
        Logger.log(`[解析失敗] ${cardName}: ${msg.getSubject()}`);
        return;
      }

      const amount = amountMatch[1].replace(/,/g, "");
      const store = storeMatch[1].trim();
      const dateStr = normalizeUsageDate(usageDateMatch ? usageDateMatch[1] : null, msg.getDate());

      if (targetMonth && !dateStr.startsWith(targetMonth)) {
        return;
      }

      parsedCount++;
      Logger.log(`[解析成功] ${cardName}: 店名=${store} / 金額=${amount} / 利用日=${dateStr}`);

      try {
        const queued = enqueuePendingCard_(messageId, cardName, store, amount, dateStr);
        if (!queued || !queued.pending_id) {
          Logger.log(`[キュー登録失敗] ${cardName}: ${store}`);
          return;
        }

        if (queued.created) createdCount++;

        let notificationOk = true;
        if (notify && !queued.notified) {
          notificationOk = sendToLineBot(
            cardName,
            store,
            amount,
            dateStr,
            queued.pending_id,
            queued.pending_count || 1
          );
          if (notificationOk) {
            markPendingNotified_(queued.pending_id);
          }
        }

        if (!notify || queued.notified || notificationOk) {
          rememberProcessedMessageId(messageId);
          processedIds.add(messageId);
          if (backfillMode) {
            rememberId_(BACKFILL_IDS_KEY, messageId);
            backfilledIds.add(messageId);
          }
          msg.markRead();
          Logger.log(`[処理成功] ${cardName}: ${store} ¥${amount}`);
        }
      } catch (e) {
        Logger.log(`[処理失敗・再試行対象] ${cardName}: ${e.toString()}`);
      }
    });
  });

  Logger.log(
    `[${cardName}] 集計: スレッド=${threads.length}, メール=${messageCount}, 重複=${duplicateCount}, 解析=${parsedCount}, 新規キュー=${createdCount}`
  );
  return { createdCount, parsedCount, duplicateCount };
}

function checkJCB(cutoff) {
  const query = `from:mail@qa.jcb.co.jp subject:"JCBカード／ショッピングご利用のお知らせ" newer_than:${GMAIL_SEARCH_DAYS}d`;
  return processCardThreads(
    query, cutoff, "JCB",
    /(?:【)?(?:ご利用金額|利用金額)(?:】)?[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:【)?(?:ご利用先|利用先)(?:】)?[：:\s　]*([^\r\n]+)/,
    /(?:【)?(?:ご利用日時|利用日時|ご利用日|利用日)(?:\([^\)]*\))?(?:】)?[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

function checkSMBC(cutoff) {
  const query = `from:statement@vpass.ne.jp subject:"ご利用のお知らせ【三井住友カード】" newer_than:${GMAIL_SEARCH_DAYS}d`;
  return processCardThreads(
    query, cutoff, "三井住友カード",
    /(?:◇)?(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:◇)?(?:利用先|ご利用先|利用店名)[：:\s　]*([^\r\n]+)/,
    /(?:◇)?(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

function checkRakuten(cutoff) {
  const query = `from:info@mail.rakuten-card.co.jp subject:"カード利用のお知らせ(本人ご利用分)" newer_than:${GMAIL_SEARCH_DAYS}d`;
  return processCardThreads(
    query, cutoff, "楽天カード",
    /(?:■)?(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:■)?(?:利用先|ご利用先|利用店名)[：:\s　]*([^\r\n]+)/,
    /(?:■)?(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

function checkPayPay(cutoff) {
  const query = `subject:"【PayPayカード】ご利用のお知らせ" newer_than:${GMAIL_SEARCH_DAYS}d`;
  return processCardThreads(
    query, cutoff, "PayPay",
    /(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:利用先|ご利用先)[：:\s　]*([^\r\n]+)/,
    /(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/
  );
}

// 指定月のカードメールをまとめて未処理キューへ入れます。
// 過去取り込みでは1件ごとの通知はせず、最後に件数だけLINE通知します。
function backfillCardEmailsForMonth(year, month) {
  const targetMonth = `${year}-${String(month).padStart(2, "0")}`;
  const monthStart = new Date(year, month - 1, 1);
  const nextMonth = new Date(year, month, 1);
  const searchStart = new Date(monthStart.getTime() - 7 * 24 * 60 * 60 * 1000);
  const searchEnd = new Date(nextMonth.getTime() + 7 * 24 * 60 * 60 * 1000);
  const after = Utilities.formatDate(searchStart, "JST", "yyyy/MM/dd");
  const before = Utilities.formatDate(searchEnd, "JST", "yyyy/MM/dd");
  const commonOptions = {
    notify: false,
    targetMonth: targetMonth,
    ignoreNormalProcessed: true,
    backfillMode: true,
    maxThreads: 500,
  };

  let created = 0;

  created += processCardThreads(
    `from:mail@qa.jcb.co.jp subject:"JCBカード／ショッピングご利用のお知らせ" after:${after} before:${before}`,
    null, "JCB",
    /(?:【)?(?:ご利用金額|利用金額)(?:】)?[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:【)?(?:ご利用先|利用先)(?:】)?[：:\s　]*([^\r\n]+)/,
    /(?:【)?(?:ご利用日時|利用日時|ご利用日|利用日)(?:\([^\)]*\))?(?:】)?[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/,
    commonOptions
  ).createdCount;

  created += processCardThreads(
    `from:statement@vpass.ne.jp subject:"ご利用のお知らせ【三井住友カード】" after:${after} before:${before}`,
    null, "三井住友カード",
    /(?:◇)?(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:◇)?(?:利用先|ご利用先|利用店名)[：:\s　]*([^\r\n]+)/,
    /(?:◇)?(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/,
    commonOptions
  ).createdCount;

  created += processCardThreads(
    `from:info@mail.rakuten-card.co.jp subject:"カード利用のお知らせ(本人ご利用分)" after:${after} before:${before}`,
    null, "楽天カード",
    /(?:■)?(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:■)?(?:利用先|ご利用先|利用店名)[：:\s　]*([^\r\n]+)/,
    /(?:■)?(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/,
    commonOptions
  ).createdCount;

  created += processCardThreads(
    `subject:"【PayPayカード】ご利用のお知らせ" after:${after} before:${before}`,
    null, "PayPay",
    /(?:利用金額|ご利用金額)[：:\s　]*([\d,]+)[\s　]*円/,
    /(?:利用先|ご利用先)[：:\s　]*([^\r\n]+)/,
    /(?:利用日|ご利用日)[：:\s　]*((?:20\d{2})[\/\-年]\d{1,2}[\/\-月]\d{1,2})/,
    commonOptions
  ).createdCount;

  pushTextToLine_(
    `💳 ${year}年${month}月のカード履歴取り込みが完了しました。\n` +
    `未処理キューへ新しく ${created} 件追加しました。\n` +
    `「カード未処理」と送ると、古いものから1件ずつジャンルを選べます。`
  );

  return created;
}

// 2026年9月をまとめて取り込むときだけ手動実行してください。
function backfillSeptember2026() {
  return backfillCardEmailsForMonth(2026, 9);
}
