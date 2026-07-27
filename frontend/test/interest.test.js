import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, makeRow } from "./dom-stub.js";

let interest;
beforeEach(async () => {
  installDom();
  interest = await import("../js/interest.js?" + Math.random());
});
afterEach(() => restoreDom());

function scheduleTable(rows) {
  const doc = globalThis.document;
  const table = doc.createElement("table");
  table.classList.add("loadmore-container");
  const tbody = doc.createElement("tbody");
  for (const r of rows) tbody.appendChild(r);
  table.appendChild(tbody);
  doc.body.appendChild(table);
  return table;
}

function scoredRow(away, home, score) {
  const row = makeRow({ away, home });
  if (score !== undefined) row.dataset.interest = String(score);
  return row;
}

test("applyThreshold hides rows below the threshold and keeps the rest", () => {
  const low = scoredRow("mets", "phillies", 10);
  const high = scoredRow("red sox", "yankees", 80);
  scheduleTable([low, high]);

  interest.applyThreshold(globalThis.document, 50);
  assert.equal(low.classList.contains("interest-hidden"), true);
  assert.equal(high.classList.contains("interest-hidden"), false);
});

test("applyThreshold with threshold 0 shows everything again", () => {
  const low = scoredRow("mets", "phillies", 10);
  scheduleTable([low]);
  interest.applyThreshold(globalThis.document, 50);
  assert.equal(low.classList.contains("interest-hidden"), true);
  interest.applyThreshold(globalThis.document, 0);
  assert.equal(low.classList.contains("interest-hidden"), false);
});

test("rows without a data-interest score count as 0", () => {
  const unscored = scoredRow("cubs", "brewers", undefined);
  scheduleTable([unscored]);
  interest.applyThreshold(globalThis.document, 1);
  assert.equal(unscored.classList.contains("interest-hidden"), true);
  interest.applyThreshold(globalThis.document, 0);
  assert.equal(unscored.classList.contains("interest-hidden"), false);
});

test("threshold persists via localStorage and rejects garbage", () => {
  assert.equal(interest.getThreshold(), 0);
  interest.setThreshold(35);
  assert.equal(interest.getThreshold(), 35);
  globalThis.localStorage.setItem(interest.THRESHOLD_KEY, "onzin");
  assert.equal(interest.getThreshold(), 0);
  globalThis.localStorage.setItem(interest.THRESHOLD_KEY, "150");
  assert.equal(interest.getThreshold(), 0);
});
