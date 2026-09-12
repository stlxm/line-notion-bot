// サミットのチラシ一覧・生活カレンダー連携（Shufoo配信ID単位）
// gas/FlyerDeals.gs と同じApps Scriptプロジェクトに置いてください。
//
// 方針:
// - Shufooの /shop/264241/<配信ID>/ を1チラシとして扱う
// - 配信IDごとにページ・画像を取得し、Geminiも個別解析
// - 新規チラシは確認待ち / 有効=false
// - Notion「チラシ一覧」で確認済みにしたものだけ生活カレンダーで有効化

const SUMMIT_SHUFOO_ROOT_URL = "https://asp.shufoo.net/t/asp_iframe/shop/264241/?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore";
const SUMMIT_SHUFOO_SEED_URL = "https://asp.shufoo.net/t/asp_iframe/shop/264241/9783726841844?lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore";
const LIFE_FLYER_SIGNATURE_KEY = "SUMMIT_LIFE_FLYER_CATALOG_SIGNATURE_V2";
const LIFE_FLYER_MAX_IDS = 12;
const LIFE_FLYER_MAX_IMAGES_PER_ID = 4;

function runDailySummitLifeCalendarAutomation() {
  Logger.log("--- サミット→生活カレンダー 開始 ---");
  const catalog = collectShufooFlyerCatalog_();
  const props = PropertiesService.getScriptProperties();
  const previousSignature = props.getProperty(LIFE_FLYER_SIGNATURE_KEY) || "";

  if (!catalog.signature || catalog.signature !== previousSignature) {
    const flyers = analyzeShufooFlyersById_(catalog);
    const sync = syncLifeFlyers_(flyers);
    Logger.log(`[チラシ同期] flyers=${sync.flyers} / calendar=${sync.deals}`);
    if (catalog.signature && flyers.length > 0) {
      props.setProperty(LIFE_FLYER_SIGNATURE_KEY, catalog.signature);
      sendLifeFlyerReviewNotice_(flyers);
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
}

function testSummitLifeFlyerParse() {
  const catalog = collectShufooFlyerCatalog_();
  Logger.log("検出した配信ID: " + JSON.stringify(catalog.flyerPages.map(x => x.id)));
  const flyers = analyzeShufooFlyersById_(catalog);
  Logger.log(JSON.stringify({
    sourceUrl: catalog.sourceUrl,
    flyerPages: catalog.flyerPages.map(x => ({ id: x.id, url: x.url, imageUrls: x.images.map(i => i.url) })),
    flyers: flyers,
  }, null, 2));
}

function testSummitLifeFlyerSync() {
  const catalog = collectShufooFlyerCatalog_();
  const flyers = analyzeShufooFlyersById_(catalog);
  const result = syncLifeFlyers_(flyers);
  Logger.log(JSON.stringify(result, null, 2));
}

function applyLifeFlyerReviewsNow() {
  const result = applyLifeFlyerReviews_();
  Logger.log(JSON.stringify(result, null, 2));
  return result;
}

function testTodayLifeCalendarFlyerNotification() {
  const deals = getTodayConfirmedLifeFlyerDeals_();
  Logger.log(JSON.stringify(deals, null, 2));
  sendTodaySummitDealsToLine_(deals);
}

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
    if (oldNames.indexOf(name) >= 0) ScriptApp.deleteTrigger(trigger);
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

function collectShufooFlyerCatalog_() {
  const discoveryUrls = [SUMMIT_SHUFOO_ROOT_URL, SUMMIT_SHUFOO_SEED_URL, SUMMIT_FLYER_OFFICIAL_URL];
  const htmlParts = [];
  let flyerUrls = [];

  discoveryUrls.forEach(url => {
    const response = fetchHtml_(url);
    if (!response.ok) return;
    htmlParts.push(response.html);
    flyerUrls = flyerUrls.concat(extractShufooFlyerUrls_(response.html, url));
  });

  flyerUrls = uniqueStrings_(flyerUrls).slice(0, LIFE_FLYER_MAX_IDS);
  if (flyerUrls.length === 0) {
    const seedId = extractShufooFlyerId_(SUMMIT_SHUFOO_SEED_URL);
    flyerUrls.push({ id: seedId, url: SUMMIT_SHUFOO_SEED_URL });
  }

  const flyerPages = [];
  flyerUrls.forEach(entry => {
    const page = collectSingleShufooFlyerPage_(entry.id, entry.url);
    if (page) flyerPages.push(page);
  });

  const signatureMaterial = flyerPages.map(page => [
    page.id,
    page.url,
    page.text.slice(0, 6000),
    page.images.map(x => x.url + ":" + x.bytes.length).join("|")
  ].join("\n")).join("\n---\n");

  return {
    sourceUrl: SUMMIT_SHUFOO_ROOT_URL,
    flyerPages: flyerPages,
    signature: sha256Hex_(signatureMaterial),
  };
}

function extractShufooFlyerUrls_(html, baseUrl) {
  const results = [];
  const seen = {};
  const source = String(html || "").replace(/\\\//g, "/");
  const patterns = [
    /(?:https?:\/\/asp\.shufoo\.net)?\/t\/asp_iframe\/shop\/264241\/(\d{6,})\/?[^\s"'<>]*/gi,
    /(?:href|data-url|data-href)\s*=\s*["']([^"']*\/shop\/264241\/(\d{6,})\/?[^"']*)["']/gi,
  ];

  patterns.forEach((regex, pIndex) => {
    let match;
    while ((match = regex.exec(source)) !== null) {
      const id = pIndex === 0 ? match[1] : match[2];
      let url = pIndex === 0 ? match[0] : match[1];
      if (!id || seen[id]) continue;
      url = normalizeUrl_(url, baseUrl);
      if (!url) continue;
      if (url.indexOf("lp-chirashi=") < 0) {
        url += (url.indexOf("?") >= 0 ? "&" : "?") + "lp-chirashi=true&lp-timeline=true&lp-pickup=true&lp-coupon=true&lp-event=true&lp-shop-detail=false&un=summitstore";
      }
      seen[id] = true;
      results.push({ id: id, url: url });
    }
  });

  return results;
}

function extractShufooFlyerId_(url) {
  const match = String(url || "").match(/\/shop\/264241\/(\d{6,})/);
  return match ? match[1] : "";
}

function collectSingleShufooFlyerPage_(id, url) {
  const response = fetchHtml_(url);
  if (!response.ok) return null;

  let htmlParts = [response.html];
  let imageUrls = extractImageUrls_(response.html, url);
  extractIframeUrls_(response.html, url).slice(0, 3).forEach(childUrl => {
    const child = fetchHtml_(childUrl);
    if (!child.ok) return;
    htmlParts.push(child.html);
    imageUrls = imageUrls.concat(extractImageUrls_(child.html, childUrl));
  });

  imageUrls = uniqueStrings_(imageUrls)
    .filter(isLikelyFlyerImageUrl_)
    .slice(0, LIFE_FLYER_MAX_IMAGES_PER_ID * 4);

  const images = fetchLifeFlyerImages_(imageUrls, LIFE_FLYER_MAX_IMAGES_PER_ID);
  const text = htmlToPlainText_(htmlParts.join("\n\n")).slice(0, 24000);

  return { id: id, url: url, text: text, images: images };
}

function fetchLifeFlyerImages_(urls, limit) {
  const results = [];
  let total = 0;
  const maxTotal = 14 * 1024 * 1024;
  const maxImages = limit || LIFE_FLYER_MAX_IMAGES_PER_ID;
  for (let i = 0; i < urls.length && results.length < maxImages; i++) {
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
      results.push({ url: urls[i], bytes: bytes, mimeType: contentType.replace("image/jpg", "image/jpeg") });
    } catch (e) {
      Logger.log(`[画像取得失敗] ${urls[i]}: ${e}`);
    }
  }
  return results;
}

function analyzeShufooFlyersById_(catalog) {
  const flyers = [];
  (catalog.flyerPages || []).forEach(page => {
    const flyer = analyzeSingleShufooFlyerWithGemini_(page);
    if (flyer) flyers.push(flyer);
  });
  return flyers;
}

function analyzeSingleShufooFlyerWithGemini_(page) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY") || "";
  const model = props.getProperty("FLYER_GEMINI_MODEL") || "gemini-3.5-flash-lite";
  if (!apiKey) throw new Error("GEMINI_API_KEY をScript Propertiesへ設定してください。");

  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const prompt = [
    "あなたはスーパーのチラシを正確に読み取るアシスタントです。",
    `対象店舗: ${SUMMIT_FLYER_STORE_NAME}`,
    `今日: ${today}`,
    `Shufoo配信ID: ${page.id}`,
    "この入力は1つの配信IDだけです。別のチラシと混ぜず、この配信IDだけを解析してください。",
    "名前よりも掲載期間と内容を優先し、typeは期間に基づき 月間/週次/日替わり/その他 のいずれかにしてください。",
    "20日以上なら月間、4〜19日なら週次、1〜2日中心なら日替わり、それ以外はその他。",
    "商品名・価格・容量・対象日は画像または本文で読める内容だけを使い、推測で補わないでください。",
    "各商品に根拠画像URLをimage_urlへ入れてください。",
    "説明文なしのJSONだけを返してください。",
    '{"title":"表示用タイトル","type":"月間|週次|日替わり|その他","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","deals":[{"product":"商品名","price":"価格","unit":"容量・単位","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","notes":"条件","priority":1,"image_url":"https://..."}]}',
    "",
    "【画像URL一覧】",
    (page.images || []).map((x, i) => `${i + 1}. ${x.url}`).join("\n"),
    "",
    "【ページ本文】",
    (page.text || "").slice(0, 22000),
  ].join("\n");

  const parts = [{ text: prompt }];
  (page.images || []).forEach(image => {
    parts.push({ inlineData: { mimeType: image.mimeType, data: Utilities.base64Encode(image.bytes) } });
  });

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      contents: [{ role: "user", parts: parts }],
      generationConfig: { temperature: 0.05, responseMimeType: "application/json" },
    }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  const body = response.getContentText();
  if (code < 200 || code >= 300) throw new Error(`Gemini flyer analysis failed (${page.id}): ${code} ${body.slice(0, 500)}`);

  const outer = JSON.parse(body);
  const outParts = (((outer.candidates || [])[0] || {}).content || {}).parts || [];
  const parsed = JSON.parse(stripJsonFence_(outParts.map(x => x.text || "").join("").trim()));
  return sanitizeSingleLifeFlyer_(parsed, page);
}

function sanitizeSingleLifeFlyer_(raw, page) {
  raw = raw || {};
  const start = normalizeDateString_(raw.start_date);
  const end = normalizeDateString_(raw.end_date || raw.start_date);
  if (!start || !end) return null;
  const allowed = { "月間": true, "週次": true, "日替わり": true, "その他": true };
  const type = allowed[raw.type] ? raw.type : inferLifeFlyerType_(start, end);
  const imageUrls = (page.images || []).map(x => x.url);
  const deals = (Array.isArray(raw.deals) ? raw.deals : []).map(item => {
    const startDate = normalizeDateString_(item.start_date || start);
    const endDate = normalizeDateString_(item.end_date || item.start_date || end || start);
    if (!item.product || !startDate || !endDate) return null;
    const imageUrl = /^https?:\/\//.test(String(item.image_url || "")) ? String(item.image_url) : (imageUrls[0] || "");
    return {
      product: String(item.product).trim().slice(0, 120),
      price: String(item.price || "").trim().slice(0, 80),
      unit: String(item.unit || "").trim().slice(0, 80),
      start_date: startDate,
      end_date: endDate,
      notes: String(item.notes || "").trim().slice(0, 200),
      priority: Math.min(3, Math.max(1, Number(item.priority) || 2)),
      image_url: imageUrl,
    };
  }).filter(Boolean);

  return {
    id: page.id,
    source_url: page.url,
    title: String(raw.title || `${type}チラシ ${page.id}`).trim().slice(0, 180),
    type: type,
    start_date: start,
    end_date: end,
    image_urls: imageUrls,
    deals: deals.slice(0, 40),
  };
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
    const flyerKey = sha256Hex_([SUMMIT_FLYER_STORE_NAME, flyer.id, flyer.start_date, flyer.end_date].join("|"));
    upsertLifeFlyerListPage_(flyer, flyerKey);
    dealCount += upsertLifeCalendarDeals_(flyer, flyerKey);
    flyerCount++;
  });
  return { flyers: flyerCount, deals: dealCount };
}

