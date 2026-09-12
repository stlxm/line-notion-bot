// サミットのチラシ一覧・月間チラシ・確認フロー・生活カレンダー連携
// gas/FlyerDeals.gs と同じApps Scriptプロジェクトに置いてください。
//
// 必須 Script Properties:
//   GEMINI_API_KEY
//   NOTION_API_KEY
//   NOTION_FLYER_DATABASE_ID       // 生活カレンダーDB ID（互換名を継続利用）
//   NOTION_FLYER_LIST_DATABASE_ID  // チラシ一覧DB ID
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN
//
// 実行入口:
//   runDailySummitLifeCalendarAutomation
//
// 安全方針:
//   新しいチラシを解析しても、最初は生活カレンダーへ「確認待ち / 有効=false」で保存する。
//   Notion「チラシ一覧」で確認状態を「確認済み」にしたチラシだけ有効化し、毎朝LINE通知へ採用する。

const SUMMIT_SHUFOO_CATALOG_URL = "https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore";
const LIFE_FLYER_SIGNATURE_KEY = "SUMMIT_LIFE_FLYER_CATALOG_SIGNATURE_V1";
const LIFE_FLYER_MAX_IMAGES = 8;

function runDailySummitLifeCalendarAutomation() {
  Logger.log("--- サミット→生活カレンダー 開始 ---");

  const snapshot = collectLifeFlyerSnapshot_();
  const props = PropertiesService.getScriptProperties();
  const previousSignature = props.getProperty(LIFE_FLYER_SIGNATURE_KEY) || "";

  if (!snapshot.signature || snapshot.signature !== previousSignature) {
    const analyzed = analyzeLifeFlyersWithGemini_(snapshot);
    const sync = syncLifeFlyers_(analyzed.flyers || []);
    Logger.log(`[チラシ同期] flyers=${sync.flyers} / calendar=${sync.deals}`);

    if (snapshot.signature && (analyzed.flyers || []).length > 0) {
      props.setProperty(LIFE_FLYER_SIGNATURE_KEY, snapshot.signature);
      sendLifeFlyerReviewNotice_(analyzed.flyers || []);
    }
  } else {
    Logger.log("チラシ一覧に変更がないためGemini解析を省略しました。");
  }

  const review = applyLifeFlyerReviews_();
  disableExpiredLifeFlyerEvents_();
  Logger.log(`[確認状態反映] 確認済み=${review.confirmed} / 要修正=${review.rejected}`);

  const deals = getTodayConfirmedLifeFlyerDeals_();
  sendTodaySummitDealsToLine_(deals);
  Logger.log(`今日の確認済み特売: ${deals.length}件`);
  Logger.log("--- サミット→生活カレンダー 完了 ---");
}

// 画像取得とGemini解析だけ。Notion・LINEは変更しない。
function testSummitLifeFlyerParse() {
  const snapshot = collectLifeFlyerSnapshot_();
  const analyzed = analyzeLifeFlyersWithGemini_(snapshot);
  Logger.log(JSON.stringify({
    sourceUrl: snapshot.sourceUrl,
    imageUrls: snapshot.images.map(x => x.url),
    flyers: analyzed.flyers || [],
  }, null, 2));
}

// チラシ一覧DB・生活カレンダーへの確認待ち登録までテストする。
function testSummitLifeFlyerSync() {
  const snapshot = collectLifeFlyerSnapshot_();
  const analyzed = analyzeLifeFlyersWithGemini_(snapshot);
  const result = syncLifeFlyers_(analyzed.flyers || []);
  Logger.log(JSON.stringify(result, null, 2));
}

// Notionで「確認済み」に変更した後、生活カレンダーへ状態を即時反映する。
function applyLifeFlyerReviewsNow() {
  const result = applyLifeFlyerReviews_();
  Logger.log(JSON.stringify(result, null, 2));
  return result;
}

// 確認済みの今日の特売だけLINE通知する。
function testTodayLifeCalendarFlyerNotification() {
  const deals = getTodayConfirmedLifeFlyerDeals_();
  Logger.log(JSON.stringify(deals, null, 2));
  sendTodaySummitDealsToLine_(deals);
}

