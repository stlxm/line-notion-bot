// 家計簿の定期通知
//
// Script Properties:
//   RENDER_BASE_URL  例: https://xxxx.onrender.com
//   SCHEDULER_SECRET Render側と同じ秘密鍵
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN

function callFinanceEndpoint_(path) {
  const props = PropertiesService.getScriptProperties();
  const baseUrl = (props.getProperty("RENDER_BASE_URL") || "").replace(/\/$/, "");
  const secret = props.getProperty("SCHEDULER_SECRET") || "";

  if (!baseUrl || !secret) {
    throw new Error("Script Properties に RENDER_BASE_URL と SCHEDULER_SECRET を設定してください。");
  }

  const response = UrlFetchApp.fetch(baseUrl + path, {
    method: "post",
    headers: { "X-API-KEY": secret },
    muteHttpExceptions: true,
  });

  const status = response.getResponseCode();
  const body = response.getContentText();
  Logger.log(`${path}: ${status} ${body}`);

  if (status < 200 || status >= 300) {
    throw new Error(`${path} の呼び出しに失敗しました: ${status} ${body}`);
  }

  return body;
}

function pushFinanceLineMessage_(message) {
  const props = PropertiesService.getScriptProperties();
  const userId = props.getProperty("LINE_USER_ID") || "";
  const token = props.getProperty("LINE_CHANNEL_ACCESS_TOKEN") || "";

  if (!userId || !token) {
    throw new Error("Script Properties に LINE_USER_ID と LINE_CHANNEL_ACCESS_TOKEN を設定してください。");
  }

  const response = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({
      to: userId,
      messages: [message],
    }),
    muteHttpExceptions: true,
  });

  const status = response.getResponseCode();
  const body = response.getContentText();
  Logger.log(`[LINE push] ${status} ${body}`);

  if (status < 200 || status >= 300) {
    throw new Error(`LINE送信に失敗しました: ${status} ${body}`);
  }

  return body;
}

function createMonthlyBudgetNoticeFlex_() {
  return {
    type: "flex",
    altText: "今月の予算を設定しますか？",
    contents: {
      type: "bubble",
      header: {
        type: "box",
        layout: "vertical",
        contents: [
          {
            type: "text",
            text: "📅 毎月の予算設定",
            weight: "bold",
            color: "#1DB446",
            size: "sm",
          },
          {
            type: "text",
            text: "今月の全体予算を設定しますか？",
            weight: "bold",
            size: "md",
            margin: "md",
            wrap: true,
          },
        ],
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
              label: "設定する",
              data: "action=start_monthly_budget_input",
              displayText: "▶ 予算を設定する",
            },
          },
          {
            type: "button",
            style: "secondary",
            height: "sm",
            action: {
              type: "postback",
              label: "後でする",
              data: "action=cancel_registration",
              displayText: "▶ 後でする",
            },
          },
        ],
      },
    },
  };
}

function sendMonthlyBudgetNotice() {
  Logger.log("--- 毎月1日予算設定アナウンス開始 ---");
  pushFinanceLineMessage_(createMonthlyBudgetNoticeFlex_());
  Logger.log("--- 毎月1日予算設定アナウンス終了 ---");
}

function triggerMonthlyBudgetNotice() {
  sendMonthlyBudgetNotice();
}

function testMonthlyBudgetNotice() {
  sendMonthlyBudgetNotice();
}

function testMonthlyNotice() {
  testMonthlyBudgetNotice();
}

function installMonthlyBudgetNoticeTrigger() {
  const handler = "sendMonthlyBudgetNotice";

  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (trigger.getHandlerFunction() === handler) {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger(handler)
    .timeBased()
    .onMonthDay(1)
    .atHour(6)
    .create();

  Logger.log("毎月1日6時台の予算設定通知トリガーを登録しました: " + handler);
}

function sendDailyBudgetAlert() {
  callFinanceEndpoint_("/api/budget-alert");
}

function sendDailyCardPendingReminder() {
  callFinanceEndpoint_("/api/card-pending-reminder");
}

function sendMonthEndCardCheck() {
  callFinanceEndpoint_("/api/card-month-end-check");
}

function sendWeeklyFinanceReport() {
  callFinanceEndpoint_("/api/weekly-report");
}
