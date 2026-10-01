import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, makeRow } from "./dom-stub.js";
import { installFetch, restoreFetch, lastCalls } from "./fetch-stub.js";
import { seriesLabel, seriesRecord, seriesBadgeText, seriesDecided } from "../js/util/series.js";
import { renderScoresHtml } from "../js/scores.js";

let series;
beforeEach(async () => {
  installDom();
  series = await import("../js/series.js?" + Math.random());
});
afterEach(() => { restoreFetch(); restoreDom(); });

// Minimale MLB-Stats-API-schedulegame (hydrate=linescore,team) zoals in de postseason.
function psGame({
  away = "Philadelphia Phillies", home = "Atlanta Braves", gameType = "F", league = 104,
  n = 3, ifNecessary = "N", awayWins = 1, homeWins = 1, gameDate = "2026-10-01T18:00:00Z",
  state = "Live", gamesInSeries = 3,
} = {}) {
  return {
    gameType, seriesGameNumber: n, ifNecessary, gameDate, gamesInSeries,
    status: { abstractGameState: state, detailedState: "In Progress" },
    linescore: { currentInning: 2, isTopInning: false, outs: 0, offense: {} },
    teams: {
      away: { score: 0, leagueRecord: { wins: awayWins, losses: homeWins }, team: { name: away, league: { id: league } } },
      home: { score: 0, leagueRecord: { wins: homeWins, losses: awayWins }, team: { name: home, league: { id: league } } },
    },
  };
}

// --- util/series.js ---
test("seriesLabel: wild card, division, championship en world series", () => {
  assert.equal(seriesLabel(psGame()), "NLWC - Game 3");
  assert.equal(seriesLabel(psGame({ gameType: "D", league: 103, n: 5, ifNecessary: "Y" })), "ALDS - Game 5*");
  assert.equal(seriesLabel(psGame({ gameType: "L", n: 1 })), "NLCS - Game 1");
  assert.equal(seriesLabel(psGame({ gameType: "W", n: 7, ifNecessary: "Y" })), "World Series - Game 7*");
});

test("seriesLabel: null buiten de postseason", () => {
  assert.equal(seriesLabel(psGame({ gameType: "R" })), null);
  assert.equal(seriesLabel({}), null);
});

test("seriesRecord: stand met uitteam vooraan, 0-0 weggelaten", () => {
  assert.equal(seriesRecord(psGame({ awayWins: 0, homeWins: 1 })), "(0-1)");
  assert.equal(seriesRecord(psGame({ awayWins: 0, homeWins: 0 })), null);
  assert.equal(seriesRecord(psGame({ gameType: "R" })), null);
  assert.equal(seriesBadgeText(psGame({ awayWins: 2, homeWins: 1 })), "NLWC - Game 3 (2-1)");
});

test("seriesDecided: meer dan de helft van gamesInSeries gewonnen", () => {
  assert.equal(seriesDecided(psGame({ awayWins: 2, homeWins: 0 })), true);
  assert.equal(seriesDecided(psGame({ awayWins: 1, homeWins: 1 })), false);
  assert.equal(seriesDecided(psGame({ gameType: "D", gamesInSeries: 5, awayWins: 2, homeWins: 1 })), false);
  assert.equal(seriesDecided(psGame({ gameType: "D", gamesInSeries: 5, awayWins: 1, homeWins: 3 })), true);
  assert.equal(seriesDecided(psGame({ gamesInSeries: null, awayWins: 2, homeWins: 0 })), false);
});

// --- live-/scorerij ---
test("renderScoresHtml toont de serie-badge met stand in een postseason-rij", () => {
  const html = renderScoresHtml([psGame({ awayWins: 0, homeWins: 1 })], [], [], () => false);
  assert.match(html, /class="ps-score-row"/);
  assert.match(html, /<span class="stp">NLWC - Game 3 \(0-1\)<\/span>/);
});

test("renderScoresHtml: geen serie-badge in het reguliere seizoen", () => {
  const html = renderScoresHtml([psGame({ gameType: "R" })], [], [], () => false);
  assert.doesNotMatch(html, /series-line|ps-score-row/);
});

