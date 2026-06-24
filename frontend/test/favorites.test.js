import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, dispatchStorageEvent, storageListenerCount } from "./dom-stub.js";

let fav;
beforeEach(async () => {
  installDom();
  fav = await import("../js/favorites.js?" + Math.random());
});
afterEach(() => restoreDom());

test("normalizeTeam handles +, case, dbacks", () => {
  assert.equal(fav.normalizeTeam("  Red+Sox "), "red sox");
  assert.equal(fav.normalizeTeam("Diamondbacks"), "d-backs");
  assert.equal(fav.normalizeTeam("DBacks"), "d-backs");
  assert.equal(fav.normalizeTeam("AL All-Stars"), "al all-stars");
});

test("get/set round-trip normalizes + dedupes", () => {
  fav.setFavorites(["Yankees", "yankees", "Red+Sox"]);
  assert.deepEqual(fav.getFavorites().sort(), ["red sox", "yankees"]);
});

test("getFavorites tolerates corrupt JSON", () => {
  globalThis.localStorage.setItem(fav.STORAGE_KEY, "{not json");
  assert.deepEqual(fav.getFavorites(), []);
});

test("isFavoriteMatchup matches either side", () => {
  fav.setFavorites(["mets"]);
  assert.equal(fav.isFavoriteMatchup("Mets", "Cubs"), true);
  assert.equal(fav.isFavoriteMatchup("Cubs", "mets"), true);
  assert.equal(fav.isFavoriteMatchup("Cubs", "Reds"), false);
});

test("settings-favorite (nickname) matches full MLB Stats API names", () => {
  // De gebruiker slaat via settings nicknames op; de API levert volledige namen.
  fav.setFavorites(["red sox", "yankees", "d-backs"]);
  assert.equal(fav.normalizeTeam("Boston Red Sox"), "red sox");
  assert.equal(fav.isFavoriteMatchup("Boston Red Sox", "Tampa Bay Rays"), true);
  assert.equal(fav.isFavoriteMatchup("Toronto Blue Jays", "New York Yankees"), true);
  assert.equal(fav.isFavoriteMatchup("Arizona Diamondbacks", "Colorado Rockies"), true);
  assert.equal(fav.isFavoriteMatchup("Chicago Cubs", "Cincinnati Reds"), false);
});

test("applyFavoriteHighlights toggles class idempotently", () => {
  fav.setFavorites(["dodgers"]);
  const root = globalThis.document.createElement("div");
  const r1 = globalThis.document.createElement("tr");
  r1.dataset.awayTeam = "dodgers"; r1.dataset.homeTeam = "giants";
  const r2 = globalThis.document.createElement("tr");
  r2.dataset.awayTeam = "cubs"; r2.dataset.homeTeam = "reds";
  root.appendChild(r1); root.appendChild(r2);
  fav.applyFavoriteHighlights(root);
  assert.ok(r1.classList.contains("favorite-game"));
  assert.ok(!r2.classList.contains("favorite-game"));
  // de-favorite → class wordt verwijderd bij her-apply
  fav.setFavorites([]);
  fav.applyFavoriteHighlights(root);
  assert.ok(!r1.classList.contains("favorite-game"));
});

test("initFavorites registers one storage listener and updates all registered roots", () => {
  const rootA = globalThis.document.createElement("div");
  const rowA = globalThis.document.createElement("tr");
  rowA.dataset.awayTeam = "dodgers";
  rowA.dataset.homeTeam = "giants";
  rootA.appendChild(rowA);

  const rootB = globalThis.document.createElement("div");
  const rowB = globalThis.document.createElement("tr");
  rowB.dataset.awayTeam = "mets";
  rowB.dataset.homeTeam = "cubs";
  rootB.appendChild(rowB);

  fav.initFavorites(rootA);
  fav.initFavorites(rootB);
  assert.equal(storageListenerCount(), 1);

  fav.setFavorites(["mets"]);
  dispatchStorageEvent(fav.STORAGE_KEY, JSON.stringify(["mets"]));
  assert.ok(!rowA.classList.contains("favorite-game"));
  assert.ok(rowB.classList.contains("favorite-game"));
});
