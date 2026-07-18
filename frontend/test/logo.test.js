import { test } from "node:test";
import assert from "node:assert/strict";
import { logoSlug, logoPicture, displayName } from "../js/util/logo.js";

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

test("displayName maps all-star pseudo-teams to their full league name", () => {
  // MLB Stats API clubName voor de all-star game is "American"/"National"
  assert.equal(displayName("American"), "American League");
  assert.equal(displayName("National"), "National League");
  assert.equal(displayName("AL All-Stars"), "American League");
  assert.equal(displayName("National League All-Stars"), "National League");
});

test("displayName leaves normal club names untouched", () => {
  assert.equal(displayName("Yankees"), "Yankees");
  assert.equal(displayName("Red Sox"), "Red Sox");
});

test("logoPicture emits the league logo (not text fallback) for all-star clubName", () => {
  const html = logoPicture(displayName("American"));
  assert.match(html, /<img[^>]+src="\/img\/american\+league-fs8\.png"/);
  assert.doesNotMatch(html, /logofill/);
});
