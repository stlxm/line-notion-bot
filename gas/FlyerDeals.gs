// サミット ミナノ分倍河原店のチラシ自動取得・Googleカレンダー登録・LINE日次通知
//
// 対象店舗（公式）:
//   https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer
// 店舗名:
//   サミット ミナノ分倍河原店
//
// 必須 Script Properties:
//   GEMINI_API_KEY
//   LINE_USER_ID
//   LINE_CHANNEL_ACCESS_TOKEN
//
// 任意 Script Properties:
//   FLYER_GEMINI_MODEL  既定: gemini-3.5-flash-lite
//   FLYER_CALENDAR_ID   未設定ならGoogleのデフォルトカレンダー
//
// 推奨:
//   runDailySummitFlyerAutomation を毎日6〜7時台に時間主導型トリガーで実行
//
// この機能は1日1回程度の取得を前提としています。サイトへ高頻度アクセスしないでください。

const SUMMIT_FLYER_OFFICIAL_URL = "https://www.summitstore.co.jp/store/tokyo/post/?id=151#flyer";
const SUMMIT_FLYER_TOKUBAI_URL = "https://tokubai.co.jp/%E3%82%B5%E3%83%9F%E3%83%83%E3%83%88/7221";
const SUMMIT_FLYER_STORE_NAME = "サミット ミナノ分倍河原店";
const FLYER_CACHE_KEY = "SUMMIT_FLYER_LAST_RESULT_V1";
const FLYER_SIGNATURE_KEY = "SUMMIT_FLYER_LAST_SIGNATURE_V1";
const FLYER_EVENT_MARKER = "[SUMMIT_FLYER_AUTOMATION]";
const FLYER_MAX_IMAGES = 6;
const FLYER_MAX_IMAGE_BYTES = 6 * 1024 * 1024;
const FLYER_MAX_TOTAL_IMAGE_BYTES = 18 * 1024 * 1024;
const FLYER_MAX_DEALS_PER_DAY = 12;

function runDailySummitFlyerAutomation() {
  Logger.log("--- サミットチラシ自動処理 開始 ---");

  const result = getOrAnalyzeSummitFlyer_();
  syncSummitDealsToCalendar_(result.deals || []);
  sendTodaySummitDealsToLine_(result.deals || [], result.sourceUrl || SUMMIT_FLYER_OFFICIAL_URL);

  Logger.log(`解析結果: ${(result.deals || []).length}件 / source=${result.sourceUrl || "unknown"}`);
  Logger.log("--- サミットチラシ自動処理 完了 ---");
}

// 初回確認用。カレンダー更新・LINE送信はせず、解析結果だけログへ出します。
function testSummitFlyerParse() {
  const result = analyzeSummitFlyer_(true);
  Logger.log(JSON.stringify(result, null, 2));
}

// 初回確認用。実際にカレンダー更新とLINE通知まで実行します。
function testSummitFlyerAutomation() {
  runDailySummitFlyerAutomation();
}

// 一度だけ実行すると、毎日6時台に自動実行するトリガーを作成します。
function installDailySummitFlyerTrigger() {
  const functionName = "runDailySummitFlyerAutomation";
  const exists = ScriptApp.getProjectTriggers().some(trigger =>
    trigger.getHandlerFunction && trigger.getHandlerFunction() === functionName
  );
  if (exists) {
    Logger.log("チラシ自動処理トリガーはすでに存在します。");
    return;
  }

  ScriptApp.newTrigger(functionName)
    .timeBased()
    .everyDays(1)
    .atHour(6)
    .create();

  Logger.log("毎日6時台のチラシ自動処理トリガーを作成しました。");
}