function upsertLifeFlyerListPage_(flyer, flyerKey) {
  const dbId = getLifeFlyerListConfig_().databaseId;
  const existing = findLifePageByRichText_(dbId, "配信ID", flyer.id) || findLifePageByRichText_(dbId, "チラシ識別", flyerKey);
  const currentState = existing ? notionSelect_((existing.properties || {})["確認状態"]) : "";
  const dateObj = { start: flyer.start_date };
  if (flyer.end_date !== flyer.start_date) dateObj.end = flyer.end_date;
  const summary = buildLifeFlyerSummary_(flyer.deals || []);
  const props = {
    "チラシ名": { title: [{ text: { content: flyer.title } }] },
    "配信ID": { rich_text: richTextContent_(flyer.id) },
    "種別": { select: { name: flyer.type } },
    "掲載期間": { date: dateObj },
    "元URL": { url: flyer.source_url },
    "画像URL": { url: (flyer.image_urls || [])[0] || null },
    "画像一覧": { rich_text: richTextContent_((flyer.image_urls || []).join("\n")) },
    "抽出件数": { number: Number((flyer.deals || []).length) },
    "抽出サマリー": { rich_text: richTextContent_(summary) },
    "確認状態": { select: { name: currentState || "確認待ち" } },
    "チラシ識別": { rich_text: richTextContent_(flyerKey) },
    "取得日時": { date: { start: new Date().toISOString() } },
  };
  if (existing) {
    notionRequest_(`https://api.notion.com/v1/pages/${existing.id}`, "patch", { properties: props });
  } else {
    notionRequest_("https://api.notion.com/v1/pages", "post", { parent: { database_id: dbId }, properties: props });
  }
}

