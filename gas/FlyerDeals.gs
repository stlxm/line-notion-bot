// サミット ミナノ分倍河原店: チラシ共通関数 + LINE通知
//
// 現在の取得・解析・Notion同期の本体は FlyerLifeCalendar.gs です。
// このファイルは以下だけを担当します。
// - Web/画像/Notion/LINE の共通ヘルパー
// - 生活カレンダーから「今日の確認済み特売」を読み取る
// - 通知前の重複整理
// - 短期特売を優先したLINE通知
//
// Apps Scriptでは FlyerLifeCalendar.gs と同じプロジェクトに置いてください。

const SUMMIT_FLYER_OFFICIAL_URL = "https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer";
const SUMMIT_FLYER_STORE_NAME = "サミット ミナノ分倍河原店";
const FLYER_MAX_IMAGE_BYTES = 6 * 1024 * 1024;
const FLYER_MAX_DEALS_PER_DAY = 20;
const NOTION_API_VERSION = "2022-06-28";

// -----------------------------------------------------------------------------
// 旧入口の互換ラッパー
// -----------------------------------------------------------------------------

function runDailySummitFlyerAutomation() {
  if (typeof runDailySummitLifeCalendarAutomation !== "function") {
    throw new Error("FlyerLifeCalendar.gs が見つかりません。");
  }
  return runDailySummitLifeCalendarAutomation();
}

function testSummitFlyerAutomation() {
  if (typeof testSummitLifeFlyerSync !== "function") {
    throw new Error("FlyerLifeCalendar.gs が見つかりません。");
  }
  return testSummitLifeFlyerSync();
}

function testSummitFlyerParse() {
  if (typeof testSummitLifeFlyerParse !== "function") {
    throw new Error("FlyerLifeCalendar.gs が見つかりません。");
  }
  return testSummitLifeFlyerParse();
}

function installDailySummitFlyerTrigger() {
  if (typeof installDailySummitLifeCalendarTrigger !== "function") {
    throw new Error("FlyerLifeCalendar.gs が見つかりません。");
  }
  return installDailySummitLifeCalendarTrigger();
}

// Notionの今日分だけを読み、LINE通知だけ試す。
function testTodaySummitFlyerNotification() {
  const deals = getTodaySummitDealsFromNotion_();
  Logger.log(JSON.stringify(deals, null, 2));
  sendTodaySummitDealsToLine_(deals);
}

// -----------------------------------------------------------------------------
// Web / 画像 共通処理
// -----------------------------------------------------------------------------

function fetchHtml_(url) {
  try {
    const response = UrlFetchApp.fetch(url, {
      method: "get",
      followRedirects: true,
      muteHttpExceptions: true,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; LINE-Notion-Bot-Flyer/3.0; personal-use)",
        "Accept-Language": "ja,en;q=0.8",
      },
    });
    const code = response.getResponseCode();
    if (code < 200 || code >= 300) {
      Logger.log(`[チラシ取得失敗] ${code} ${url}`);
      return { ok: false, html: "" };
    }
    return { ok: true, html: response.getContentText("UTF-8") };
  } catch (e) {
    Logger.log(`[チラシ取得例外] ${url}: ${e}`);
    return { ok: false, html: "" };
  }
}

function extractIframeUrls_(html, baseUrl) {
  const urls = [];
  const regex = /<iframe\b[^>]*?\bsrc\s*=\s*["']([^"']+)["'][^>]*>/gi;
  let match;
  while ((match = regex.exec(html || "")) !== null) {
    const url = normalizeUrl_(match[1], baseUrl);
    if (url) urls.push(url);
  }
  return uniqueStrings_(urls);
}

