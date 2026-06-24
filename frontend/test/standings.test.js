import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { installDom, restoreDom } from "./dom-stub.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
function fixture(name) {
  return JSON.parse(readFileSync(join(__dirname, "fixtures", name), "utf8"));
}

let st;
beforeEach(async () => {
  installDom();
  st = await import("../js/standings.js?" + Math.random());
});
afterEach(() => restoreDom());

// --- flatten ---
test("flatten extracts all team records from full fixture", () => {
  const data = fixture("standings-full.json");
  const rows = st.flatten(data);
  assert.equal(rows.length, 13); // AL West has 3 teams, others 2
  // Check a known field
  const yankees = rows.find((r) => r.teamName === "New York Yankees");
  assert.ok(yankees);
  assert.equal(yankees.wins, 55);
  assert.equal(yankees.losses, 25);
});

// --- real MLB Stats API shape (nested records.splitRecords, streak.streakCode, team.teamName) ---
test("flatten reads L10/streak/short-name from the real nested API shape", () => {
  const api = {
    records: [{
      division: { id: 201 }, league: { id: 103 },
      teamRecords: [{
        team: { name: "New York Yankees", teamName: "Yankees", abbreviation: "NYY" },
        wins: 46, losses: 31, winningPercentage: ".597", gamesBack: "-",
        divisionRank: "1", leagueRank: "1",
        streak: { streakCode: "L3" },
        records: { splitRecords: [
          { type: "home", wins: 25, losses: 12 },
          { type: "lastTen", wins: 5, losses: 5 },
        ] },
      }],
    }],
  };
  const [row] = st.flatten(api);
  assert.equal(row.teamName, "Yankees", "korte weergavenaam");
  assert.equal(row.l10, "5-5", "L10 uit tr.records.splitRecords");
  assert.equal(row.streak, "L3", "streak uit tr.streak.streakCode");
});

// --- validateRow ---
test("validateRow: row missing wins fails all views", () => {
  const row = { teamName: "X", losses: 10, pct: ".500", divisionId: 200, divisionRank: 1 };
  assert.equal(st.validateRow(row, "division"), false);
  assert.equal(st.validateRow(row, "al"), false);
  assert.equal(st.validateRow(row, "mlb"), false);
  assert.equal(st.validateRow(row, "wildcard"), false);
});

test("validateRow: full row passes division view", () => {
  const row = { teamName: "X", wins: 50, losses: 30, pct: ".625", divisionId: 200, divisionRank: 1 };
  assert.equal(st.validateRow(row, "division"), true);
});

test("validateRow: row with wildCardRank passes wildcard view", () => {
  const row = { teamName: "X", wins: 50, losses: 30, pct: ".625", wildCardRank: 2, wcGamesBack: "2.0" };
  assert.equal(st.validateRow(row, "wildcard"), true);
});

test("validateRow: row without wildCardRank fails wildcard view", () => {
  const row = { teamName: "X", wins: 50, losses: 30, pct: ".625" };
  assert.equal(st.validateRow(row, "wildcard"), false);
});

// --- viewDivision ---
test("viewDivision: groups by divisionId, sorts by divisionRank", () => {
  const data = fixture("standings-full.json");
  const rows = st.flatten(data);
  const groups = st.viewDivision(rows);
  // Should have 6 groups (6 divisions)
  assert.equal(groups.length, 6);
  // Each group sorted by divisionRank ascending
  for (const group of groups) {
    for (let i = 1; i < group.rows.length; i++) {
      assert.ok(group.rows[i].divisionRank >= group.rows[i - 1].divisionRank);
    }
  }
});

test("viewDivision: skips unknown divisionId 999", () => {
  const data = fixture("standings-missing.json");
  const rows = st.flatten(data);
  const groups = st.viewDivision(rows);
  const divIds = groups.map((g) => g.divisionId);
  assert.ok(!divIds.includes(999));
});

// --- viewLeague ---
test("viewLeague AL: sorted by leagueRank ascending", () => {
  const data = fixture("standings-full.json");
  const rows = st.flatten(data);
  const alRows = st.viewLeague(rows, "AL");
  for (let i = 1; i < alRows.length; i++) {
    assert.ok(alRows[i].leagueRank >= alRows[i - 1].leagueRank);
  }
});