function buildLifeFlyerSummary_(deals) {
  return (deals || []).slice(0, 20).map(d => {
    let line = d.product || "商品";
    if (d.price) line += ` ${d.price}`;
    if (d.unit) line += ` / ${d.unit}`;
    if (d.start_date) line += ` [${d.start_date}${d.end_date && d.end_date !== d.start_date ? "〜" + d.end_date : ""}]`;
    return line;
  }).join("\n").slice(0, 1800);
}

function upsertLifeCalendarDeals_(flyer, flyerKey) {
  const dbId = getFlyerNotionConfig_().databaseId;
  let count = 0;
  (flyer.deals || []).forEach(deal => {
    const key = sha256Hex_([SUMMIT_FLYER_STORE_NAME, flyer.id, deal.product, deal.price, deal.unit, deal.start_date, deal.end_date].join("|"));
    const existing = findLifePageByRichText_(dbId, "識別キー", key);
    const currentState = existing ? notionSelect_((existing.properties || {})["確認状態"]) : "";
    const dateObj = { start: deal.start_date };
    if (deal.end_date !== deal.start_date) dateObj.end = deal.end_date;
    const props = {
      "予定名": { title: [{ text: { content: deal.product || "特売商品" } }] },
      "日付": { date: dateObj },
      "種類": { select: { name: "特売" } },
      "価格": { rich_text: richTextContent_(deal.price) },
      "容量・単位": { rich_text: richTextContent_(deal.unit) },
      "内容": { rich_text: richTextContent_([deal.price, deal.unit].filter(Boolean).join(" / ")) },
      "店舗": { select: { name: SUMMIT_FLYER_STORE_NAME } },
      "備考": { rich_text: richTextContent_(deal.notes) },
      "優先度": { number: Number(deal.priority || 2) },
      "チラシURL": { url: flyer.source_url },
      "チラシ識別": { rich_text: richTextContent_(flyerKey) },
      "識別キー": { rich_text: richTextContent_(key) },
      "元チラシID": { rich_text: richTextContent_(flyer.id) },
      "元チラシ名": { rich_text: richTextContent_(flyer.title) },
      "元画像URL": { url: deal.image_url || (flyer.image_urls || [])[0] || null },
      "確認状態": { select: { name: currentState || "確認待ち" } },
      "有効": { checkbox: currentState === "確認済み" },
      "更新日時": { date: { start: new Date().toISOString() } },
    };
    if (existing) {
      notionRequest_(`https://api.notion.com/v1/pages/${existing.id}`, "patch", { properties: props });
    } else {
      notionRequest_("https://api.notion.com/v1/pages", "post", { parent: { database_id: dbId }, properties: props });
    }
    count++;
  });
  return count;
}

