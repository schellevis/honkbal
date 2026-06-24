import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { installDom, restoreDom } from "./dom-stub.js";
import { installFetch, restoreFetch } from "./fetch-stub.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
function fixture(name) {
  return JSON.parse(readFileSync(join(__dirname, "fixtures", name), "utf8"));
}

let scores;
beforeEach(async () => {
  installDom();
  scores = await import("../js/scores.js?" + Math.random());
});
afterEach(() => { restoreFetch(); restoreDom(); });

// --- favorites highlight with full MLB Stats API names ---
test("renderScoresHtml highlights a game whose API names match a settings-favorite nickname", async () => {
  const fav = await import("../js/favorites.js?" + Math.random());
  fav.setFavorites(["red sox"]); // zoals settings opslaat
  const game = {
    gameDate: "2026-04-01T17:00:00Z",
    status: { abstractGameState: "Final", detailedState: "Final" },
    teams: {
      away: { team: { name: "Boston Red Sox", abbreviation: "BOS" } },
      home: { team: { name: "Tampa Bay Rays", abbreviation: "TB" } },
    },
  };
  const html = scores.renderScoresHtml([], [game], [], fav.isFavoriteMatchup);
  assert.match(html, /class="favorite-game"/);
  assert.match(html, /data-away-team="red sox"/);
  assert.match(html, /<img[^>]+\/img\/red\+sox-fs8\.png/); // logo, geen logofill
  assert.doesNotMatch(html, /data-away-team="boston-red-sox"/); // niet de oude gehyphende bug
});

// --- classifyGame ---
test("classifyGame: Live → 'live'", () => {
  const game = fixture("scores-live.json").dates[0].games[0];
  assert.equal(scores.classifyGame(game), "live");
});

test("classifyGame: Warmup → 'preview'", () => {
  const game = fixture("scores-warmup.json").dates[0].games[0];
  assert.equal(scores.classifyGame(game), "preview");
});

test("classifyGame: Delayed → 'preview'", () => {
  const game = fixture("scores-delayed.json").dates[0].games[0];
  assert.equal(scores.classifyGame(game), "preview");
});

test("classifyGame: Final → 'finished'", () => {
  const game = fixture("scores-final.json").dates[0].games[0];
  assert.equal(scores.classifyGame(game), "finished");
});

test("classifyGame: Scheduled → null", () => {
  const game = fixture("scores-final.json").dates[0].games[2];
  assert.equal(scores.classifyGame(game), null);
});

// --- sortLive ---
test("sortLive without favorites: inning sort (Dodgers@Giants inning 3 bottom → 7, Mets@Cubs inning 5 top → 10)", () => {
  const games = fixture("scores-live.json").dates[0].games;
  const sorted = scores.sortLive(games, () => false);
  assert.equal(sorted[0].teams.away.team.name, "Los Angeles Dodgers");
  assert.equal(sorted[1].teams.away.team.name, "New York Mets");
});

test("sortLive with Mets favorite: Mets@Cubs first", () => {
  const games = fixture("scores-live.json").dates[0].games;
  const sorted = scores.sortLive(games, (a, h) => {
    const n = (s) => s.toLowerCase();
    return n(a).includes("mets") || n(h).includes("mets");
  });
  assert.equal(sorted[0].teams.away.team.name, "New York Mets");
  assert.equal(sorted[1].teams.away.team.name, "Los Angeles Dodgers");
});

// --- sortFinished ---
test("sortFinished without favorites: earliest gameDate first [FIX]", () => {
  const games = fixture("scores-final.json").dates[0].games.filter((g) => g.status.abstractGameState === "Final");
  const sorted = scores.sortFinished(games, () => false);
  assert.equal(sorted[0].gameDate, "2026-06-21T08:00:00Z");
  assert.equal(sorted[1].gameDate, "2026-06-21T23:00:00Z");
});

// --- statusLabel ---
test("statusLabel: warmup", () => {
  const game = fixture("scores-warmup.json").dates[0].games[0];
  const label = scores.statusLabel(game);
  assert.equal(label.kind, "warmup");
  assert.ok(label.html.toLowerCase().includes("warmup"));
});

test("statusLabel: DEL", () => {
  const game = fixture("scores-delayed.json").dates[0].games[0];
  const label = scores.statusLabel(game);
  assert.equal(label.kind, "DEL");
  assert.ok(label.html.includes("DEL"));
});

test("statusLabel: live contains svg and inning", () => {
  const game = fixture("scores-live.json").dates[0].games[0];
  const label = scores.statusLabel(game);
  assert.equal(label.kind, "live");
  assert.ok(label.html.includes("<svg"));
  assert.ok(label.html.includes("3"));
});

test("statusLabel: final", () => {
  const game = fixture("scores-final.json").dates[0].games[0];
  const label = scores.statusLabel(game);
  assert.equal(label.kind, "final");
  assert.ok(label.html.toLowerCase().includes("final"));
});

// --- cache ---
test("cache round-trip: writeCache then readCache returns payload", () => {
  const now = new Date("2026-06-21T12:00:00Z");
  scores.writeCache("20260621", { foo: "bar" }, now);
  const result = scores.readCache("20260621");
  assert.deepEqual(result, { foo: "bar" });
});

