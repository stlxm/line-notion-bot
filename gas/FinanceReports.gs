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
            },
          },
        ],
      },
    },
  };
}

// 毎月1日 朝6時台に実行する予算設定案内。
// 「設定する」を押すとRender側の既存 postback 処理が
// WAITING_MONTHLY_BUDGET 状態へ移行し、数字入力後に月別管理DBへ保存します。
function sendMonthlyBudgetNotice() {
  Logger.log("--- 毎月1日予算設定アナウンス開始 ---");
  pushFinanceLineMessage_(createMonthlyBudgetNoticeFlex_());
  Logger.log("--- 毎月1日予算設定アナウンス終了 ---");
}

// 旧関数名との互換ラッパー。古いトリガーが残っていても動作します。
function triggerMonthlyBudgetNotice() {
  sendMonthlyBudgetNotice();
}

// 手動テスト用。
function testMonthlyBudgetNotice() {
  sendMonthlyBudgetNotice();
}

// 旧テスト関数名との互換ラッパー。
function testMonthlyNotice() {
  testMonthlyBudgetNotice();
}

// 毎月1日6時台のトリガーを1つだけ作成します。
// Apps Script のプロジェクトタイムゾーンは Asia/Tokyo を使用してください。
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