test("viewLeague: tie-break by pct descending then wins descending (SPEC §12.8)", () => {
  const data = fixture("standings-tie.json");
  const rows = st.flatten(data);
  // All four teams share leagueRank 1, but differ by pct and wins:
  //   Alpha:  .650, 52 wins
  //   Gamma:  .625, 50 wins
  //   Beta:   .600, 48 wins
  //   Delta:  .600, 48 wins
  // Expected order: Alpha → Gamma → Beta or Delta (both .600/48) in any internal order
  const alRows = st.viewLeague(rows, "AL");
  assert.ok(alRows.length >= 3, "should have at least 3 AL teams");
  assert.equal(alRows[0].teamName, "Team Alpha", "Alpha first (.650 pct)");
  assert.equal(alRows[1].teamName, "Team Gamma", "Gamma second (.625 pct)");
  // Beta and Delta share pct .600 and wins 48 — both ahead of any worse team
  const rank2Names = alRows.slice(2).map((r) => r.teamName);
  assert.ok(rank2Names.includes("Team Beta"), "Beta in positions 3+");
  assert.ok(rank2Names.includes("Team Delta"), "Delta in positions 3+");
});

test("viewLeague: pct breaks tie before wins — same leagueRank, different pct asserts exact order", () => {
  // Teams with same leagueRank 1 but different pct should be sorted pct↓ first
  const data = fixture("standings-tie.json");
  const rows = st.flatten(data);
  const alRows = st.viewLeague(rows, "AL");
  // Verify pct↓ ordering holds for adjacent pairs
  for (let i = 1; i < alRows.length; i++) {
    const prev = parseFloat(alRows[i - 1].pct);
    const curr = parseFloat(alRows[i].pct);
    // pct should not increase going down the list
    assert.ok(curr <= prev, `pct should not increase at position ${i}: ${prev} → ${curr}`);
  }
});

// --- viewMlb ---
test("viewMlb: sorted by pct descending then wins descending", () => {
  const data = fixture("standings-full.json");
  const rows = st.flatten(data);
  const mlb = st.viewMlb(rows);
  for (let i = 1; i < mlb.length; i++) {
    const a = mlb[i - 1];
    const b = mlb[i];
    const aVal = parseFloat(a.pct) * 10000 + a.wins;
    const bVal = parseFloat(b.pct) * 10000 + b.wins;
    assert.ok(aVal >= bVal);
  }
  // Dodgers should be first (.725)
  assert.equal(mlb[0].teamName, "Los Angeles Dodgers");
});

// --- viewWildcard ---
test("viewWildcard: only ranks 1-6, sorted by wildCardRank", () => {
  const data = fixture("standings-full.json");
  const rows = st.flatten(data);
  const wc = st.viewWildcard(rows, "AL");
  for (const r of wc) {
    assert.ok(r.wildCardRank >= 1 && r.wildCardRank <= 6);
  }
  for (let i = 1; i < wc.length; i++) {
    assert.ok(wc[i].wildCardRank >= wc[i - 1].wildCardRank);
  }
});

test("viewWildcard: holder row (wcGamesBack starts with +) marked", () => {
  const data = fixture("standings-full.json");
  const rows = st.flatten(data);
  const wc = st.viewWildcard(rows, "AL");
  const holder = wc.find((r) => r.isWildcardHolder);
  assert.ok(holder, "should have a wildcard holder");
  assert.ok(String(holder.wcGamesBack).startsWith("+"));
});

// --- missing fields ---
test("standings-missing: row without wins skipped in all views", () => {
  const data = fixture("standings-missing.json");
  const rows = st.flatten(data);
  const mlb = st.viewMlb(rows);
  const names = mlb.map((r) => r.teamName);
  assert.ok(!names.includes("Missing Wins Team"));
});

test("standings-missing: row without wildCardRank skipped only in wildcard view", () => {
  const data = fixture("standings-missing.json");
  const rows = st.flatten(data);
  const mlb = st.viewMlb(rows);
  const wc = st.viewWildcard(rows, "AL");
  const mlbNames = mlb.map((r) => r.teamName);
  const wcNames = wc.map((r) => r.teamName);
  // "No Wildcard Rank" team should appear in mlb but not wildcard
  assert.ok(mlbNames.includes("No Wildcard Rank"), "should appear in mlb");
  assert.ok(!wcNames.includes("No Wildcard Rank"), "should not appear in wildcard");
});

