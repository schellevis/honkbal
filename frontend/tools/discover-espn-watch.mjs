// discover-espn-watch.mjs — zelfherstel voor de ESPN watch-apiKey (SPEC §3.3).
//
// De apiKey van watch.graph.api.espn.com is een publieke client-side constante uit de
// espn.nl-paginabundel. De pagina zelf zit achter AWS-WAF-botmitigatie (HTTP 202 voor kale
// clients), dus als ESPN de key roteert kan `fetch/tv_guide.py` hem niet zelf opvissen.
// Dit script laadt de speelkalender headless (Playwright zit al in de devdeps), kijkt het
// eerste request naar de watch-GraphQL-API af, valideert de gevonden key met een echte
// API-call en schrijft hem naar .data/espn_watch_config.json — waar de fetch hem met
// voorrang op de ingebouwde fallback-constante leest.
//
// Gebruik: `npm run discover:espn` (optioneel: DATA_DIR=<pad> voor een andere cache-map).
// CI (build.yml) draait dit alleen wanneer de vorige fetch niet meer op ESPN draaide.

import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, renameSync } from "node:fs";
import { join } from "node:path";

const PAGE_URL = "https://www.espn.nl/watch/speelkalender";
const API_HOST = "watch.graph.api.espn.com";
const DATA_DIR = process.env.DATA_DIR || ".data";
const CONFIG_FILE = "espn_watch_config.json";
const PAGE_TIMEOUT_MS = 60_000;

// De pagina praat voor meerdere doelen met de graph-API (o.a. artwork, met een andere key);
// alleen het airings-request draagt de key die de fetch-adapter nodig heeft.
function isAiringsRequest(req) {
  const url = new URL(req.url());
  return (
    url.host === API_HOST &&
    url.searchParams.has("apiKey") &&
    (url.searchParams.get("query") || "").includes("airings")
  );
}

async function sniffApiKey() {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const apiRequest = page.waitForRequest(isAiringsRequest, { timeout: PAGE_TIMEOUT_MS });
    await page.goto(PAGE_URL, { waitUntil: "domcontentloaded", timeout: PAGE_TIMEOUT_MS });
    const request = await apiRequest;
    return new URL(request.url()).searchParams.get("apiKey");
  } finally {
    await browser.close();
  }
}

async function validateApiKey(apiKey) {
  const url = new URL(`https://${API_HOST}/api`);
  url.searchParams.set("apiKey", apiKey);
  url.searchParams.set(
    "query",
    "query A($countryCode:String!,$deviceType:DeviceType!,$tz:String!," +
      "$type:AiringType,$day:String,$limit:Int)" +
      "{airings(countryCode:$countryCode,deviceType:$deviceType,tz:$tz," +
      "type:$type,day:$day,limit:$limit){id}}",
  );
  url.searchParams.set(
    "variables",
    JSON.stringify({
      countryCode: "NL",
      deviceType: "DESKTOP",
      tz: "UTC+0200",
      type: "UPCOMING",
      day: new Date().toISOString().slice(0, 10),
      limit: 1,
    }),
  );
  const res = await fetch(url);
  if (!res.ok) return false;
  const body = await res.json();
  return Array.isArray(body?.data?.airings);
}

const apiKey = await sniffApiKey();
if (!apiKey) {
  console.error("[FOUT] geen apiKey gezien in het verkeer naar de watch-API");
  process.exit(1);
}
if (!(await validateApiKey(apiKey))) {
  console.error(`[FOUT] afgekeken apiKey wordt door de API geweigerd`);
  process.exit(1);
}

mkdirSync(DATA_DIR, { recursive: true });
const target = join(DATA_DIR, CONFIG_FILE);
const tmp = `${target}.tmp`;
writeFileSync(
  tmp,
  JSON.stringify(
    { apiKey, discovered_at: new Date().toISOString(), source: PAGE_URL },
    null,
    2,
  ) + "\n",
);
renameSync(tmp, target);
console.log(`[ok] geldige apiKey weggeschreven naar ${target}`);