// 一度だけ実行。旧チラシ系トリガーを削除し、完成版の毎朝6時台トリガーへ統一する。
function installDailySummitLifeCalendarTrigger() {
  const newName = "runDailySummitLifeCalendarAutomation";
  const oldNames = [
    "runDailySummitFlyerAutomation",
    "runDailySummitFlyerNotionAutomation",
    "runDailySummitFlyerCatalogAutomation",
    "runDailySummitFlyerCatalogReviewedAutomation"
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
    Logger.log("毎日6時台の生活カレンダー連携トリガーを作成しました。");
  }
}

function getLifeFlyerListConfig_() {
  const databaseId = PropertiesService.getScriptProperties().getProperty("NOTION_FLYER_LIST_DATABASE_ID") || "";
  if (!databaseId) throw new Error("NOTION_FLYER_LIST_DATABASE_ID をScript Propertiesへ設定してください。");
  return { databaseId };
}

function collectLifeFlyerSnapshot_() {
  const htmlParts = [];
  let imageUrls = [];

  [SUMMIT_SHUFOO_CATALOG_URL, SUMMIT_FLYER_OFFICIAL_URL].forEach(url => {
    const response = fetchHtml_(url);
    if (!response.ok) return;
    htmlParts.push(response.html);
    imageUrls = imageUrls.concat(extractImageUrls_(response.html, url));

    extractIframeUrls_(response.html, url).slice(0, 4).forEach(childUrl => {
      const child = fetchHtml_(childUrl);
      if (!child.ok) return;
      htmlParts.push(child.html);
      imageUrls = imageUrls.concat(extractImageUrls_(child.html, childUrl));
    });
  });

  imageUrls = uniqueStrings_(imageUrls)
    .filter(isLikelyFlyerImageUrl_)
    .slice(0, LIFE_FLYER_MAX_IMAGES * 4);

  const images = fetchLifeFlyerImages_(imageUrls);
  const text = htmlToPlainText_(htmlParts.join("\n\n")).slice(0, 36000);
  const signature = sha256Hex_(
    [SUMMIT_SHUFOO_CATALOG_URL, text.slice(0, 14000)]
      .concat(images.map(x => x.url + ":" + x.bytes.length))
      .join("\n")
  );

  return { sourceUrl: SUMMIT_SHUFOO_CATALOG_URL, text, images, signature };
}

function fetchLifeFlyerImages_(urls) {
  const results = [];
  let total = 0;
  const maxTotal = 22 * 1024 * 1024;

  for (let i = 0; i < urls.length && results.length < LIFE_FLYER_MAX_IMAGES; i++) {
    try {
      const response = UrlFetchApp.fetch(urls[i], {
        method: "get",
        followRedirects: true,
        muteHttpExceptions: true,
        headers: { "User-Agent": "Mozilla/5.0" },
      });
      if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) continue;
      const blob = response.getBlob();
      const bytes = blob.getBytes();
      const contentType = String(blob.getContentType() || "").toLowerCase();
      if (!/^image\/(jpeg|jpg|png|webp)/.test(contentType)) continue;
      if (bytes.length < 15000 || bytes.length > FLYER_MAX_IMAGE_BYTES) continue;
      if (total + bytes.length > maxTotal) break;
      total += bytes.length;
      results.push({ url: urls[i], bytes, mimeType: contentType.replace("image/jpg", "image/jpeg") });
    } catch (e) {
      Logger.log(`[画像取得失敗] ${urls[i]}: ${e}`);
    }
  }
  return results;
}

