import { test } from "node:test";
import assert from "node:assert/strict";
import { nyDateWindow, mmddyyyy, yyyymmdd, amsHHmm } from "../js/util/time.js";

const NOW = new Date("2026-06-21T12:00:00Z");

test("nyDateWindow returns 5 NY calendar dates descending", () => {
  const dates = nyDateWindow(NOW, 5);
  assert.equal(dates.length, 5);
  // Should include today and 4 days back in NY time (ET, UTC-4 in summer)
  // 2026-06-21 12:00 UTC = 08:00 ET → date is 2026-06-21
  const strs = dates.map((d) => yyyymmdd(d));
  assert.equal(strs[0], "20260621");
  assert.equal(strs[1], "20260620");
  assert.equal(strs[2], "20260619");
  assert.equal(strs[3], "20260618");
  assert.equal(strs[4], "20260617");
});

test("mmddyyyy formats correctly", () => {
  const d = new Date("2026-06-21T00:00:00Z");
  assert.equal(mmddyyyy(d), "06/21/2026");
});

test("yyyymmdd formats correctly", () => {
  const d = new Date("2026-01-05T00:00:00Z");
  assert.equal(yyyymmdd(d), "20260105");
});

test("amsHHmm summer (CEST = UTC+2)", () => {
  assert.equal(amsHHmm("2026-06-21T17:30:00Z"), "19:30");
});

test("amsHHmm winter (CET = UTC+1)", () => {
  assert.equal(amsHHmm("2026-01-01T12:00:00Z"), "13:00");
});
