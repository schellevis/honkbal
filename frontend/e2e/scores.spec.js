import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(__dirname, "../test/fixtures");

function fixture(name) {
  return JSON.parse(readFileSync(join(fixturesDir, name), "utf8"));
}

// Serve a minimal scores.html shell from e2e/fixtures/
test("scores page: live game renders SVG bases and outs", async ({ page }) => {
  const liveData = fixture("scores-live.json");
  await page.route("**/statsapi.mlb.com/**", (route) => {
    route.fulfill({ contentType: "application/json", body: JSON.stringify(liveData) });
  });
  await page.goto("/scores.html");
  await page.waitForTimeout(500);
  const svgCount = await page.locator("svg").count();
  expect(svgCount).toBeGreaterThan(0);
});

test("scores page: team abbreviations are never clipped at mobile width", async ({ page }) => {
  // Regressie: op smalle schermen toont de cel de afkorting (score-abbr). Die is kort en mag
  // nooit met ellipsis worden afgekapt ("HOU" -> "H..."), ook niet in rijen met een brede
  // live-statuspil of een tweecijferige score die de cel extra opknijpen.
  await page.setViewportSize({ width: 390, height: 844 });
  const now = new Date().toISOString();
  const payload = { dates: [{ date: "2026-07-27", games: [
    { gamePk: 1, gameDate: now,
      status: { abstractGameState: "Live", detailedState: "In Progress" },
      linescore: { currentInning: 9, isTopInning: false, outs: 1, offense: { first: true, second: true, third: true } },
      teams: { away: { score: 6, team: { name: "Houston Astros", clubName: "Astros", abbreviation: "HOU" } },
               home: { score: 4, team: { name: "Los Angeles Angels", clubName: "Angels", abbreviation: "LAA" } } } },
    { gamePk: 2, gameDate: now,
      status: { abstractGameState: "Final", detailedState: "Final" },
      teams: { away: { score: 3, isWinner: false, team: { name: "Atlanta Braves", clubName: "Braves", abbreviation: "ATL" } },
               home: { score: 14, isWinner: true, team: { name: "New York Mets", clubName: "Mets", abbreviation: "NYM" } } } },
  ] }] };
  await page.route("**/statsapi.mlb.com/**", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify(payload) }));
  await page.goto("/scores.html");
  await page.waitForTimeout(600);
  const clipped = await page.evaluate(() => {
    const bad = [];
    for (const el of document.querySelectorAll(".score-abbr")) {
      if (getComputedStyle(el).display === "none") continue; // desktop-modus: naam i.p.v. afkorting
      const span = el.parentElement; // .score-team draagt de (uitgeschakelde) ellipsis
      if (span.scrollWidth > span.clientWidth + 1) bad.push(el.textContent);
    }
    return bad;
  });
  expect(clipped).toEqual([]);
});

test("scores page: empty response renders empty state", async ({ page }) => {
  const emptyData = fixture("scores-empty.json");
  await page.route("**/statsapi.mlb.com/**", (route) => {
    route.fulfill({ contentType: "application/json", body: JSON.stringify(emptyData) });
  });
  await page.goto("/scores.html");
  await page.waitForTimeout(500);
  // Productie-markup: lege staat is een <p> in #scores-container.
  const containerText = await page.locator("#scores-container").textContent();
  expect(containerText).toContain("Geen recente scores beschikbaar");
});

test("scores page: offline shows cache fallback message", async ({ page }) => {
  // Phase 1: Load successfully so data is cached in localStorage
  const liveData = fixture("scores-live.json");
  await page.route("**/statsapi.mlb.com/**", (route) => {
    route.fulfill({ contentType: "application/json", body: JSON.stringify(liveData) });
  });
  await page.goto("/scores.html");
  await page.waitForTimeout(800);

  // Verify rows loaded and data was cached
  const rowsBefore = await page.locator("tr[data-away-team]").count();
  expect(rowsBefore).toBeGreaterThan(0);

  // Grab a cached key from localStorage to confirm caching happened
  const cachedKeys = await page.evaluate(() => {
    return Object.keys(localStorage).filter((k) => k.startsWith("scores-") && !k.startsWith("scores-meta-"));
  });
  expect(cachedKeys.length).toBeGreaterThan(0);

  // Phase 2: Block all MLB API calls (simulate offline fetch failure) and reload the page
  // NOTE: We use page.route to abort at the Playwright network level, keeping context online
  // so page.goto itself still works (only MLB API requests fail).
  await page.unroute("**/statsapi.mlb.com/**");
  await page.route("**/statsapi.mlb.com/**", (route) => route.abort());

  // Reload the same page (context is still online so navigation works)
  await page.reload();
  await page.waitForTimeout(1200);

  // SPEC §offline: de offline-melding staat per dag-tabel in #scores-container (productie-markup).
  const containerText = await page.locator("#scores-container").textContent();
  expect(containerText).toContain("offline - laatst bijgewerkt om");
});
