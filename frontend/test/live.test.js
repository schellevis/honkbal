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

// --- applyNuAvondLabel ---
test("applyNuAvondLabel renames only the avond tab link", () => {
  const doc = globalThis.document;
  const avond = doc.createElement("a");
  avond.classList.add("nav-link");
  avond.setAttribute("href", "/avond.html?v1");
  avond.textContent = "avond";
  const nacht = doc.createElement("a");
  nacht.classList.add("nav-link");
  nacht.setAttribute("href", "/nacht.html?v1");
  nacht.textContent = "nacht";
  doc.body.appendChild(avond);
  doc.body.appendChild(nacht);

  live.applyNuAvondLabel(doc);
  assert.equal(avond.textContent, "nu + avond");
  assert.equal(nacht.textContent, "nacht");
});

// --- poll-vensters (SPEC §6.8) ---
test("parseLiveWindows accepts a JSON array and falls back to null on garbage", () => {
  assert.deepEqual(live.parseLiveWindows("[100,200]"), [100, 200]);
  assert.deepEqual(live.parseLiveWindows("[]"), []);
  assert.equal(live.parseLiveWindows(null), null);
  assert.equal(live.parseLiveWindows("geen json{"), null);
  assert.equal(live.parseLiveWindows('{"a":1}'), null);
});

test("nextPollDelay: in window → 0, before window → wait, after all windows → null", () => {
  const start = 1_000_000; // epoch-seconden
  const windows = [start];
  const startMs = start * 1000;
  assert.equal(live.nextPollDelay(windows, startMs + 1), 0);
  assert.equal(live.nextPollDelay(windows, startMs + live.LIVE_WINDOW_MS - 1), 0);
  assert.equal(live.nextPollDelay(windows, startMs - 60_000), 60_000);
  assert.equal(live.nextPollDelay(windows, startMs + live.LIVE_WINDOW_MS + 1), null);
  assert.equal(live.nextPollDelay([], startMs), null);
});

test("init does not call the API outside every poll window", async () => {
  const { doc, container } = containerDoc();
  container.setAttribute("data-live-windows", "[]");
  let calls = 0;
  const timer = await live.init(doc, { fetch: async () => { calls += 1; throw new Error("nee"); } });
  clearTimeout(timer);
  assert.equal(calls, 0);
  assert.equal(container.innerHTML, "");
});

test("init polls when now falls inside a poll window", async () => {
  const { doc, container } = containerDoc();
  const nowSec = Math.floor(Date.now() / 1000);
  container.setAttribute("data-live-windows", JSON.stringify([nowSec - 60]));
  installFetch({
    "statsapi.mlb.com": {
      ok: true, status: 200,
      payload: { dates: [{ games: [liveGame("New York Mets", "Philadelphia Phillies")] }] },
    },
  });
  const timer = await live.init(doc, { fetch: globalThis.fetch });
  clearTimeout(timer);
  assert.match(container.innerHTML, /nu bezig/);
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