function getOrAnalyzeSummitFlyer_() {
  const snapshot = collectSummitFlyerSnapshot_();
  const props = PropertiesService.getScriptProperties();
  const previousSignature = props.getProperty(FLYER_SIGNATURE_KEY) || "";
  const cached = readFlyerCache_();

  if (snapshot.signature && snapshot.signature === previousSignature && cached) {
    cached.reusedCache = true;
    return cached;
  }

  const result = analyzeSnapshotWithGemini_(snapshot);
  result.sourceUrl = snapshot.sourceUrl || SUMMIT_FLYER_OFFICIAL_URL;
  result.reusedCache = false;

  if ((result.deals || []).length > 0) {
    writeFlyerCache_(result);
    if (snapshot.signature) {
      props.setProperty(FLYER_SIGNATURE_KEY, snapshot.signature);
    }
    return result;
  }

  // 新しいページの解析に失敗しても、直前の正常結果をすぐ捨てない。
  if (cached) {
    cached.reusedCache = true;
    cached.analysisWarning = "最新チラシ解析で特売を抽出できなかったため、直前の正常結果を再利用しました。";
    return cached;
  }

  return result;
}

function analyzeSummitFlyer_(forceRefresh) {
  if (!forceRefresh) return getOrAnalyzeSummitFlyer_();
  const snapshot = collectSummitFlyerSnapshot_();
  const result = analyzeSnapshotWithGemini_(snapshot);
  result.sourceUrl = snapshot.sourceUrl || SUMMIT_FLYER_OFFICIAL_URL;
  return result;
}

function collectSummitFlyerSnapshot_() {
  const official = fetchHtml_(SUMMIT_FLYER_OFFICIAL_URL);
  let sourceUrl = SUMMIT_FLYER_OFFICIAL_URL;
  let htmlParts = [];
  let imageUrls = [];

  if (official.ok) {
    htmlParts.push(official.html);
    const iframeUrls = extractIframeUrls_(official.html, SUMMIT_FLYER_OFFICIAL_URL).slice(0, 3);
    iframeUrls.forEach(url => {
      const child = fetchHtml_(url);
      if (!child.ok) return;
      sourceUrl = url;
      htmlParts.push(child.html);
      imageUrls = imageUrls.concat(extractImageUrls_(child.html, url));
    });
    imageUrls = imageUrls.concat(extractImageUrls_(official.html, SUMMIT_FLYER_OFFICIAL_URL));
  }

  // 公式側のiframeはJavaScript依存になることがあるため、公開されている同店舗の
  // トクバイページを低頻度のフォールバックとして使う。
  if (imageUrls.length < 2) {
    const tokubai = fetchHtml_(SUMMIT_FLYER_TOKUBAI_URL);
    if (tokubai.ok) {
      sourceUrl = SUMMIT_FLYER_TOKUBAI_URL;
      htmlParts.push(tokubai.html);
      imageUrls = imageUrls.concat(extractImageUrls_(tokubai.html, SUMMIT_FLYER_TOKUBAI_URL));
    }
  }

  imageUrls = uniqueStrings_(imageUrls)
    .filter(isLikelyFlyerImageUrl_)
    .slice(0, FLYER_MAX_IMAGES * 3);

  const images = fetchCandidateImages_(imageUrls);
  const text = htmlToPlainText_(htmlParts.join("\n\n")).slice(0, 28000);
  const signatureMaterial = [sourceUrl, text.slice(0, 12000)]
    .concat(images.map(x => x.url + ":" + x.bytes.length))
    .join("\n");

  return {
    sourceUrl: sourceUrl,
    text: text,
    images: images,
    signature: sha256Hex_(signatureMaterial),
  };
}