function applyLifeFlyerReviews_() {
  const listDb = getLifeFlyerListConfig_().databaseId;
  const calendarDb = getFlyerNotionConfig_().databaseId;
  const listPages = queryAllLifePages_(listDb);
  const calendarPages = queryAllLifePages_(calendarDb);
  const statesById = {};

  listPages.forEach(page => {
    const p = page.properties || {};
    const id = notionRichText_(p["配信ID"]);
    const state = notionSelect_(p["確認状態"]);
    if (id && state) statesById[id] = state;
  });

  let confirmed = 0;
  let rejected = 0;
  calendarPages.forEach(page => {
    const p = page.properties || {};
    if (notionSelect_(p["種類"]) !== "特売") return;
    const id = notionRichText_(p["元チラシID"]);
    const state = statesById[id];
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
    const p = page.properties || {};
    if (notionSelect_(p["種類"]) !== "特売") return;
    if (!notionCheckbox_(p["有効"], false)) return;
    const range = notionDateRange_(p["日付"]);
    if (!range.end || range.end >= today) return;
    notionRequest_(`https://api.notion.com/v1/pages/${page.id}`, "patch", { properties: { "有効": { checkbox: false } } });
  });
}

function getTodayConfirmedLifeFlyerDeals_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const dbId = getFlyerNotionConfig_().databaseId;
  const deals = [];
  queryAllLifePages_(dbId).forEach(page => {
    const p = page.properties || {};
    if (notionSelect_(p["種類"]) !== "特売") return;
    if (!notionCheckbox_(p["有効"], false)) return;
    if (notionSelect_(p["確認状態"]) !== "確認済み") return;
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
  return deals.sort((a, b) => a.priority - b.priority || a.product.localeCompare(b.product, "ja")).slice(0, FLYER_MAX_DEALS_PER_DAY);
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
  if (!value) return null;
  const data = notionRequest_(`https://api.notion.com/v1/databases/${databaseId}/query`, "post", {
    page_size: 1,
    filter: { property: propertyName, rich_text: { equals: value } },
  });
  return (data.results || [])[0] || null;
}

function sendLifeFlyerReviewNotice_(flyers) {
  if (!flyers || flyers.length === 0) return;
  const lines = ["🆕 サミットのチラシを読み取りました", "", "Notion『チラシ一覧 → 確認待ち』で画像と内容を確認してください。", ""];
  flyers.slice(0, 8).forEach(f => {
    lines.push(`・${f.type} / ID ${f.id}`);
    lines.push(`  ${f.start_date}${f.end_date !== f.start_date ? "〜" + f.end_date : ""}`);
    lines.push(`  ${f.deals.length}件`);
  });
  lines.push("", "確認済みにした配信IDだけ、生活カレンダーと毎朝通知で有効になります。");
  pushFlyerTextToLine_(lines.join("\n").slice(0, 4800));
}