function analyzeLifeFlyersWithGemini_(snapshot) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY") || "";
  const model = props.getProperty("FLYER_GEMINI_MODEL") || "gemini-3.5-flash-lite";
  if (!apiKey) throw new Error("GEMINI_API_KEY をScript Propertiesへ設定してください。");

  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const prompt = [
    "あなたはスーパーのチラシ一覧とチラシ画像を正確に整理するアシスタントです。",
    `対象店舗: ${SUMMIT_FLYER_STORE_NAME}`,
    `今日: ${today}`,
    "Shufoo/サミットのHTML本文と複数のチラシ画像から、別々のチラシを区別してください。",
    "月初から月末近くまで有効な長期チラシはtype=月間、約1週間は週次、1〜2日中心は日替わり、それ以外はその他。",
    "チラシ名・掲載期間・商品・価格・容量・対象日は画像か本文で読める内容だけを使い、推測で補わないでください。",
    "商品ごとに根拠画像URLをimage_urlへ入れてください。画像URLは下記一覧から選んでください。",
    "同じ商品の重複は同一チラシ内でまとめ、各チラシ最大40商品。説明文なしのJSONだけを返してください。",
    '{"flyers":[{"title":"チラシ名","type":"月間|週次|日替わり|その他","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","image_urls":["https://..."],"deals":[{"product":"商品名","price":"価格","unit":"容量・単位","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","notes":"条件","priority":1,"image_url":"https://..."}]}]}',
    "priority: 1=目立つ日替わり/大幅値引き、2=通常特売、3=長期キャンペーン。",
    "",
    "【取得画像URL】",
    (snapshot.images || []).map((x, i) => `${i + 1}. ${x.url}`).join("\n"),
    "",
    "【ページ本文】",
    (snapshot.text || "").slice(0, 32000),
  ].join("\n");

  const parts = [{ text: prompt }];
  (snapshot.images || []).forEach(image => {
    parts.push({ inlineData: { mimeType: image.mimeType, data: Utilities.base64Encode(image.bytes) } });
  });

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      contents: [{ role: "user", parts }],
      generationConfig: { temperature: 0.05, responseMimeType: "application/json" },
    }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  const body = response.getContentText();
  if (code < 200 || code >= 300) throw new Error(`Gemini flyer analysis failed: ${code} ${body.slice(0, 500)}`);

  const outer = JSON.parse(body);
  const outParts = (((outer.candidates || [])[0] || {}).content || {}).parts || [];
  const parsed = JSON.parse(stripJsonFence_(outParts.map(x => x.text || "").join("").trim()));
  return { flyers: sanitizeLifeFlyers_(parsed.flyers || []) };
}

