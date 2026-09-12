// サミット特売をNotionカレンダーDBへ同期し、期限切れを自動アーカイブする処理
//
// このファイルは gas/FlyerDeals.gs のチラシ取得・Gemini解析関数を再利用します。
// Apps Scriptプロジェクトには FlyerDeals.gs と FlyerNotion.gs の両方を配置してください。
//
// 必須 Script Properties:
//   NOTION_API_KEY
//   NOTION_FLYER_DATABASE_ID
//   GEMINI_API_KEY
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN
//
// 推奨トリガー:
//   runDailySummitFlyerNotionAutomation -> 毎日6〜7時台

const NOTION_API_VERSION_FLYER = "2022-06-28";
const NOTION_FLYER_STORE_NAME = "サミット ミナノ分倍河原店";
const NOTION_FLYER_SOURCE_URL = "https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer";

function runDailySummitFlyerNotionAutomation() {
  Logger.log("--- サミット特売 Notion同期 開始 ---");

  const archived = cleanupExpiredSummitFlyerPages_();
  const result = getOrAnalyzeSummitFlyer_();
  const sync = syncSummitDealsToNotion_(result.deals || [], result.sourceUrl || NOTION_FLYER_SOURCE_URL);
  sendTodaySummitDealsToLine_(result.deals || [], result.sourceUrl || NOTION_FLYER_SOURCE_URL);

  Logger.log(`期限切れアーカイブ: ${archived}件`);
  Logger.log(`Notion同期: 作成${sync.created} / 更新${sync.updated} / スキップ${sync.skipped}`);
  Logger.log(`解析結果: ${(result.deals || []).length}件`);
  Logger.log("--- サミット特売 Notion同期 完了 ---");
}

// 初回テスト用。期限切れ整理・Notion同期・LINE通知まで実行します。
function testSummitFlyerNotionAutomation() {
  runDailySummitFlyerNotionAutomation();
}

// Notionへの登録だけ試したい場合。LINE通知は行いません。
function testSummitFlyerNotionSyncOnly() {
  const result = analyzeSummitFlyer_(true);
  const archived = cleanupExpiredSummitFlyerPages_();
  const sync = syncSummitDealsToNotion_(result.deals || [], result.sourceUrl || NOTION_FLYER_SOURCE_URL);
  Logger.log(JSON.stringify({ archived: archived, sync: sync, deals: result.deals || [] }, null, 2));
}

// 既存のGoogleカレンダー用トリガーがあれば削除し、Notion版だけを毎日6時台に登録します。
function installDailySummitFlyerNotionTrigger() {
  const oldName = "runDailySummitFlyerAutomation";
  const newName = "runDailySummitFlyerNotionAutomation";
  const triggers = ScriptApp.getProjectTriggers();
  let hasNew = false;

  triggers.forEach(trigger => {
    const name = trigger.getHandlerFunction ? trigger.getHandlerFunction() : "";
    if (name === oldName) {
      ScriptApp.deleteTrigger(trigger);
      Logger.log("旧Googleカレンダー版トリガーを削除しました。");
    }
    if (name === newName) hasNew = true;
  });

  if (!hasNew) {
    ScriptApp.newTrigger(newName)
      .timeBased()
      .everyDays(1)
      .atHour(6)
      .create();
    Logger.log("毎日6時台のNotion特売同期トリガーを作成しました。");
  } else {
    Logger.log("Notion特売同期トリガーはすでに存在します。");
  }
}

function getFlyerNotionConfig_() {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("NOTION_API_KEY") || "";
  const databaseId = props.getProperty("NOTION_FLYER_DATABASE_ID") || "";
  if (!apiKey || !databaseId) {
    throw new Error("Script Properties に NOTION_API_KEY と NOTION_FLYER_DATABASE_ID を設定してください。");
  }
  return { apiKey: apiKey, databaseId: databaseId };
}

function flyerNotionHeaders_() {
  const config = getFlyerNotionConfig_();
  return {
    Authorization: `Bearer ${config.apiKey}`,
    "Notion-Version": NOTION_API_VERSION_FLYER,
    "Content-Type": "application/json",
  };
}

function notionFlyerRequest_(url, method, payload) {
  const options = {
    method: method || "get",
    headers: flyerNotionHeaders_(),
    muteHttpExceptions: true,
  };
  if (payload !== undefined && payload !== null) {
    options.contentType = "application/json";
    options.payload = JSON.stringify(payload);
  }

  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();
  const body = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error(`Notion API error: ${code} ${body.slice(0, 700)}`);
  }
  return body ? JSON.parse(body) : {};
}

