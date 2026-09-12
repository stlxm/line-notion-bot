// FlyerLifeCalendar.gs の解析欠落を安全に診断・救済する暫定リカバリー版。
// FlyerDeals.gs / FlyerLifeCalendar.gs と同じApps Scriptプロジェクトに置く。
// 検出済み配信IDを1件ずつ解析し、トップレベル日付が欠けた場合は商品日付から期間を復元する。

function testSummitLifeFlyerSyncRecovery() {
  const catalog = collectShufooFlyerCatalog_();
  const detectedIds = (catalog.flyerPages || []).map(x => String(x.id));
  Logger.log("[検出] " + JSON.stringify(detectedIds));

  const result = analyzeShufooFlyersRecovery_(catalog);
  Logger.log("[解析成功] " + JSON.stringify(result.flyers.map(x => x.id)));
  Logger.log("[解析失敗] " + JSON.stringify(result.failedIds));

  const sync = syncLifeFlyers_(result.flyers);
  Logger.log(JSON.stringify({
    detected: detectedIds.length,
    analyzed: result.flyers.length,
    missing: result.failedIds,
    flyers: sync.flyers,
    deals: sync.deals,
  }, null, 2));

  if (result.failedIds.length > 0) {
    throw new Error("一部チラシの解析に失敗しました。missing=" + result.failedIds.join(","));
  }
  return sync;
}

function analyzeShufooFlyersRecovery_(catalog) {
  const flyers = [];
  const failedIds = [];
  (catalog.flyerPages || []).forEach(page => {
    try {
      const flyer = analyzeSingleShufooFlyerRecovery_(page);
      if (flyer) {
        flyers.push(flyer);
        Logger.log(`[解析OK] ${page.id} ${flyer.start_date}〜${flyer.end_date} ${flyer.deals.length}件`);
      } else {
        failedIds.push(String(page.id));
        Logger.log(`[解析NG] ${page.id}: 日付または商品情報を確定できませんでした`);
      }
    } catch (e) {
      failedIds.push(String(page.id));
      Logger.log(`[解析エラー] ${page.id}: ${e}`);
    }
  });
  return { flyers: flyers, failedIds: failedIds };
}

function analyzeSingleShufooFlyerRecovery_(page) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY") || "";
  const model = props.getProperty("FLYER_GEMINI_MODEL") || "gemini-3.5-flash-lite";
  if (!apiKey) throw new Error("GEMINI_API_KEY をScript Propertiesへ設定してください。");
  if (!page.images || page.images.length === 0) return null;

  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const prompt = [
    "あなたはスーパーのチラシを正確に読み取るアシスタントです。",
    `対象店舗: ${SUMMIT_FLYER_STORE_NAME}`,
    `今日: ${today}`,
    `Shufoo配信ID: ${page.id}`,
    "この入力は1つの配信IDだけです。別のチラシと混ぜないでください。",
    "商品名・価格・容量・対象日は画像または本文で読める内容だけを使い、推測で補わないでください。",
    "チラシ全体のstart_date/end_dateが不明でも、各商品のstart_date/end_dateは読める範囲で必ず返してください。",
    "各商品に根拠画像URLをimage_urlへ入れてください。",
    "説明文なしのJSONだけを返してください。",
    '{"title":"表示用タイトル","type":"月間|週次|日替わり|その他","start_date":"YYYY-MM-DDまたは空文字","end_date":"YYYY-MM-DDまたは空文字","deals":[{"product":"商品名","price":"価格","unit":"容量・単位","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","notes":"条件","priority":1,"image_url":"https://..."}]}',
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
  if (code < 200 || code >= 300) {
    throw new Error(`Gemini flyer analysis failed (${page.id}): ${code} ${body.slice(0, 500)}`);
  }

  const outer = JSON.parse(body);
  const outParts = (((outer.candidates || [])[0] || {}).content || {}).parts || [];
  const parsedText = stripJsonFence_(outParts.map(x => x.text || "").join("").trim());
  if (!parsedText) return null;
  const parsed = JSON.parse(parsedText);
  return sanitizeSingleLifeFlyerRecovery_(parsed, page);
}

function sanitizeSingleLifeFlyerRecovery_(raw, page) {
  raw = raw || {};
  const imageUrls = (page.images || []).map(x => x.url);

  // 先に商品を正規化する。チラシ全体の日付が欠けていても商品日付は救済に使う。
  const rawDeals = Array.isArray(raw.deals) ? raw.deals : [];
  const provisionalDeals = rawDeals.map(item => {
    const startDate = normalizeDateString_(item.start_date);
    const endDate = normalizeDateString_(item.end_date || item.start_date);
    if (!item.product || !startDate || !endDate) return null;
    let imageUrl = /^https?:\/\//.test(String(item.image_url || "")) ? String(item.image_url) : (imageUrls[0] || "");
    if (imageUrls.indexOf(imageUrl) < 0) imageUrl = imageUrls[0] || "";
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

  let start = normalizeDateString_(raw.start_date);
  let end = normalizeDateString_(raw.end_date || raw.start_date);

  // トップレベル期間が欠けた場合、画像から読めた商品日付の最小〜最大で復元する。
  if ((!start || !end) && provisionalDeals.length > 0) {
    const starts = provisionalDeals.map(x => x.start_date).filter(Boolean).sort();
    const ends = provisionalDeals.map(x => x.end_date || x.start_date).filter(Boolean).sort();
    if (!start && starts.length > 0) start = starts[0];
    if (!end && ends.length > 0) end = ends[ends.length - 1];
    Logger.log(`[期間救済] ${page.id}: ${start || "?"}〜${end || "?"}`);
  }

  if (!start || !end) return null;

  // 商品側に日付欠落がある場合のみ、確定したチラシ期間を補助値として使う。
  const deals = rawDeals.map(item => {
    const startDate = normalizeDateString_(item.start_date || start);
    const endDate = normalizeDateString_(item.end_date || item.start_date || end || start);
    if (!item.product || !startDate || !endDate) return null;
    let imageUrl = /^https?:\/\//.test(String(item.image_url || "")) ? String(item.image_url) : (imageUrls[0] || "");
    if (imageUrls.indexOf(imageUrl) < 0) imageUrl = imageUrls[0] || "";
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

  if (deals.length === 0) return null;

  const type = inferLifeFlyerTypeRecovery_(start, end);
  return {
    id: String(page.id),
    source_url: page.url,
    title: String(raw.title || `${type}チラシ ${page.id}`).trim().slice(0, 180),
    type: type,
    start_date: start,
    end_date: end,
    image_urls: imageUrls,
    deals: deals.slice(0, 40),
  };
}

function inferLifeFlyerTypeRecovery_(start, end) {
  if (!start || !end) return "その他";
  const days = Math.round((new Date(end + "T00:00:00+09:00") - new Date(start + "T00:00:00+09:00")) / 86400000) + 1;
  if (days >= 20) return "月間";
  if (days >= 3) return "週次";
  if (days <= 2) return "日替わり";
  return "その他";
}
