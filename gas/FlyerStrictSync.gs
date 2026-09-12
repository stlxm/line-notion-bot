// Phase 2.7: 最小JSONスキーマで全配信IDを再検証する一時テスト。
// FlyerDeals.gs / FlyerLifeCalendar.gs と同じApps Scriptプロジェクトに置く。
// Notion同期は全IDの解析成功後にだけ実行する。

function testSummitLifeFlyerStrictSync() {
  const catalog = collectShufooFlyerCatalog_();
  const detectedIds = (catalog.flyerPages || []).map(x => String(x.id));
  Logger.log("[STRICT検出] " + JSON.stringify(detectedIds));

  const flyers = [];
  const missing = [];

  (catalog.flyerPages || []).forEach(page => {
    try {
      const flyer = analyzeSingleShufooFlyerStrictMinimal_(page);
      if (flyer && flyer.start_date && flyer.end_date && Array.isArray(flyer.deals) && flyer.deals.length > 0) {
        flyers.push(flyer);
        Logger.log(`[STRICT解析OK] ${page.id} ${flyer.start_date}〜${flyer.end_date} ${flyer.deals.length}件`);
      } else {
        missing.push(String(page.id));
        Logger.log(`[STRICT解析NG] ${page.id}`);
      }
    } catch (e) {
      missing.push(String(page.id));
      Logger.log(`[STRICT解析エラー] ${page.id}: ${e}`);
    }
  });

  Logger.log("[STRICT成功ID] " + JSON.stringify(flyers.map(x => x.id)));
  Logger.log("[STRICT失敗ID] " + JSON.stringify(missing));

  if (missing.length > 0) {
    throw new Error("最小スキーマでも一部チラシの解析に失敗しました。missing=" + missing.join(","));
  }

  const sync = syncLifeFlyers_(flyers);
  Logger.log(JSON.stringify({
    detected: detectedIds.length,
    analyzed: flyers.length,
    missing: [],
    flyers: sync.flyers,
    deals: sync.deals,
  }, null, 2));
  return sync;
}

function analyzeSingleShufooFlyerStrictMinimal_(page) {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY") || "";
  const model = props.getProperty("FLYER_GEMINI_MODEL") || "gemini-3.5-flash-lite";
  if (!apiKey) throw new Error("GEMINI_API_KEY をScript Propertiesへ設定してください。");
  if (!page.images || page.images.length === 0) return null;

  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  const prompt = [
    "スーパーのチラシ画像を読み取ってください。推測は禁止です。",
    `対象店舗: ${SUMMIT_FLYER_STORE_NAME}`,
    `今日: ${today}`,
    `Shufoo配信ID: ${page.id}`,
    "重要: チラシに書かれた掲載期間・対象日を最優先で読み取ってください。",
    "チラシ全体の日付が読めない場合でも、商品名と商品ごとの日付は読める範囲で返してください。",
    "日付文字列を画像内で見つけた場合は date_evidence に原文も入れてください。",
    "価格が書かれていない割引/ポイントカレンダーでも、カテゴリ名・対象日をdealsとして返してください。",
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
    throw new Error(`Gemini strict analysis failed (${page.id}): ${code} ${body.slice(0, 500)}`);
  }

  const outer = JSON.parse(body);
  const outParts = (((outer.candidates || [])[0] || {}).content || {}).parts || [];
  const parsedText = stripJsonFence_(outParts.map(x => x.text || "").join("").trim());
  if (!parsedText) return null;

  const raw = JSON.parse(parsedText);
  return sanitizeSingleLifeFlyerStrictMinimal_(raw, page);
}

function sanitizeSingleLifeFlyerStrictMinimal_(raw, page) {
  raw = raw || {};
  const imageUrls = (page.images || []).map(x => x.url);
  const rawDeals = Array.isArray(raw.deals) ? raw.deals : [];

  let start = normalizeDateString_(raw.start_date);
  let end = normalizeDateString_(raw.end_date || raw.start_date);

  const datedDeals = rawDeals.map(item => {
    const s = normalizeDateString_(item.start_date);
    const e = normalizeDateString_(item.end_date || item.start_date);
    if (!item.product || !s || !e) return null;
    return { start: s, end: e };
  }).filter(Boolean);

  if ((!start || !end) && datedDeals.length > 0) {
    const starts = datedDeals.map(x => x.start).sort();
    const ends = datedDeals.map(x => x.end).sort();
    if (!start) start = starts[0];
    if (!end) end = ends[ends.length - 1];
    Logger.log(`[STRICT期間救済] ${page.id}: ${start || "?"}〜${end || "?"}`);
  }

  if (!start || !end) return null;

  const deals = rawDeals.map(item => {
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
      priority: 2,
      image_url: imageUrls[0] || "",
    };
  }).filter(Boolean);

  if (deals.length === 0) return null;

  return {
    id: String(page.id),
    source_url: page.url,
    title: String(raw.title || `チラシ ${page.id}`).trim().slice(0, 180),
    type: inferLifeFlyerType_(start, end),
    start_date: start,
    end_date: end,
    image_urls: imageUrls,
    deals: deals.slice(0, 40),
  };
}
