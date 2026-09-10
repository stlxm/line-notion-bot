// 1日1回のメモ一覧通知
//
// Script Properties に以下を設定してください。
//   RENDER_BASE_URL   例: https://line-notion-bot.onrender.com
//   SCHEDULER_SECRET  Render側と同じ秘密鍵
//
// Apps Script のトリガーから sendDailyMemoReminder を1日1回実行してください。

function sendDailyMemoReminder() {
  const props = PropertiesService.getScriptProperties();
  const baseUrl = (props.getProperty("RENDER_BASE_URL") || "").replace(/\/$/, "");
  const secret = props.getProperty("SCHEDULER_SECRET") || "";

  if (!baseUrl || !secret) {
    throw new Error("RENDER_BASE_URL と SCHEDULER_SECRET を Script Properties に設定してください。");
  }

  const url = baseUrl + "/api/daily-memo";
  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "X-API-KEY": secret
    },
    payload: JSON.stringify({}),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  const status = response.getResponseCode();
  const body = response.getContentText();
  Logger.log(`[Daily Memo] ${status} ${body}`);

  if (status < 200 || status >= 300) {
    throw new Error(`Daily memo notification failed: ${status} ${body}`);
  }
}
