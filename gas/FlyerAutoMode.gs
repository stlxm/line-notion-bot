// サミットチラシの自動反映モード。
// FlyerDeals.gs / FlyerLifeCalendar.gs と同じApps Scriptプロジェクトに置いてください。
//
// 目的:
// - Notionで「確認待ち → 確認済み」に手作業で変更する工程をなくす
// - Gemini解析に成功したチラシは、そのまま生活カレンダーへ有効化する
// - 既存の確認待ちデータも、掲載期間内なら自動で有効化する
// - 期限切れの特売は従来どおり無効化する

const LIFE_FLYER_AUTO_TRIGGER_FUNCTION = "runDailySummitLifeCalendarAutoAutomation";

function runDailySummitLifeCalendarAutoAutomation() {
  Logger.log("--- サミット→生活カレンダー 自動反映モード 開始 ---");

  const catalog = collectShufooFlyerCatalog_();
  const props = PropertiesService.getScriptProperties();
  const previousSignature = props.getProperty(LIFE_FLYER_SIGNATURE_KEY) || "";

  if (!catalog.signature || catalog.signature !== previousSignature) {
    const flyers = analyzeShufooFlyersById_(catalog);
    assertAllLifeFlyersAnalyzed_(catalog, flyers);

    const sync = syncLifeFlyers_(flyers);
    Logger.log(`[自動同期] flyers=${sync.flyers} / calendar=${sync.deals}`);

    if (catalog.signature && flyers.length > 0) {
      props.setProperty(LIFE_FLYER_SIGNATURE_KEY, catalog.signature);
      sendLifeFlyerAutoSyncNotice_(flyers);
    }
  } else {
    Logger.log("チラシ一覧に変更がないためGemini解析を省略しました。");
  }

  // 旧仕様で「確認待ち」のまま残っている既存データも自動で有効化する。
  const activated = autoActivateLifeFlyers_();
  Logger.log(`[自動有効化] チラシ一覧=${activated.flyers} / 生活カレンダー=${activated.deals}`);

  disableExpiredLifeFlyerEvents_();

  const deals = getTodayLifeFlyerDealsAuto_();
  sendTodaySummitDealsToLine_(deals);
  Logger.log(`今日の特売: ${deals.length}件`);
}

function autoActivateLifeFlyers_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const listDb = getLifeFlyerListConfig_().databaseId;
  const calendarDb = getFlyerNotionConfig_().databaseId;

  let flyerCount = 0;
  queryAllLifePages_(listDb).forEach(page => {
    const p = page.properties || {};
    const period = notionDateRange_(p["掲載期間"]);
    const end = period.end || period.start;
    if (end && end < today) return;

    const state = notionSelect_(p["確認状態"]);
    if (state === "確認済み") return;

    notionRequest_(`https://api.notion.com/v1/pages/${page.id}`, "patch", {
      properties: {
        "確認状態": { select: { name: "確認済み" } },
      },
    });
    flyerCount++;
  });

  let dealCount = 0;
  queryAllLifePages_(calendarDb).forEach(page => {
    const p = page.properties || {};
    if (notionSelect_(p["種類"]) !== "特売") return;

    const range = notionDateRange_(p["日付"]);
    const end = range.end || range.start;
    if (end && end < today) return;

    const state = notionSelect_(p["確認状態"]);
    const active = notionCheckbox_(p["有効"], false);
    if (state === "確認済み" && active) return;

    notionRequest_(`https://api.notion.com/v1/pages/${page.id}`, "patch", {
      properties: {
        "確認状態": { select: { name: "確認済み" } },
        "有効": { checkbox: true },
        "更新日時": { date: { start: new Date().toISOString() } },
      },
    });
    dealCount++;
  });

  return { flyers: flyerCount, deals: dealCount };
}

function getTodayLifeFlyerDealsAuto_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const dbId = getFlyerNotionConfig_().databaseId;
  const deals = [];

  queryAllLifePages_(dbId).forEach(page => {
    const p = page.properties || {};
    if (notionSelect_(p["種類"]) !== "特売") return;
    if (!notionCheckbox_(p["有効"], false)) return;

    const range = notionDateRange_(p["日付"]);
    const end = range.end || range.start;
    if (!range.start || range.start > today || end < today) return;

    deals.push({
      product: notionTitle_(p["予定名"]) || "特売商品",
      price: notionRichText_(p["価格"]),
      unit: notionRichText_(p["容量・単位"]),
      notes: notionRichText_(p["備考"]),
      priority: notionNumber_(p["優先度"], 2),
      start_date: range.start,
      end_date: end,
      sourceUrl: notionUrl_(p["元画像URL"]) || notionUrl_(p["チラシURL"]),
    });
  });

  return deals
    .sort((a, b) => a.priority - b.priority || a.product.localeCompare(b.product, "ja"))
    .slice(0, FLYER_MAX_DEALS_PER_DAY);
}

function sendLifeFlyerAutoSyncNotice_(flyers) {
  if (!flyers || flyers.length === 0) return;

  const lines = [
    "🆕 サミットの新しいチラシを自動反映しました",
    "",
    "確認操作は不要です。解析できた特売は生活カレンダーとLINE特売へ自動反映しています。",
    "",
  ];

  flyers.slice(0, 8).forEach(f => {
    lines.push(`・${f.type} / ID ${f.id}`);
    lines.push(`  ${f.start_date}${f.end_date !== f.start_date ? "〜" + f.end_date : ""}`);
    lines.push(`  ${f.deals.length}件`);
  });

  lines.push("", "※価格・在庫は店頭表示を優先してください。");
  pushFlyerTextToLine_(lines.join("\n").slice(0, 4800));
}

// 既存の毎日トリガーを自動反映モードへ置き換える。
// この関数を1回だけ手動実行してください。
function installDailySummitLifeCalendarAutoTrigger() {
  const oldNames = [
    "runDailySummitLifeCalendarAutomation",
    "runDailySummitFlyerAutomation",
    "runDailySummitFlyerNotionAutomation",
    "runDailySummitFlyerCatalogAutomation",
    "runDailySummitFlyerCatalogReviewedAutomation",
    LIFE_FLYER_AUTO_TRIGGER_FUNCTION,
  ];

  ScriptApp.getProjectTriggers().forEach(trigger => {
    const name = trigger.getHandlerFunction ? trigger.getHandlerFunction() : "";
    if (oldNames.indexOf(name) >= 0) ScriptApp.deleteTrigger(trigger);
  });

  ScriptApp.newTrigger(LIFE_FLYER_AUTO_TRIGGER_FUNCTION)
    .timeBased()
    .everyDays(1)
    .atHour(6)
    .create();

  Logger.log("毎日6時台のサミットチラシ自動反映トリガーへ置き換えました。");
}

// Gemini解析をせず、現在Notionにある確認待ちデータの自動有効化と今日の通知だけをテストする。
function testSummitLifeCalendarAutoMode() {
  const activated = autoActivateLifeFlyers_();
  const deals = getTodayLifeFlyerDealsAuto_();
  Logger.log(JSON.stringify({ activated: activated, todayDeals: deals.length }, null, 2));
  sendTodaySummitDealsToLine_(deals);
  return { activated: activated, todayDeals: deals.length };
}