function syncSummitDealsToNotion_(deals, sourceUrl) {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  let created = 0;
  let updated = 0;
  let skipped = 0;

  (deals || []).forEach(deal => {
    if (!deal || !deal.product || !deal.start_date || !deal.end_date) {
      skipped++;
      return;
    }

    // すでに終了している商品は新規登録しない。
    if (deal.end_date < today) {
      skipped++;
      return;
    }

    const key = buildFlyerDealKey_(deal);
    const existing = findFlyerPageByKey_(key);
    const properties = buildFlyerNotionProperties_(deal, key, sourceUrl);

    if (existing && existing.id) {
      notionFlyerRequest_(
        `https://api.notion.com/v1/pages/${existing.id}`,
        "patch",
        { properties: properties, archived: false }
      );
      updated++;
    } else {
      const config = getFlyerNotionConfig_();
      notionFlyerRequest_(
        "https://api.notion.com/v1/pages",
        "post",
        {
          parent: { database_id: config.databaseId },
          properties: properties,
        }
      );
      created++;
    }
  });

  return { created: created, updated: updated, skipped: skipped };
}

function buildFlyerDealKey_(deal) {
  const material = [
    NOTION_FLYER_STORE_NAME,
    String(deal.product || "").trim(),
    String(deal.price || "").trim(),
    String(deal.unit || "").trim(),
    String(deal.start_date || "").trim(),
    String(deal.end_date || "").trim(),
  ].join("|");
  return sha256Hex_(material).slice(0, 40);
}

function buildFlyerNotionProperties_(deal, key, sourceUrl) {
  const nowIso = new Date().toISOString();
  const dateValue = { start: deal.start_date };
  if (deal.end_date && deal.end_date !== deal.start_date) {
    dateValue.end = deal.end_date;
  }

  return {
    "商品名": {
      title: [{ text: { content: String(deal.product || "").slice(0, 200) } }],
    },
    "特売日": { date: dateValue },
    "価格": {
      rich_text: [{ text: { content: String(deal.price || "").slice(0, 200) } }],
    },
    "容量・単位": {
      rich_text: [{ text: { content: String(deal.unit || "").slice(0, 200) } }],
    },
    "店舗": { select: { name: NOTION_FLYER_STORE_NAME } },
    "備考": {
      rich_text: [{ text: { content: String(deal.notes || "").slice(0, 1000) } }],
    },
    "チラシURL": { url: sourceUrl || NOTION_FLYER_SOURCE_URL },
    "優先度": { number: Number(deal.priority) || 2 },
    "識別キー": {
      rich_text: [{ text: { content: key } }],
    },
    "更新日時": { date: { start: nowIso } },
  };
}

function findFlyerPageByKey_(key) {
  const config = getFlyerNotionConfig_();
  const result = notionFlyerRequest_(
    `https://api.notion.com/v1/databases/${config.databaseId}/query`,
    "post",
    {
      page_size: 1,
      filter: {
        property: "識別キー",
        rich_text: { equals: key },
      },
    }
  );
  return (result.results || [])[0] || null;
}

// 特売終了日が今日より前のページをアーカイブします。
// Notion APIの「削除」は通常アーカイブ扱いで、DB/カレンダービューから非表示になります。
function cleanupExpiredSummitFlyerPages_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  let archived = 0;
  let cursor = null;
  let guard = 0;

  do {
    const payload = { page_size: 100 };
    if (cursor) payload.start_cursor = cursor;
    const config = getFlyerNotionConfig_();
    const result = notionFlyerRequest_(
      `https://api.notion.com/v1/databases/${config.databaseId}/query`,
      "post",
      payload
    );

    (result.results || []).forEach(page => {
      if (!page || page.archived) return;
      const props = page.properties || {};
      const store = (((props["店舗"] || {}).select || {}).name || "");
      if (store && store !== NOTION_FLYER_STORE_NAME) return;

      const dateObj = (props["特売日"] || {}).date || null;
      if (!dateObj || !dateObj.start) return;
      const endDate = String(dateObj.end || dateObj.start).slice(0, 10);
      if (endDate >= today) return;

      notionFlyerRequest_(
        `https://api.notion.com/v1/pages/${page.id}`,
        "patch",
        { archived: true }
      );
      archived++;
    });

    cursor = result.has_more ? result.next_cursor : null;
    guard++;
  } while (cursor && guard < 20);

  return archived;
}

// 手動で期限切れだけ整理したいときに実行できます。
function cleanupExpiredSummitFlyerPages() {
  const archived = cleanupExpiredSummitFlyerPages_();
  Logger.log(`期限切れ特売を ${archived} 件アーカイブしました。`);
  return archived;
}
