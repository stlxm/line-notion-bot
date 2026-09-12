// Phase 2.7 flyer parser targeted diagnostics.
// Temporary helper: identifies why a detected Shufoo delivery ID is dropped after Gemini parsing.
// No Notion or LINE writes.

const FLYER_DEBUG_IDS = ["4441736841834", "2187006858976"];

function debugFailedSummitFlyers() {
  const catalog = collectShufooFlyerCatalog_();
  const pagesById = {};
  (catalog.flyerPages || []).forEach(page => { pagesById[String(page.id)] = page; });

  FLYER_DEBUG_IDS.forEach(id => {
    const page = pagesById[id];
    if (!page) {
      Logger.log(`[DEBUG NG] ${id}: catalogにページがありません`);
      return;
    }
    debugSingleSummitFlyerRaw_(page);
  });
}

function debugSingleSummitFlyerRaw_(page) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY") || "";
  const model = props.getProperty("FLYER_GEMINI_MODEL") || "gemini-3.5-flash-lite";
  if (!apiKey) throw new Error("GEMINI_API_KEY をScript Propertiesへ設定してください。");
  if (!page.images || page.images.length === 0) {
    Logger.log(`[DEBUG NG] ${page.id}: image=0`);
    return;
  }

  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const prompt = [
    "スーパーのチラシ画像を読み取ってください。推測は禁止です。",
    `対象店舗: ${SUMMIT_FLYER_STORE_NAME}`,
    `今日: ${today}`,
    `Shufoo配信ID: ${page.id}`,
    "重要: チラシに書かれた掲載期間・対象日を最優先で読み取ってください。",
    "チラシ全体の日付が読めない場合でも、商品名と商品ごとの日付は読める範囲で返してください。",
    "日付文字列を画像内で見つけた場合は date_evidence に原文も入れてください。",
    "説明なしのJSONだけを返してください。",
    '{"title":"","type":"月間|週次|日替わり|その他|不明","start_date":"","end_date":"","date_evidence":"画像内の日付原文","deals":[{"product":"","price":"","unit":"","start_date":"","end_date":"","notes":""}]}',
    "",
    "【画像URL】",
    (page.images || []).map(x => x.url).join("\n"),
    "",
    "【ページ本文】",
    String(page.text || "").slice(0, 22000),
  ].join("\n");

  const parts = [{ text: prompt }];
  page.images.forEach(image => {
    parts.push({ inlineData: { mimeType: image.mimeType, data: Utilities.base64Encode(image.bytes) } });
  });

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      contents: [{ role: "user", parts: parts }],
      generationConfig: { temperature: 0, responseMimeType: "application/json" },
    }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  const body = response.getContentText();
  if (code < 200 || code >= 300) {
    Logger.log(`[DEBUG API ERROR] ${page.id}: ${code} ${body.slice(0, 500)}`);
    return;
  }

  const outer = JSON.parse(body);
  const outParts = (((outer.candidates || [])[0] || {}).content || {}).parts || [];
  const parsedText = stripJsonFence_(outParts.map(x => x.text || "").join("").trim());
  if (!parsedText) {
    Logger.log(`[DEBUG NG] ${page.id}: Gemini JSONが空です`);
    return;
  }

  let raw;
  try {
    raw = JSON.parse(parsedText);
  } catch (e) {
    Logger.log(`[DEBUG JSON ERROR] ${page.id}: ${parsedText.slice(0, 1200)}`);
    return;
  }

  const deals = Array.isArray(raw.deals) ? raw.deals : [];
  Logger.log(`[DEBUG ${page.id}] imageCount=${page.images.length}`);
  Logger.log(JSON.stringify({
    id: String(page.id),
    title: raw.title || "",
    type: raw.type || "",
    start_date: raw.start_date || "",
    end_date: raw.end_date || "",
    date_evidence: raw.date_evidence || "",
    deal_count: deals.length,
    deals: deals.slice(0, 8).map(d => ({
      product: d.product || "",
      price: d.price || "",
      unit: d.unit || "",
      start_date: d.start_date || "",
      end_date: d.end_date || "",
      notes: d.notes || "",
    })),
  }, null, 2));
}