// --- resolveSeason ---
test("resolveSeason reads data-season from body", () => {
  globalThis.document.body.dataset.season = "2026";
  assert.equal(st.resolveSeason(globalThis.document), 2026);
});

test("resolveSeason falls back to current year with warning when missing", () => {
  delete globalThis.document.body.dataset.season;
  const warns = [];
  const origWarn = console.warn;
  console.warn = (...args) => warns.push(args.join(" "));
  const result = st.resolveSeason(globalThis.document);
  console.warn = origWarn;
  assert.equal(typeof result, "number");
  assert.ok(warns.some((w) => w.includes("season")));
});

// --- cache ---
test("standings cache round-trip", () => {
  const now = new Date("2026-06-21T12:00:00Z");
  st.writeCache(2026, { foo: "bar" }, now);
  const result = st.readCache(2026);
  assert.deepEqual(result, { foo: "bar" });
});

test("standings cache: atomic save overwrites even with existing meta", () => {
  const now1 = new Date("2026-06-20T12:00:00Z");
  const now2 = new Date("2026-06-21T12:00:00Z");
  st.writeCache(2026, { old: true }, now1);
  st.writeCache(2026, { new: true }, now2);
  assert.deepEqual(st.readCache(2026), { new: true });
});

// --- renderWildcardRow (Fix 1: malformed class attribute) ---
test("renderWildcardRow: holder+fav produces valid class attribute without .trimStart() literal", () => {
  // Set up a favorite so favCls is applied
  globalThis.localStorage.setItem("honkbal-favorite-teams", JSON.stringify(["test team"]));
  const row = {
    teamName: "Test Team",
    teamAbbr: "TST",
    wins: 50, losses: 30, pct: ".625",
    wcGamesBack: "+1.0",
    isWildcardHolder: true,
    l10: "6-4", streak: "W2",
  };
  const html = st.renderWildcardRow(row);
  // Must not contain the literal text .trimStart() or class="".
  assert.ok(!html.includes(".trimStart()"), "should not contain literal .trimStart()");
  assert.ok(!html.includes('class="".'), "should not contain class=\"\".");
  // class attribute must be syntactically valid: class="..." (productie: standings-wildcard-holder)
  assert.match(html, /class="[^"]*standings-wildcard-holder[^"]*"/, "should have holder class in class attr");
});

test("renderWildcardRow: neither holder nor fav produces no class attribute or empty-class-free output", () => {
  globalThis.localStorage.setItem("honkbal-favorite-teams", JSON.stringify([]));
  const row = {
    teamName: "Other Team",
    teamAbbr: "OTH",
    wins: 40, losses: 40, pct: ".500",
    wcGamesBack: "5.0",
    isWildcardHolder: false,
    l10: "5-5", streak: "L1",
  };
  const html = st.renderWildcardRow(row);
  assert.ok(!html.includes(".trimStart()"), "should not contain literal .trimStart()");
  assert.ok(!html.includes('class="".'), "should not contain class=\"\".");
  // When there are no classes, there should be no class attribute at all (clean output)
  assert.ok(!html.includes('class=""'), "should not emit empty class attribute");
});

// --- XSS / escaping + normalized data attributes (C1, SPEC §2/§6.3) ---
test("renderWildcardRow escapes a team name containing <script>/\"/&", () => {
  globalThis.localStorage.setItem("honkbal-favorite-teams", JSON.stringify([]));
  const row = {
    teamName: '<script>alert(1)</script> & "Sox"',
    teamAbbr: "X&Y",
    wins: 50, losses: 30, pct: ".625",
    wcGamesBack: "5.0", isWildcardHolder: false,
    l10: "5-5", streak: "W1",
  };
  const html = st.renderWildcardRow(row);
  assert.ok(!html.includes("<script>alert(1)</script>"), "raw <script> must not appear");
  assert.ok(html.includes("&lt;script&gt;"), "should contain escaped script tag");
  assert.ok(html.includes("&amp;"), "ampersand escaped");
  assert.ok(html.includes("&quot;"), "double quote escaped");
});