function sanitizeLifeFlyers_(flyers) {
  if (!Array.isArray(flyers)) return [];
  const allowed = { "月間": true, "週次": true, "日替わり": true, "その他": true };

  return flyers.slice(0, 12).map((flyer, index) => {
    const title = String(flyer.title || `チラシ ${index + 1}`).trim().slice(0, 180);
    const start = normalizeDateString_(flyer.start_date);
    const end = normalizeDateString_(flyer.end_date || flyer.start_date);
    const type = allowed[flyer.type] ? flyer.type : inferLifeFlyerType_(start, end);
    const imageUrls = uniqueStrings_((flyer.image_urls || [])
      .map(x => String(x || "").trim())
      .filter(x => /^https?:\/\//.test(x)))
      .slice(0, 8);

    const deals = (Array.isArray(flyer.deals) ? flyer.deals : []).map(item => {
      const startDate = normalizeDateString_(item.start_date || start);
      const endDate = normalizeDateString_(item.end_date || item.start_date || end || start);
      if (!item.product || !startDate || !endDate) return null;
      return {
        product: String(item.product).trim().slice(0, 120),
        price: String(item.price || "").trim().slice(0, 80),
        unit: String(item.unit || "").trim().slice(0, 80),
        start_date: startDate,
        end_date: endDate,
        notes: String(item.notes || "").trim().slice(0, 200),
        priority: Math.min(3, Math.max(1, Number(item.priority) || 2)),
        image_url: /^https?:\/\//.test(String(item.image_url || "")) ? String(item.image_url) : (imageUrls[0] || ""),
      };
    }).filter(Boolean);

    return { title, type, start_date: start, end_date: end || start, image_urls: imageUrls, deals };
  }).filter(x => x.start_date && x.end_date && x.image_urls.length > 0);
}

function inferLifeFlyerType_(start, end) {
  if (!start || !end) return "その他";
  const days = Math.round((new Date(end + "T00:00:00+09:00") - new Date(start + "T00:00:00+09:00")) / 86400000) + 1;
  if (days >= 20) return "月間";
  if (days >= 4) return "週次";
  if (days <= 2) return "日替わり";
  return "その他";
}

function syncLifeFlyers_(flyers) {
  let flyerCount = 0;
  let dealCount = 0;

  (flyers || []).forEach(flyer => {
    const flyerKey = sha256Hex_([
      SUMMIT_FLYER_STORE_NAME, flyer.title, flyer.type, flyer.start_date, flyer.end_date,
      (flyer.image_urls || []).join("|")
    ].join("|"));

    upsertLifeFlyerListPage_(flyer, flyerKey);
    dealCount += upsertLifeCalendarDeals_(flyer, flyerKey);
    flyerCount++;
  });

  return { flyers: flyerCount, deals: dealCount };
}

function upsertLifeFlyerListPage_(flyer, flyerKey) {
  const dbId = getLifeFlyerListConfig_().databaseId;
  const existing = findLifePageByRichText_(dbId, "チラシ識別", flyerKey);
  const currentState = existing ? notionSelect_((existing.properties || {})["確認状態"]) : "";
  const dateObj = { start: flyer.start_date };
  if (flyer.end_date && flyer.end_date !== flyer.start_date) dateObj.end = flyer.end_date;

  const properties = {
    "チラシ名": { title: [{ text: { content: flyer.title } }] },
    "種別": { select: { name: flyer.type || "その他" } },
    "掲載期間": { date: dateObj },
    "元URL": { url: SUMMIT_SHUFOO_CATALOG_URL },
    "画像URL": { url: (flyer.image_urls || [])[0] || null },
    "画像一覧": { rich_text: richTextContent_((flyer.image_urls || []).join("\n")) },
    "抽出件数": { number: Number((flyer.deals || []).length) },
    "抽出サマリー": { rich_text: richTextContent_(buildLifeFlyerSummary_(flyer.deals || [])) },
    "確認状態": { select: { name: currentState || "確認待ち" } },
    "チラシ識別": { rich_text: richTextContent_(flyerKey) },
    "取得日時": { date: { start: new Date().toISOString() } },
  };

  if (existing) {
    notionRequest_(`https://api.notion.com/v1/pages/${existing.id}`, "patch", { properties });
  } else {
    notionRequest_("https://api.notion.com/v1/pages", "post", {
      parent: { database_id: dbId }, properties,
    });
  }
}

function buildLifeFlyerSummary_(deals) {
  return (deals || []).slice(0, 20).map(deal => {
    let line = deal.product || "商品";
    if (deal.price) line += ` ${deal.price}`;
    if (deal.unit) line += ` / ${deal.unit}`;
    if (deal.start_date) line += ` [${deal.start_date}${deal.end_date && deal.end_date !== deal.start_date ? "〜" + deal.end_date : ""}]`;
    return line;
  }).join("\n").slice(0, 1800);
}

function upsertLifeCalendarDeals_(flyer, flyerKey) {
  const dbId = getFlyerNotionConfig_().databaseId;
  let count = 0;

  (flyer.deals || []).forEach(deal => {
    const key = sha256Hex_([
      "特売", SUMMIT_FLYER_STORE_NAME, flyerKey, deal.product, deal.price, deal.unit,
      deal.start_date, deal.end_date
    ].join("|"));
    const existing = findLifePageByRichText_(dbId, "識別キー", key);
    const currentState = existing ? notionSelect_((existing.properties || {})["確認状態"]) : "";
    const dateObj = { start: deal.start_date };
    if (deal.end_date && deal.end_date !== deal.start_date) dateObj.end = deal.end_date;
    const imageUrl = deal.image_url || (flyer.image_urls || [])[0] || "";

    const properties = {
      "予定名": { title: [{ text: { content: deal.product || "特売商品" } }] },
      "日付": { date: dateObj },
      "種類": { select: { name: "特売" } },
      "内容": { rich_text: richTextContent_([deal.price, deal.unit, deal.notes].filter(Boolean).join(" / ")) },
      "価格": { rich_text: richTextContent_(deal.price) },
      "容量・単位": { rich_text: richTextContent_(deal.unit) },
      "店舗": { select: { name: SUMMIT_FLYER_STORE_NAME } },
      "備考": { rich_text: richTextContent_(deal.notes) },
      "優先度": { number: Number(deal.priority || 2) },
      "チラシURL": { url: SUMMIT_SHUFOO_CATALOG_URL },
      "チラシ識別": { rich_text: richTextContent_(flyerKey) },
      "識別キー": { rich_text: richTextContent_(key) },
      "元チラシ名": { rich_text: richTextContent_(flyer.title) },
      "元画像URL": { url: imageUrl || null },
      "確認状態": { select: { name: currentState || "確認待ち" } },
      "有効": { checkbox: currentState === "確認済み" },
      "更新日時": { date: { start: new Date().toISOString() } },
    };

    if (existing) {
      notionRequest_(`https://api.notion.com/v1/pages/${existing.id}`, "patch", { properties });
    } else {
      notionRequest_("https://api.notion.com/v1/pages", "post", {
        parent: { database_id: dbId }, properties,
      });
    }
    count++;
  });
  return count;
}

function applyLifeFlyerReviews_() {
  const listDb = getLifeFlyerListConfig_().databaseId;
  const calendarDb = getFlyerNotionConfig_().databaseId;
  const states = {};

  queryAllLifePages_(listDb).forEach(page => {
    const props = page.properties || {};
    const key = notionRichText_(props["チラシ識別"]);
    const state = notionSelect_(props["確認状態"]);
    if (key && state) states[key] = state;
  });

  let confirmed = 0;
  let rejected = 0;
  queryAllLifePages_(calendarDb).forEach(page => {
    const props = page.properties || {};
    if (notionSelect_(props["種類"]) !== "特売") return;
    const flyerKey = notionRichText_(props["チラシ識別"]);
    const state = states[flyerKey];
    if (!state || state === "確認待ち") return;

    const active = state === "確認済み";
    notionRequest_(`https://api.notion.com/v1/pages/${page.id}`, "patch", {
      properties: {
        "確認状態": { select: { name: state } },
        "有効": { checkbox: active },
        "更新日時": { date: { start: new Date().toISOString() } },
      },
    });
    if (active) confirmed++; else rejected++;
  });

  return { confirmed, rejected };
}

function disableExpiredLifeFlyerEvents_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const dbId = getFlyerNotionConfig_().databaseId;

  queryAllLifePages_(dbId).forEach(page => {
    const props = page.properties || {};
    if (notionSelect_(props["種類"]) !== "特売") return;
    if (!notionCheckbox_(props["有効"], false)) return;
    const range = notionDateRange_(props["日付"]);
    if (!range.end || range.end >= today) return;

    notionRequest_(`https://api.notion.com/v1/pages/${page.id}`, "patch", {
      properties: {
        "有効": { checkbox: false },
        "更新日時": { date: { start: new Date().toISOString() } },
      },
    });
  });
}

function getTodayConfirmedLifeFlyerDeals_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const dbId = getFlyerNotionConfig_().databaseId;
  const deals = [];

  queryAllLifePages_(dbId).forEach(page => {
    const props = page.properties || {};
    if (notionSelect_(props["種類"]) !== "特売") return;
    if (notionSelect_(props["店舗"]) !== SUMMIT_FLYER_STORE_NAME) return;
    if (!notionCheckbox_(props["有効"], false)) return;
    if (notionSelect_(props["確認状態"]) !== "確認済み") return;

    const range = notionDateRange_(props["日付"]);
    if (!range.start) return;
    const end = range.end || range.start;
    if (range.start > today || end < today) return;

    deals.push({
      product: notionTitle_(props["予定名"]) || "特売商品",
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

function queryAllLifePages_(databaseId) {
  let cursor = null;
  const pages = [];
  do {
    const payload = { page_size: 100 };
    if (cursor) payload.start_cursor = cursor;
    const data = notionRequest_(`https://api.notion.com/v1/databases/${databaseId}/query`, "post", payload);
    pages.push.apply(pages, data.results || []);
    cursor = data.has_more ? data.next_cursor : null;
  } while (cursor && pages.length < 1000);
  return pages;
}

function findLifePageByRichText_(databaseId, propertyName, value) {
  const data = notionRequest_(`https://api.notion.com/v1/databases/${databaseId}/query`, "post", {
    page_size: 1,
    filter: { property: propertyName, rich_text: { equals: value } },
  });
  return (data.results || [])[0] || null;
}

function sendLifeFlyerReviewNotice_(flyers) {
  if (!flyers || flyers.length === 0) return;
  const lines = [
    "🆕 新しいサミットのチラシを読み取りました",
    "",
    "Notionの『チラシ一覧 → 確認待ち』で画像と抽出内容を確認してください。",
    "確認済みにしたチラシだけ生活カレンダーと毎朝通知で有効になります。",
    ""
  ];

  flyers.slice(0, 6).forEach(flyer => {
    lines.push(`・${flyer.title}（${flyer.type} / ${(flyer.deals || []).length}件）`);
    if (flyer.start_date) lines.push(`  ${flyer.start_date}${flyer.end_date && flyer.end_date !== flyer.start_date ? "〜" + flyer.end_date : ""}`);
    if ((flyer.image_urls || [])[0]) lines.push(`  画像: ${(flyer.image_urls || [])[0]}`);
  });

  pushFlyerTextToLine_(lines.join("\n").slice(0, 4800));
}
