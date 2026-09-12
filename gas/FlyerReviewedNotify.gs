// 確認済みチラシだけを特売通知へ採用する安全な日次入口。
// FlyerDeals.gs / FlyerReview.gs と同じApps Scriptプロジェクトに置いてください。

function runDailySummitFlyerCatalogReviewedAutomation() {
  Logger.log("--- サミット チラシ一覧+確認済み通知 開始 ---");

  const snapshot = collectSummitFlyerCatalogSnapshot_();
  const props = PropertiesService.getScriptProperties();
  const previousSignature = props.getProperty(FLYER_CATALOG_SIGNATURE_KEY) || "";

  if (!snapshot.signature || snapshot.signature !== previousSignature) {
    const analyzed = analyzeSummitFlyerCatalogWithGemini_(snapshot);
    const sync = syncAnalyzedFlyers_(analyzed.flyers || []);
    Logger.log(`[チラシ一覧同期] flyers=${(analyzed.flyers || []).length} / list=${sync.flyers} / deals=${sync.deals}`);
    if (snapshot.signature && (analyzed.flyers || []).length > 0) {
      props.setProperty(FLYER_CATALOG_SIGNATURE_KEY, snapshot.signature);
      sendFlyerReviewNoticeToLine_(analyzed.flyers || []);
    }
  } else {
    Logger.log("チラシ一覧に変更がないため画像解析を省略しました。");
  }

  const reviewResult = applyFlyerReviewStates_();
  cleanupExpiredCatalogDeals_();
  Logger.log(`[確認状態反映] 確認済み=${reviewResult.confirmed} / 要修正=${reviewResult.rejected}`);

  const todayDeals = getTodayConfirmedSummitDealsFromNotion_();
  sendTodaySummitDealsToLine_(todayDeals);
  Logger.log(`今日の確認済み特売: ${todayDeals.length}件`);
  Logger.log("--- サミット チラシ一覧+確認済み通知 完了 ---");
}

function getTodayConfirmedSummitDealsFromNotion_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const dbId = getFlyerNotionConfig_().databaseId;
  const deals = [];

  queryAllPagesForDb_(dbId).forEach(page => {
    const props = page.properties || {};
    if (notionSelect_(props["店舗"]) !== SUMMIT_FLYER_STORE_NAME) return;
    if (!notionCheckbox_(props["有効"], false)) return;
    if (notionSelect_(props["確認状態"]) !== "確認済み") return;

    const range = notionDateRange_(props["特売日"]);
    if (!range.start) return;
    const end = range.end || range.start;
    if (range.start > today || end < today) return;

    deals.push({
      product: notionTitle_(props["商品名"]) || "特売商品",
      price: notionRichText_(props["価格"]),
      unit: notionRichText_(props["容量・単位"]),
      notes: notionRichText_(props["備考"]),
      priority: notionNumber_(props["優先度"], 2),
      start_date: range.start,
      end_date: end,
      sourceUrl: notionUrl_(props["元画像URL"]) || notionUrl_(props["チラシURL"]) || SUMMIT_SHUFOO_CATALOG_URL,
    });
  });

  return deals
    .sort((a, b) => a.priority - b.priority || a.product.localeCompare(b.product, "ja"))
    .slice(0, FLYER_MAX_DEALS_PER_DAY);
}

function testTodayConfirmedSummitFlyerNotification() {
  const deals = getTodayConfirmedSummitDealsFromNotion_();
  Logger.log(JSON.stringify(deals, null, 2));
  sendTodaySummitDealsToLine_(deals);
}

function installDailySummitFlyerReviewedTrigger() {
  const newName = "runDailySummitFlyerCatalogReviewedAutomation";
  const oldNames = [
    "runDailySummitFlyerAutomation",
    "runDailySummitFlyerNotionAutomation",
    "runDailySummitFlyerCatalogAutomation"
  ];
  let hasNew = false;

  ScriptApp.getProjectTriggers().forEach(trigger => {
    const name = trigger.getHandlerFunction ? trigger.getHandlerFunction() : "";
    if (oldNames.indexOf(name) >= 0) {
      ScriptApp.deleteTrigger(trigger);
      Logger.log(`旧チラシトリガーを削除: ${name}`);
    }
    if (name === newName) hasNew = true;
  });

  if (!hasNew) {
    ScriptApp.newTrigger(newName).timeBased().everyDays(1).atHour(6).create();
    Logger.log("毎日6時台の確認済みチラシ通知トリガーを作成しました。");
  }
}
