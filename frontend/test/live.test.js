import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, makeRow } from "./dom-stub.js";
import { installFetch, restoreFetch } from "./fetch-stub.js";

let live;
beforeEach(async () => {
  installDom();
  live = await import("../js/live.js?" + Math.random());
});
afterEach(() => { restoreFetch(); restoreDom(); });

function liveGame(away, home, { awayScore = 1, homeScore = 0 } = {}) {
  return {
    gameDate: "2026-07-27T00:10:00Z",
    status: { abstractGameState: "Live", detailedState: "In Progress" },
    linescore: { currentInning: 5, isTopInning: true, outs: 1, offense: {} },
    teams: {
      away: { score: awayScore, team: { name: away, abbreviation: "AWY" } },
      home: { score: homeScore, team: { name: home, abbreviation: "HOM" } },
    },
  };
}

// --- renderLiveHtml ---
test("renderLiveHtml renders a 'nu bezig' table with scores for live games", () => {
  const html = live.renderLiveHtml([liveGame("New York Mets", "Philadelphia Phillies")], [], () => false);
  assert.match(html, /nu bezig/);
  assert.match(html, /data-away-team="mets"/);
  assert.match(html, /data-home-team="phillies"/);
  assert.match(html, /<strong[^>]*>1<\/strong>/); // score zichtbaar
});

test("renderLiveHtml returns empty string when there is nothing live", () => {
  assert.equal(live.renderLiveHtml([], [], () => false), "");
});

// --- syncHiddenRows ---
function scheduleTable(rows) {
  const table = globalThis.document.createElement("table");
  table.classList.add("loadmore-container");
  for (const r of rows) table.appendChild(r);
  globalThis.document.body.appendChild(table);
  return table;
}

test("syncHiddenRows hides the static row of a live game and restores it afterwards", () => {
  const row = makeRow({ away: "mets", home: "phillies" });
  const other = makeRow({ away: "cubs", home: "brewers" });
  scheduleTable([row, other]);

  live.syncHiddenRows(globalThis.document, [liveGame("New York Mets", "Philadelphia Phillies")]);
  assert.equal(row.hidden, true);
  assert.equal(other.hidden, false);

  // Wedstrijd afgelopen → volgende sync zonder die game → rij komt terug (SPEC §6.8).
  live.syncHiddenRows(globalThis.document, []);
  assert.equal(row.hidden, false);
});

test("syncHiddenRows hides only one row per live game for a doubleheader", () => {
  const row1 = makeRow({ away: "mets", home: "phillies" });
  const row2 = makeRow({ away: "mets", home: "phillies" });
  scheduleTable([row1, row2]);

  live.syncHiddenRows(globalThis.document, [liveGame("New York Mets", "Philadelphia Phillies")]);
  assert.equal([row1, row2].filter((r) => r.hidden).length, 1);
});

// --- init ---
function containerDoc() {
  const doc = globalThis.document;
  const container = doc.createElement("div");
  container.id = "live-container";
  doc.registerElement(container);
  doc.querySelector = (sel) => (sel === "#live-container" ? container : doc.body.querySelector(sel));
  return { doc, container };
}

test("init renders live games from both fetched days into #live-container", async () => {
  const { doc, container } = containerDoc();
  installFetch({
    "statsapi.mlb.com": {
      ok: true, status: 200,
      payload: { dates: [{ games: [liveGame("New York Mets", "Philadelphia Phillies")] }] },
    },
  });
  const timer = await live.init(doc, { fetch: globalThis.fetch });
  clearTimeout(timer);
  assert.match(container.innerHTML, /nu bezig/);
  assert.match(container.innerHTML, /data-away-team="mets"/);
});

test("init leaves the section untouched on network failure", async () => {
  const { doc, container } = containerDoc();
  container.innerHTML = "<p>bestaand</p>";
  installFetch({ "statsapi.mlb.com": new Error("offline") });
  const timer = await live.init(doc, { fetch: globalThis.fetch });
  clearTimeout(timer);
  assert.equal(container.innerHTML, "<p>bestaand</p>");
});

test("init clears the section when no games are live", async () => {
  const { doc, container } = containerDoc();
  container.innerHTML = "<p>oud</p>";
  installFetch({
    "statsapi.mlb.com": { ok: true, status: 200, payload: { dates: [] } },
  });
  const timer = await live.init(doc, { fetch: globalThis.fetch });
  clearTimeout(timer);
  assert.equal(container.innerHTML, "");
});
