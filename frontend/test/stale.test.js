import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, makeRow } from "./dom-stub.js";

let stale;
beforeEach(async () => {
  installDom();
  stale = await import("../js/stale.js?" + Math.random());
});
afterEach(() => restoreDom());

// Donderdag 30 juli 2026, 05:55 Amsterdam — het moment uit de bugmelding.
const NOW = Date.parse("2026-07-30T05:55:00+02:00");
const HOUR = 3600 * 1000;

function epoch(iso) {
  return Math.floor(Date.parse(iso) / 1000);
}

// table.loadmore-container > (thead, tbody[data-date])* zoals _rows.html rendert.
function scheduleTable(days) {
  const doc = globalThis.document;
  const table = doc.createElement("table");
  table.classList.add("loadmore-container");
  for (const day of days) {
    const thead = doc.createElement("thead");
    day.thead = thead;
    table.appendChild(thead);
    const tbody = doc.createElement("tbody");
    if (day.date) tbody.dataset.date = day.date;
    for (const row of day.rows) tbody.appendChild(row);
    table.appendChild(tbody);
  }
  doc.body.appendChild(table);
  return table;
}

function timedRow(away, home, startIso) {
  const row = makeRow({ away, home });
  if (startIso) row.dataset.start = String(epoch(startIso));
  return row;
}

test("rij van gisteravond die ruim buiten het grace-window ligt wordt verborgen", () => {
  // Woensdag 21:45 — op de nachtbuild (01:00) nog binnen grace, om 05:55 acht uur oud.
  const yesterday = timedRow("brewers", "giants", "2026-07-29T21:45:00+02:00");
  scheduleTable([{ date: "2026-07-29", rows: [yesterday] }]);

  assert.equal(stale.pruneStaleRows(globalThis.document, NOW), 1);
  assert.equal(yesterday.classList.contains("stale-hidden"), true);
});

test("wedstrijd binnen het grace-window blijft staan (vermoedelijk nog bezig)", () => {
  const running = timedRow("dodgers", "mariners", new Date(NOW - 2 * HOUR).toISOString());
  const upcoming = timedRow("rangers", "rays", "2026-07-30T18:10:00+02:00");
  scheduleTable([{ date: "2026-07-30", rows: [running, upcoming] }]);

  assert.equal(stale.pruneStaleRows(globalThis.document, NOW), 0);
  assert.equal(running.classList.contains("stale-hidden"), false);
  assert.equal(upcoming.classList.contains("stale-hidden"), false);
});

test("de grens ligt exact op start + GRACE_MS", () => {
  const justInside = timedRow("cubs", "reds", new Date(NOW - stale.GRACE_MS + 1000).toISOString());
  const justOutside = timedRow("mets", "phillies", new Date(NOW - stale.GRACE_MS).toISOString());
  scheduleTable([{ date: "2026-07-30", rows: [justInside, justOutside] }]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(justInside.classList.contains("stale-hidden"), false);
  assert.equal(justOutside.classList.contains("stale-hidden"), true);
});

test("TBD-rijen verouderen datum-granulair op de dagdatum", () => {
  const yesterdayTbd = makeRow({ away: "yankees", home: "red sox" });
  const todayTbd = makeRow({ away: "astros", home: "angels" });
  scheduleTable([
    { date: "2026-07-29", rows: [yesterdayTbd] },
    { date: "2026-07-30", rows: [todayTbd] },
  ]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(yesterdayTbd.classList.contains("stale-hidden"), true);
  assert.equal(todayTbd.classList.contains("stale-hidden"), false);
});

test("rij zonder starttijd én zonder dagdatum blijft zichtbaar", () => {
  const orphan = makeRow({ away: "twins", home: "royals" });
  scheduleTable([{ rows: [orphan] }]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(orphan.classList.contains("stale-hidden"), false);
});

test("onleesbare data-start verbergt niets", () => {
  const broken = makeRow({ away: "padres", home: "rockies" });
  broken.dataset.start = "later";
  scheduleTable([{ date: "2026-07-29", rows: [broken] }]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(broken.classList.contains("stale-hidden"), false);
});

test("dagkop verdwijnt mee zodra al zijn rijen verouderd zijn", () => {
  const day = {
    date: "2026-07-29",
    rows: [
      timedRow("brewers", "giants", "2026-07-29T21:45:00+02:00"),
      timedRow("rockies", "padres", "2026-07-29T22:10:00+02:00"),
    ],
  };
  const today = { date: "2026-07-30", rows: [timedRow("rangers", "rays", "2026-07-30T18:10:00+02:00")] };
  scheduleTable([day, today]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(day.thead.classList.contains("day-hidden"), true);
  assert.equal(today.thead.classList.contains("day-hidden"), false);
});

test("veroudering laat row.hidden van de live-dedup ongemoeid", () => {
  // live.js claimt row.hidden (SPEC §6.8); stale.js gebruikt een eigen klasse.
  const live = timedRow("dodgers", "mariners", new Date(NOW - 2 * HOUR).toISOString());
  live.hidden = true;
  scheduleTable([{ date: "2026-07-30", rows: [live] }]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(live.hidden, true);
  assert.equal(live.classList.contains("stale-hidden"), false);
});

test("een teruggedraaide klok maakt een eerder verborgen rij weer zichtbaar", () => {
  const row = timedRow("brewers", "giants", "2026-07-29T21:45:00+02:00");
  scheduleTable([{ date: "2026-07-29", rows: [row] }]);

  stale.pruneStaleRows(globalThis.document, NOW);
  assert.equal(row.classList.contains("stale-hidden"), true);
  stale.pruneStaleRows(globalThis.document, Date.parse("2026-07-29T23:00:00+02:00"));
  assert.equal(row.classList.contains("stale-hidden"), false);
});

test("init prunet direct en werkt zonder schematabel", () => {
  const row = timedRow("brewers", "giants", "2026-07-29T21:45:00+02:00");
  scheduleTable([{ date: "2026-07-29", rows: [row] }]);
  // Zonder recheck-timer: init mag de eventloop niet openhouden in tests.
  assert.equal(stale.init(globalThis.document, { recheckMs: 0 }), null);
  // De echte klok staat ná 2026-07-29, dus de rij is verouderd.
  assert.equal(row.classList.contains("stale-hidden"), true);

  restoreDom();
  installDom();
  assert.equal(stale.init(globalThis.document, { recheckMs: 0 }), null);
});
