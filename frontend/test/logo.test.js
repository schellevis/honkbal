import { test } from "node:test";
import assert from "node:assert/strict";
import { logoSlug, logoPicture } from "../js/util/logo.js";

test("logoSlug maps full MLB Stats API names to existing logo slugs", () => {
  assert.equal(logoSlug("Boston Red Sox"), "red+sox");
  assert.equal(logoSlug("New York Yankees"), "yankees");
  assert.equal(logoSlug("Arizona Diamondbacks"), "d-backs");
  assert.equal(logoSlug("Toronto Blue Jays"), "blue+jays");
  assert.equal(logoSlug("Chicago White Sox"), "white+sox");
});

test("logoSlug keeps all-star + already-canonical mapping", () => {
  assert.equal(logoSlug("AL All-Stars"), "american+league");
  assert.equal(logoSlug("red sox"), "red+sox");
});

test("logoPicture emits <img> (not text fallback) for full API names", () => {
  const html = logoPicture("Boston Red Sox");
  assert.match(html, /<img[^>]+src="\/img\/red\+sox-fs8\.png"/);
  assert.doesNotMatch(html, /logofill/);
});

test("logoPicture falls back to logofill for unknown teams", () => {
  assert.match(logoPicture("River Cats"), /class="logofill"/);
});