function fetchHtml_(url) {
  try {
    const response = UrlFetchApp.fetch(url, {
      method: "get",
      followRedirects: true,
      muteHttpExceptions: true,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; LINE-Notion-Bot-Flyer/1.0; personal-use)",
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
    const normalized = match[0].replace(/\\\//g, "/").replace(/&amp;/g, "&");
    urls.push(normalized);
  }

  return uniqueStrings_(urls);
}

function normalizeUrl_(url, baseUrl) {
  if (!url) return "";
  let value = String(url).trim().replace(/&amp;/g, "&").replace(/\\\//g, "/");
  if (!value || value.startsWith("data:") || value.startsWith("javascript:")) return "";
  if (value.startsWith("//")) return "https:" + value;
  if (/^https?:\/\//i.test(value)) return value;

  try {
    const base = String(baseUrl || "").match(/^(https?):\/\/([^/]+)(\/.*)?$/i);
    if (!base) return "";
    const origin = `${base[1]}://${base[2]}`;
    if (value.startsWith("/")) return origin + value;

    let path = (base[3] || "/").split("?")[0].split("#")[0];
    path = path.substring(0, path.lastIndexOf("/") + 1);
    return origin + path + value;
  } catch (e) {
    return "";
  }
}

function isLikelyFlyerImageUrl_(url) {
  const lower = String(url || "").toLowerCase();
  if (!/^https?:\/\//.test(lower)) return false;
  if (!/\.(?:jpg|jpeg|png|webp)(?:\?|$)/.test(lower)) return false;
  if (/(logo|icon|favicon|sprite|button|bnr|banner|qr|appstore|googleplay|publisher)/.test(lower)) return false;
  return true;
}

function fetchCandidateImages_(urls) {
  const results = [];
  let totalBytes = 0;

  for (let i = 0; i < urls.length && results.length < FLYER_MAX_IMAGES; i++) {
    const url = urls[i];
    try {
      const response = UrlFetchApp.fetch(url, {
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
      if (totalBytes + bytes.length > FLYER_MAX_TOTAL_IMAGE_BYTES) break;

      totalBytes += bytes.length;
      results.push({ url: url, bytes: bytes, mimeType: contentType.replace("image/jpg", "image/jpeg") });
    } catch (e) {
      Logger.log(`[画像取得失敗] ${url}: ${e}`);
    }
  }

  return results;
}

function analyzeSnapshotWithGemini_(snapshot) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY") || "";
  const model = props.getProperty("FLYER_GEMINI_MODEL") || "gemini-3.5-flash-lite";
  if (!apiKey) {
    throw new Error("Script Properties に GEMINI_API_KEY を設定してください。");
  }

  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const prompt = [
    "あなたはスーパーのチラシを正確に読み取るアシスタントです。",
    `対象店舗: ${SUMMIT_FLYER_STORE_NAME}`,
    `今日: ${today}`,
    "提供されたWebページ本文とチラシ画像だけを根拠に、特売商品をJSONで抽出してください。",
    "推測で商品名・価格・日付を補わないでください。読めない項目はnullまたは空文字にしてください。",
    "通常価格ではなく、チラシ上で特売・お買得・日替わり・期間限定と判断できるものを優先してください。",
    "同じ商品が重複する場合は1件にまとめてください。",
    "価格は税込/税抜が分かればnotesへ残してください。",
    "日付指定が1日だけならstart_date=end_dateにしてください。期間指定なら両方を設定してください。",
    "月だけ書かれていて年がない場合は、今日とチラシ期間から自然に一意に決められる場合だけ年を補ってください。",
    "最大40件まで。",
    "出力は説明文なしのJSONのみ。形式:",
    '{"deals":[{"product":"商品名","price":"価格表記","unit":"容量・単位","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","notes":"条件や税込/税抜等","priority":1}]}',
    "priorityは目立つ日替わり/大幅値引き=1、通常の特売=2、長期キャンペーン=3。",
    "",
    "【ページ本文】",
    (snapshot.text || "").slice(0, 26000),
  ].join("\n");

  const parts = [{ text: prompt }];
  (snapshot.images || []).forEach(image => {
    parts.push({
      inlineData: {
        mimeType: image.mimeType,
        data: Utilities.base64Encode(image.bytes),
      },
    });
  });

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const payload = {
    contents: [{ role: "user", parts: parts }],
    generationConfig: {
      temperature: 0.1,
      responseMimeType: "application/json",
    },
  };

  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  const body = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error(`Gemini flyer analysis failed: ${code} ${body.slice(0, 500)}`);
  }

  let parsed;
  try {
    const outer = JSON.parse(body);
    const text = (((outer.candidates || [])[0] || {}).content || {}).parts || [];
    const joined = text.map(x => x.text || "").join("").trim();
    parsed = JSON.parse(stripJsonFence_(joined));
  } catch (e) {
    throw new Error(`GeminiのJSON解析に失敗しました: ${e}`);
  }

  const deals = sanitizeDeals_(parsed.deals || []);
  return { deals: deals, analyzedAt: new Date().toISOString(), model: model };
}

function stripJsonFence_(text) {
  return String(text || "")
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/```\s*$/i, "")
    .trim();
}

function sanitizeDeals_(items) {
  if (!Array.isArray(items)) return [];
  const seen = {};
  const deals = [];

  items.forEach(item => {
    if (!item || !item.product) return;
    const start = normalizeDateString_(item.start_date);
    const end = normalizeDateString_(item.end_date || item.start_date);
    if (!start || !end) return;

    const product = String(item.product).trim().slice(0, 120);
    const price = String(item.price || "").trim().slice(0, 80);
    const unit = String(item.unit || "").trim().slice(0, 80);
    const notes = String(item.notes || "").trim().slice(0, 200);
    const priority = Math.min(3, Math.max(1, Number(item.priority) || 2));
    const key = [product, price, unit, start, end].join("|");
    if (seen[key]) return;
    seen[key] = true;

    deals.push({
      product: product,
      price: price,
      unit: unit,
      start_date: start,
      end_date: end,
      notes: notes,
      priority: priority,
    });
  });

  return deals.slice(0, 40);
}

function normalizeDateString_(value) {
  const text = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return "";
  const date = new Date(text + "T00:00:00+09:00");
  if (isNaN(date.getTime())) return "";
  return text;
}

function syncSummitDealsToCalendar_(deals) {
  const calendar = getFlyerCalendar_();
  const grouped = groupDealsByDate_(deals);
  const dates = Object.keys(grouped).sort();

  dates.forEach(dateStr => {
    const date = new Date(dateStr + "T00:00:00+09:00");
    const dayDeals = grouped[dateStr]
      .sort((a, b) => a.priority - b.priority || a.product.localeCompare(b.product, "ja"))
      .slice(0, FLYER_MAX_DEALS_PER_DAY);

    // 自動作成した同日の古いイベントだけ消して更新する。
    calendar.getEventsForDay(date).forEach(event => {
      if ((event.getDescription() || "").indexOf(FLYER_EVENT_MARKER) >= 0) {
        event.deleteEvent();
      }
    });

    const title = `🛒 サミット特売（${dayDeals.length}件）`;
    const description = buildCalendarDescription_(dateStr, dayDeals);
    calendar.createAllDayEvent(title, date, { description: description });
  });

  // 過去7日〜未来31日のうち、現在の解析結果に存在しない自動イベントを掃除する。
  cleanupObsoleteFlyerEvents_(calendar, grouped);
}

function getFlyerCalendar_() {
  const calendarId = PropertiesService.getScriptProperties().getProperty("FLYER_CALENDAR_ID") || "";
  if (!calendarId) return CalendarApp.getDefaultCalendar();
  const calendar = CalendarApp.getCalendarById(calendarId);
  if (!calendar) throw new Error("FLYER_CALENDAR_ID のGoogleカレンダーが見つかりません。");
  return calendar;
}

function groupDealsByDate_(deals) {
  const grouped = {};
  const today = new Date();
  const minDate = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const maxDate = new Date(today.getTime() + 31 * 24 * 60 * 60 * 1000);

  (deals || []).forEach(deal => {
    let cursor = new Date(deal.start_date + "T00:00:00+09:00");
    const end = new Date(deal.end_date + "T00:00:00+09:00");
    let guard = 0;
    while (cursor <= end && guard < 40) {
      if (cursor >= minDate && cursor <= maxDate) {
        const dateStr = Utilities.formatDate(cursor, "Asia/Tokyo", "yyyy-MM-dd");
        grouped[dateStr] = grouped[dateStr] || [];
        grouped[dateStr].push(deal);
      }
      cursor = new Date(cursor.getTime() + 24 * 60 * 60 * 1000);
      guard++;
    }
  });

  return grouped;
}

function buildCalendarDescription_(dateStr, deals) {
  const lines = [
    FLYER_EVENT_MARKER,
    `${SUMMIT_FLYER_STORE_NAME} / ${dateStr}`,
    "",
  ];
  deals.forEach(deal => {
    let line = `・${deal.product}`;
    if (deal.price) line += ` ${deal.price}`;
    if (deal.unit) line += ` / ${deal.unit}`;
    lines.push(line);
    if (deal.notes) lines.push(`  ${deal.notes}`);
  });
  lines.push("", `公式: ${SUMMIT_FLYER_OFFICIAL_URL}`, `参考: ${SUMMIT_FLYER_TOKUBAI_URL}`);
  lines.push("価格・在庫は店頭表示を優先してください。");
  return lines.join("\n");
}

function cleanupObsoleteFlyerEvents_(calendar, grouped) {
  const start = new Date();
  start.setDate(start.getDate() - 7);
  const end = new Date();
  end.setDate(end.getDate() + 32);

  calendar.getEvents(start, end).forEach(event => {
    if ((event.getDescription() || "").indexOf(FLYER_EVENT_MARKER) < 0) return;
    const dateStr = Utilities.formatDate(event.getStartTime(), "Asia/Tokyo", "yyyy-MM-dd");
    if (!grouped[dateStr]) {
      event.deleteEvent();
    }
  });
}

function sendTodaySummitDealsToLine_(deals, sourceUrl) {
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const todaysDeals = (deals || []).filter(deal => deal.start_date <= today && deal.end_date >= today)
    .sort((a, b) => a.priority - b.priority || a.product.localeCompare(b.product, "ja"))
    .slice(0, FLYER_MAX_DEALS_PER_DAY);

  const lines = [`🛒 ${SUMMIT_FLYER_STORE_NAME}`, `【${today} の特売】`, ""];
  if (todaysDeals.length === 0) {
    lines.push("今日の特売商品をチラシから抽出できませんでした。", "店舗チラシを直接確認してください。");
  } else {
    todaysDeals.forEach(deal => {
      let line = `・${deal.product}`;
      if (deal.price) line += ` ${deal.price}`;
      if (deal.unit) line += ` / ${deal.unit}`;
      lines.push(line);
      if (deal.notes) lines.push(`  ${deal.notes}`);
    });
  }
  lines.push("", `チラシ: ${SUMMIT_FLYER_OFFICIAL_URL}`);
  lines.push("※価格・在庫は店頭表示を優先してください。");

  pushFlyerTextToLine_(lines.join("\n").slice(0, 4800));
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
    payload: JSON.stringify({
      to: userId,
      messages: [{ type: "text", text: text }],
    }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`LINE flyer notification failed: ${code} ${response.getContentText().slice(0, 500)}`);
  }
}

function writeFlyerCache_(result) {
  const compact = {
    deals: (result.deals || []).slice(0, 40),
    sourceUrl: result.sourceUrl || SUMMIT_FLYER_OFFICIAL_URL,
    analyzedAt: result.analyzedAt || new Date().toISOString(),
    model: result.model || "",
  };
  const json = JSON.stringify(compact);
  // Script Propertyのサイズを超えないように、超過時は件数を減らして保存。
  if (json.length <= 8500) {
    PropertiesService.getScriptProperties().setProperty(FLYER_CACHE_KEY, json);
    return;
  }
  compact.deals = compact.deals.slice(0, 20);
  PropertiesService.getScriptProperties().setProperty(FLYER_CACHE_KEY, JSON.stringify(compact));
}

function readFlyerCache_() {
  const raw = PropertiesService.getScriptProperties().getProperty(FLYER_CACHE_KEY) || "";
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.deals)) return null;
    return parsed;
  } catch (e) {
    return null;
  }
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
