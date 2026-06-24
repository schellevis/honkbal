import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssPath = join(__dirname, "../css/style.css");
const css = readFileSync(cssPath, "utf8");

const REQUIRED_SELECTORS = [
  "favorite-game",
  ".st",
  ".stp",
  "stp-bases",
  "stp-outs",
  "score-abbr",
  ".loadmore",
  "wildcard-holder",
  "empty-state",
  "scores-status",
  "loadmore-msg",
];

for (const sel of REQUIRED_SELECTORS) {
  test(`CSS contains selector: ${sel}`, () => {
    assert.ok(css.includes(sel), `Missing: ${sel}`);
  });
}