function extractImageUrls_(html, baseUrl) {
  const urls = [];
  const attrRegex = /\b(?:src|data-src|data-original|data-lazy|data-srcset)\s*=\s*["']([^"']+)["']/gi;
  let match;
  while ((match = attrRegex.exec(html || "")) !== null) {
    match[1].split(/\s*,\s*/).forEach(part => {
      const candidate = part.trim().split(/\s+/)[0];
      const normalized = normalizeUrl_(candidate, baseUrl);
      if (normalized) urls.push(normalized);
    });
  }

  const absoluteImageRegex = /https?:\\?\/\\?\/[^\s"'<>]+?\.(?:jpe?g|png|webp)(?:\?[^\s"'<>]*)?/gi;
  while ((match = absoluteImageRegex.exec(html || "")) !== null) {
    urls.push(match[0].replace(/\\\//g, "/").replace(/&amp;/g, "&"));
  }
  return uniqueStrings_(urls);
}

function normalizeUrl_(url, baseUrl) {
  if (!url) return "";
  let value = String(url).trim().replace(/&amp;/g, "&").replace(/\\\//g, "/");
  if (!value || value.startsWith("data:") || value.startsWith("javascript:")) return "";
  if (value.startsWith("//")) return "https:" + value;
  if (/^https?:\/\//i.test(value)) return value;

  const base = String(baseUrl || "").match(/^(https?):\/\/([^/]+)(\/.*)?$/i);
  if (!base) return "";
  const origin = `${base[1]}://${base[2]}`;
  if (value.startsWith("/")) return origin + value;

  let path = (base[3] || "/").split("?")[0].split("#")[0];
  path = path.substring(0, path.lastIndexOf("/") + 1);
  return origin + path + value;
}

function isLikelyFlyerImageUrl_(url) {
  const lower = String(url || "").toLowerCase();
  if (!/^https?:\/\//.test(lower)) return false;
  if (!/\.(?:jpg|jpeg|png|webp)(?:\?|$)/.test(lower)) return false;
  if (/(logo|icon|favicon|sprite|button|bnr|banner|qr|appstore|googleplay|publisher)/.test(lower)) return false;
  return true;
}

function htmlToPlainText_(html) {
  return String(html || "")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, "\n")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/gi, '"')
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function uniqueStrings_(items) {
  const seen = {};
  return (items || []).filter(value => {
    const key = String(value || "");
    if (!key || seen[key]) return false;
    seen[key] = true;
    return true;
  });
}

function stripJsonFence_(text) {
  return String(text || "")
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/```\s*$/i, "")
    .trim();
}

function normalizeDateString_(value) {
  const text = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return "";
  const date = new Date(text + "T00:00:00+09:00");
  return isNaN(date.getTime()) ? "" : text;
}

function sha256Hex_(text) {
  const digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    String(text || ""),
    Utilities.Charset.UTF_8
  );
  return digest.map(byte => {
    const value = byte < 0 ? byte + 256 : byte;
    return ("0" + value.toString(16)).slice(-2);
  }).join("");
}

// -----------------------------------------------------------------------------
// Notion 共通処理
// -----------------------------------------------------------------------------

function getFlyerNotionConfig_() {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("NOTION_API_KEY") || "";
  const databaseId = props.getProperty("NOTION_FLYER_DATABASE_ID") || "";
  if (!apiKey || !databaseId) {
    throw new Error("Script Properties に NOTION_API_KEY と NOTION_FLYER_DATABASE_ID を設定してください。");
  }
  return { apiKey: apiKey, databaseId: databaseId };
}

function notionHeaders_() {
  const config = getFlyerNotionConfig_();
  return {
    Authorization: `Bearer ${config.apiKey}`,
    "Notion-Version": NOTION_API_VERSION,
    "Content-Type": "application/json",
  };
}

function notionRequest_(url, method, payload) {
  const options = {
    method: method || "get",
    headers: notionHeaders_(),
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
    throw new Error(`Notion API failed: ${code} ${body.slice(0, 700)}`);
  }
  return body ? JSON.parse(body) : {};
}

function queryAllFlyerPages_() {
  const config = getFlyerNotionConfig_();
  let cursor = null;
  const pages = [];
  do {
    const payload = { page_size: 100 };
    if (cursor) payload.start_cursor = cursor;
    const data = notionRequest_(
      `https://api.notion.com/v1/databases/${config.databaseId}/query`,
      "post",
      payload
    );
    pages.push.apply(pages, data.results || []);
    cursor = data.has_more ? data.next_cursor : null;
  } while (cursor && pages.length < 1000);
  return pages;
}

function richTextContent_(value) {
  const text = String(value || "").slice(0, 1800);
  return text ? [{ text: { content: text } }] : [];
}

function notionTitle_(prop) {
  if (!prop || !Array.isArray(prop.title)) return "";
  return prop.title.map(x => x.plain_text || (x.text || {}).content || "").join("");
}

function notionRichText_(prop) {
  if (!prop || !Array.isArray(prop.rich_text)) return "";
  return prop.rich_text.map(x => x.plain_text || (x.text || {}).content || "").join("");
}

function notionSelect_(prop) {
  return prop && prop.select ? String(prop.select.name || "") : "";
}

function notionCheckbox_(prop, fallback) {
  return prop && typeof prop.checkbox === "boolean" ? prop.checkbox : Boolean(fallback);
}

function notionNumber_(prop, fallback) {
  return prop && typeof prop.number === "number" ? prop.number : Number(fallback || 0);
}

function notionUrl_(prop) {
  return prop && prop.url ? String(prop.url) : "";
}

function notionDateRange_(prop) {
  if (!prop || !prop.date) return { start: "", end: "" };
  return {
    start: String(prop.date.start || "").slice(0, 10),
    end: String(prop.date.end || prop.date.start || "").slice(0, 10),
  };
}

// -----------------------------------------------------------------------------
// 今日の特売: 生活カレンダーを正本として読む
// -----------------------------------------------------------------------------

function getTodaySummitDealsFromNotion_() {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const pages = queryAllFlyerPages_();
  const deals = [];

  pages.forEach(page => {
    const props = page.properties || {};

    if (notionSelect_(props["店舗"]) !== SUMMIT_FLYER_STORE_NAME) return;
    if (!notionCheckbox_(props["有効"], false)) return;

    const kind = notionSelect_(props["種類"]);
    if (kind && kind !== "特売") return;

    const reviewState = notionSelect_(props["確認状態"]);
    if (reviewState && reviewState !== "確認済み") return;

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
      sourceUrl:
        notionUrl_(props["元画像URL"]) ||
        notionUrl_(props["チラシURL"]) ||
        SUMMIT_FLYER_OFFICIAL_URL,
    });
  });

  const uniqueDeals = dedupeSummitNotificationDeals_(deals);

  uniqueDeals.sort((a, b) => {
    const aDays = flyerDealSpanDays_(a);
    const bDays = flyerDealSpanDays_(b);
    if (aDays !== bDays) return aDays - bDays;
    if (a.priority !== b.priority) return a.priority - b.priority;
    return a.product.localeCompare(b.product, "ja");
  });

  Logger.log(`[Notion今日分] ${today} / 元=${deals.length}件 / 重複整理後=${uniqueDeals.length}件`);
  return uniqueDeals.slice(0, FLYER_MAX_DEALS_PER_DAY);
}

function flyerDealSpanDays_(deal) {
  const start = String((deal || {}).start_date || "");
  const end = String((deal || {}).end_date || start);
  if (!start || !end) return 9999;

  const startDate = new Date(start + "T00:00:00+09:00");
  const endDate = new Date(end + "T00:00:00+09:00");
  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) return 9999;
  return Math.round((endDate - startDate) / 86400000) + 1;
}