// --- statisch schema (series.js) ---
function psRow(away, home, startIso, label) {
  const row = makeRow({ away, home });
  row.classList.add("ps-row");
  row.dataset.start = String(Math.floor(Date.parse(startIso) / 1000));
  const badge = globalThis.document.createElement("span");
  badge.classList.add("stp");
  badge.textContent = label;
  row.appendChild(badge);
  globalThis.document.body.appendChild(row);
  return { row, badge };
}

test("init zet de actuele stand achter het label van de schemarij", async () => {
  const { badge } = psRow("phillies", "braves", "2026-10-01T18:00:00Z", "NLWC - Game 3");
  installFetch({ "statsapi.mlb.com": { ok: true, status: 200, payload: { dates: [{ games: [psGame()] }] } } });
  await series.init(globalThis.document);
  assert.equal(badge.textContent, "NLWC - Game 3 (1-1)");
  assert.match(lastCalls()[0], /gameType=F,D,L,W&startDate=09\/29\/2026&endDate=10\/03\/2026/);
});

test("applySeries vervangt een build-time stand en valt bij een andere serie-game terug op het build-label", () => {
  const { row: r1, badge: b1 } = psRow("phillies", "braves", "2026-10-01T18:00:00Z", "NLWC - Game 3 (0-1)");
  // Serie al beslist: game 3 bestaat niet meer in de API, game 2 van gisteren wel.
  const { row: r2, badge: b2 } = psRow("white sox", "astros", "2026-10-01T21:00:00Z", "ALWC - Game 3*");
  const games = [
    psGame(),
    psGame({ away: "Chicago White Sox", home: "Houston Astros", league: 103, n: 2, awayWins: 2, homeWins: 0, gameDate: "2026-09-30T21:00:00Z", state: "Final" }),
  ];
  assert.equal(series.applySeries([r1, r2], games), 2);
  assert.equal(b1.textContent, "NLWC - Game 3 (1-1)");
  assert.equal(b2.textContent, "ALWC - Game 3* (2-0)");
  // Serie beslist bij game 2 → de *-game wordt niet meer gespeeld en verdwijnt.
  assert.equal(r2.classList.contains("series-decided"), true);
  assert.equal(r1.classList.contains("series-decided"), false);
});

test("applySeries laat rijen zonder passende API-game ongemoeid", () => {
  const { row, badge } = psRow("mets", "dodgers", "2026-10-03T22:00:00Z", "NLDS");
  assert.equal(series.applySeries([row], [psGame()]), 0);
  assert.equal(badge.textContent, "NLDS");
});

test("init zonder postseason-rijen doet geen API-call", async () => {
  installFetch({});
  await series.init(globalThis.document);
  assert.equal(lastCalls().length, 0);
});

test("init bij netwerkfout laat het build-label staan", async () => {
  const { badge } = psRow("phillies", "braves", "2026-10-01T18:00:00Z", "NLWC - Game 3");
  installFetch({ "statsapi.mlb.com": new Error("offline") });
  await series.init(globalThis.document);
  assert.equal(badge.textContent, "NLWC - Game 3");
});

test("applySeries verbergt een gespeelde/lopende beslissende game zelf niet", () => {
  const { row } = psRow("white sox", "astros", "2026-09-30T21:00:00Z", "ALWC - Game 2");
  const g = psGame({ away: "Chicago White Sox", home: "Houston Astros", league: 103, n: 2, awayWins: 2, homeWins: 0, gameDate: "2026-09-30T21:00:00Z", state: "Final" });
  series.applySeries([row], [g]);
  assert.equal(row.classList.contains("series-decided"), false);
});

test("applySeries: lopende serie → volgende game blijft zichtbaar", () => {
  const { row } = psRow("phillies", "braves", "2026-10-02T18:00:00Z", "NLWC - Game 3");
  const g = psGame({ n: 2, awayWins: 1, homeWins: 1, gameDate: "2026-10-01T18:00:00Z", state: "Final" });
  series.applySeries([row], [g]);
  assert.equal(row.classList.contains("series-decided"), false);
});