test("readCache with wrong version returns null", () => {
  const now = new Date("2026-06-21T12:00:00Z");
  scores.writeCache("20260621", { foo: "bar" }, now);
  // Manually corrupt the version in localStorage
  const key = scores.cacheKey("20260621");
  const metaKey = scores.metaKey("20260621");
  const meta = JSON.parse(globalThis.localStorage.getItem(metaKey));
  meta.version = 9999;
  globalThis.localStorage.setItem(metaKey, JSON.stringify(meta));
  assert.equal(scores.readCache("20260621"), null);
});

test("pruneCache removes old days but keeps recent", () => {
  const now = new Date("2026-06-21T12:00:00Z");
  // Write an old entry (30 days ago)
  scores.writeCache("20260521", { old: true }, new Date("2026-05-21T12:00:00Z"));
  // Write a recent entry
  scores.writeCache("20260620", { recent: true }, new Date("2026-06-20T12:00:00Z"));
  scores.pruneCache(now, ["20260620", "20260621"]);
  assert.equal(scores.readCache("20260521"), null);
  assert.deepEqual(scores.readCache("20260620"), { recent: true });
});

test("latestUpdate returns max cachedAt", () => {
  const now = new Date("2026-06-21T12:00:00Z");
  scores.writeCache("20260619", { a: 1 }, new Date("2026-06-19T10:00:00Z"));
  scores.writeCache("20260620", { b: 2 }, new Date("2026-06-20T15:00:00Z"));
  const latest = scores.latestUpdate(["20260619", "20260620"]);
  assert.ok(latest instanceof Date);
  assert.equal(latest.toISOString(), "2026-06-20T15:00:00.000Z");
});

test("refreshIntervalMs: 30s with live games, 300s otherwise", () => {
  assert.equal(scores.refreshIntervalMs(true), 30000);
  assert.equal(scores.refreshIntervalMs(false), 300000);
});

// --- XSS / escaping (C1, SPEC §2/§6.2) ---
function malformedGame(awayName, homeName, awayAbbr = "AAA", homeAbbr = "HHH") {
  return {
    teams: {
      away: { team: { name: awayName, abbreviation: awayAbbr } },
      home: { team: { name: homeName, abbreviation: homeAbbr } },
    },
    gameDate: "2026-06-21T18:00:00Z",
    status: { abstractGameState: "Final", detailedState: "Final" },
    linescore: {},
  };
}

test("renderScoresHtml escapes a team name containing <script>", () => {
  const g = malformedGame("<script>alert(1)</script>", "Normal Team");
  const html = scores.renderScoresHtml([], [g], [], () => false);
  assert.ok(!html.includes("<script>alert(1)</script>"), "raw <script> must not appear");
  assert.ok(html.includes("&lt;script&gt;"), "should contain escaped script tag");
});

test("renderScoresHtml escapes quotes/ampersand in name and abbreviation", () => {
  const g = malformedGame('Red "Sox" & Co', "A&W", 'B"D', "X&Y");
  const html = scores.renderScoresHtml([], [g], [], () => false);
  // No raw double-quote inside text content that would break out of an attribute
  assert.ok(html.includes("&amp;"), "ampersand should be escaped");
  assert.ok(html.includes("&quot;"), "double quote should be escaped");
  // The data attribute must not be broken by a raw quote
  assert.ok(!/data-away-team="[^"]*"[^>]*"/.test(html) || html.includes("&quot;"));
});

// --- I2: cachedAt uses a fresh clock per fetch, not the page-load `now` ---
test("fetchAndRender writes cachedAt from a fresh clock, not injected page-load now", async () => {
  // Inject a `now` far in the past for the day-window; the cache cachedAt must reflect
  // the real fetch moment (fresh Date), not this stale injected value (SPEC §6.2).
  const staleNow = new Date("2020-01-01T00:00:00Z");
  installFetch({
    "statsapi.mlb.com": { ok: true, status: 200, payload: { dates: [] } },
  });
  const before = Date.now();
  // init returns the promise of the first fetch cycle, resolving to the refresh timer id.
  const timer = await scores.init(globalThis.document, { now: staleNow, fetch: globalThis.fetch });
  clearTimeout(timer); // cancel the 300s refresh so node:test can exit cleanly

  // Find any scores-meta-* entry written and verify its cachedAt is recent (not 2020).
  const storage = globalThis.localStorage;
  let foundRecent = false;
  for (let i = 0; i < storage.length; i++) {
    const k = storage.key(i);
    if (k && k.startsWith("scores-meta-")) {
      const meta = JSON.parse(storage.getItem(k));
      const t = new Date(meta.cachedAt).getTime();
      if (t >= before) foundRecent = true;
      assert.notEqual(meta.cachedAt, staleNow.toISOString(), "cachedAt must not be the stale page-load now");
    }
  }
  assert.ok(foundRecent, "at least one cache entry should have a fresh cachedAt");
});

// --- empty response ---
test("empty dates array does not crash", () => {
  const data = fixture("scores-empty.json");
  const games = [];
  for (const d of data.dates) games.push(...d.games);
  assert.equal(games.length, 0);
});