function normalizeSummitNotificationProduct_(value) {
  let text = String(value || "").trim();
  try {
    text = text.normalize("NFKC");
  } catch (e) {}

  return text
    .replace(/[（(][^）)]*[）)]/g, "")
    .replace(/ケース購入/g, "")
    .replace(/1ケース/g, "")
    .replace(/ケース/g, "")
    .replace(/[\s　]+/g, "")
    .toLowerCase();
}

function normalizeSummitNotificationPrice_(value) {
  return String(value || "")
    .replace(/,/g, "")
    .replace(/[円￥¥\s　]/g, "")
    .trim();
}

function normalizeSummitNotificationPackage_(product, unit) {
  let text = `${product || ""} ${unit || ""}`;
  try {
    text = text.normalize("NFKC");
  } catch (e) {}
  text = text.toLowerCase().replace(/[\s　]/g, "");

  // 350ml×24 / 500ml×6 / 400g など、商品を区別する容量情報を優先。
  const multi = text.match(/\d+(?:\.\d+)?(?:ml|l|g|kg)×\d+(?:本|缶|個|袋|パック)?/i);
  if (multi) return multi[0];

  const single = text.match(/\d+(?:\.\d+)?(?:ml|l|g|kg)/i);
  if (single) return single[0];

  return "";
}

