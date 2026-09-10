// 家計簿の定期通知
//
// Script Properties:
//   RENDER_BASE_URL  例: https://xxxx.onrender.com
//   SCHEDULER_SECRET Render側と同じ秘密鍵

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

// 1日1回。80%以上の予算があるときだけLINE通知します。
function sendDailyBudgetAlert() {
  callFinanceEndpoint_("/api/budget-alert");
}

// 1日1回。カードのジャンル未選択が残っている時だけ件数を通知します。
function sendDailyCardPendingReminder() {
  callFinanceEndpoint_("/api/card-pending-reminder");
}

// 1日1回。Render側で月末か判定し、月末だけ未処理0件/残件数をLINE通知します。
function sendMonthEndCardCheck() {
  callFinanceEndpoint_("/api/card-month-end-check");
}

// 毎週日曜日など、週1回。
function sendWeeklyFinanceReport() {
  callFinanceEndpoint_("/api/weekly-report");
}