test("renderWildcardRow data-away-team uses normalized lowercase form", () => {
  globalThis.localStorage.setItem("honkbal-favorite-teams", JSON.stringify([]));
  const row = {
    teamName: "Red Sox",
    teamAbbr: "BOS",
    wins: 50, losses: 30, pct: ".625",
    wcGamesBack: "5.0", isWildcardHolder: false,
    l10: "5-5", streak: "W1",
  };
  const html = st.renderWildcardRow(row);
  assert.match(html, /data-away-team="red sox"/, "should be normalized to lowercase");
  assert.match(html, /data-home-team="red sox"/);
});

test("renderWildcardRow highlights full MLB Stats API name matching a nickname favorite", () => {
  globalThis.localStorage.setItem("honkbal-favorite-teams", JSON.stringify(["yankees"]));
  const row = {
    teamName: "New York Yankees", teamAbbr: "NYY",
    wins: 95, losses: 67, pct: ".586",
    wcGamesBack: "+3.0", isWildcardHolder: true, l10: "7-3", streak: "W2",
  };
  const html = st.renderWildcardRow(row);
  assert.match(html, /favorite-game/);                     // highlight matcht ondanks volledige API-naam
  assert.match(html, /data-away-team="yankees"/);          // canonieke nickname
  assert.match(html, /<img[^>]+\/img\/yankees-fs8\.png/);  // logo, geen logofill
});

test("renderWildcardRow normalizes diamondbacks to d-backs in data attribute", () => {
  globalThis.localStorage.setItem("honkbal-favorite-teams", JSON.stringify([]));
  const row = {
    teamName: "Diamondbacks", teamAbbr: "AZ",
    wins: 50, losses: 30, pct: ".625",
    wcGamesBack: "5.0", isWildcardHolder: false, l10: "5-5", streak: "W1",
  };
  const html = st.renderWildcardRow(row);
  assert.match(html, /data-away-team="d-backs"/);
});

// --- storage listener registration (Fix 2: listener leak) ---
test("storage listener registered only once across two init() cycles", async () => {
  const { installFetch } = await import("./fetch-stub.js?" + Math.random());

  // Reset the module-level guard so this test starts fresh
  st._resetStorageListenerForTest();

  // Track storage listeners, counting only AFTER the guard is reset.
  // We record the count of window.addEventListener('storage') calls that happen
  // during the two init cycles. initFavorites adds its own listeners per call
  // but standings.js's own listener (behind the guard) must appear exactly once.
  const registeredFns = [];
  const origAdd = globalThis.window.addEventListener.bind(globalThis.window);
  globalThis.window.addEventListener = (evt, fn) => {
    if (evt === "storage") registeredFns.push(fn);
    origAdd(evt, fn);
  };

  // Provide the standings shell (productie-hooks: #standings-container + #standings-tabs).
  const container = globalThis.document.createElement("div");
  const tabsEl = globalThis.document.createElement("ul");
  const origQS = globalThis.document.querySelector.bind(globalThis.document);
  globalThis.document.querySelector = (sel) => {
    if (sel === "#standings-container") return container;
    if (sel === "#standings-tabs") return tabsEl;
    if (sel === "#standings-meta") return null;
    return origQS(sel);
  };

  installFetch({ "statsapi.mlb.com": { ok: false, status: 503, payload: null } });

  // First init cycle — standings listener should be registered (guard flips to true)
  const timer1 = await st.init(globalThis.document, { now: new Date(), fetch: globalThis.fetch });
  const countAfterFirst = registeredFns.length;

  // Second init cycle — guard is true, so standings listener must NOT be re-added
  const timer2 = await st.init(globalThis.document, { now: new Date(), fetch: globalThis.fetch });
  const countAfterSecond = registeredFns.length;

  // Cancel the 300s refresh timers so they don't fire after restoreDom()
  clearTimeout(timer1);
  clearTimeout(timer2);

  // Restore
  globalThis.window.addEventListener = origAdd;
  globalThis.document.querySelector = origQS;

  // The number of new storage listeners must NOT increase from first to second cycle.
  // (initFavorites may add its own per-cycle, but standings.js's guard prevents re-add.)
  // The guard should make the second cycle add FEWER storage listeners than the first.
  const addedInSecond = countAfterSecond - countAfterFirst;
  const addedInFirst = countAfterFirst;
  assert.ok(
    addedInSecond < addedInFirst,
    `Second init cycle added ${addedInSecond} storage listener(s) but should add fewer than first cycle (${addedInFirst}), proving the guard works`
  );
});