function chooseBetterSummitNotificationDeal_(a, b) {
  const aDays = flyerDealSpanDays_(a);
  const bDays = flyerDealSpanDays_(b);

  // 同じ商品が月間と短期の両方にある場合は、今日に近い短期情報を残す。
  if (aDays !== bDays) return aDays < bDays ? a : b;

  const aLimited = /限り|限定|のみ/.test(String(a.notes || ""));
  const bLimited = /限り|限定|のみ/.test(String(b.notes || ""));
  if (aLimited !== bLimited) return aLimited ? a : b;

  if (String(a.notes || "").length !== String(b.notes || "").length) {
    return String(a.notes || "").length > String(b.notes || "").length ? a : b;
  }

  if (String(a.unit || "").length !== String(b.unit || "").length) {
    return String(a.unit || "").length > String(b.unit || "").length ? a : b;
  }

  return a;
}

function dedupeSummitNotificationDeals_(deals) {
  const byKey = {};

  (deals || []).forEach(deal => {
    const productKey = normalizeSummitNotificationProduct_(deal.product);
    const priceKey = normalizeSummitNotificationPrice_(deal.price);
    const packageKey = normalizeSummitNotificationPackage_(deal.product, deal.unit);
    const key = [productKey, priceKey, packageKey].join("|");

    if (!byKey[key]) {
      byKey[key] = deal;
      return;
    }

    byKey[key] = chooseBetterSummitNotificationDeal_(byKey[key], deal);
  });

  return Object.keys(byKey).map(key => byKey[key]);
}

// -----------------------------------------------------------------------------
// LINE通知
// -----------------------------------------------------------------------------

function sendTodaySummitDealsToLine_(todaysDeals) {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const lines = [
    `🛒 ${SUMMIT_FLYER_STORE_NAME}`,
    `【${today} の特売】`,
    "",
  ];

  if (!todaysDeals || todaysDeals.length === 0) {
    lines.push(
      "今日の確認済み特売はNotionに登録されていません。",
      "必要なら店舗チラシを直接確認してください。"
    );
  } else {
    const shortDeals = todaysDeals.filter(deal => flyerDealSpanDays_(deal) <= 7);
    const longDeals = todaysDeals.filter(deal => flyerDealSpanDays_(deal) > 7);

    if (shortDeals.length > 0) {
      lines.push("🔥 今日・短期特売");
      shortDeals.forEach(deal => appendSummitDealLine_(lines, deal));
      lines.push("");
    }

    if (longDeals.length > 0) {
      lines.push("📅 月間・長期特売");
      longDeals.forEach(deal => appendSummitDealLine_(lines, deal));
      lines.push("");
    }

    lines.push(`今日の通知: ${todaysDeals.length}件`);
  }

  lines.push(
    "",
    `チラシ: ${SUMMIT_FLYER_OFFICIAL_URL}`,
    "※価格・在庫は店頭表示を優先してください。"
  );

  pushFlyerTextToLine_(lines.join("\n").slice(0, 4800));
}

function appendSummitDealLine_(lines, deal) {
  let line = `・${deal.product}`;
  if (deal.price) line += ` ${deal.price}`;
  if (deal.unit) line += ` / ${deal.unit}`;
  lines.push(line);

  if (deal.notes) {
    lines.push(`  ${deal.notes}`);
  } else if (deal.start_date && deal.end_date && deal.start_date !== deal.end_date) {
    lines.push(`  ${deal.start_date}〜${deal.end_date}`);
  }
}

function pushFlyerTextToLine_(text) {
  const props = PropertiesService.getScriptProperties();
  const userId = props.getProperty("LINE_USER_ID") || "";
  const accessToken = props.getProperty("LINE_CHANNEL_ACCESS_TOKEN") || "";
  if (!userId || !accessToken) {
    throw new Error("Script Properties に LINE_USER_ID と LINE_CHANNEL_ACCESS_TOKEN を設定してください。");
  }

  const response = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: `Bearer ${accessToken}` },
    payload: JSON.stringify({ to: userId, messages: [{ type: "text", text: text }] }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`LINE flyer notification failed: ${code} ${response.getContentText().slice(0, 500)}`);
  }
}
