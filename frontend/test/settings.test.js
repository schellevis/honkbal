import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, dispatchStorageEvent, storageListenerCount } from "./dom-stub.js";

let settings, fav;

function buildSettingsDom(checkedTeams = []) {
  const doc = globalThis.document;
  doc.body.innerHTML = "";

  // Create favorites grid with checkboxes
  const grid = doc.createElement("div");
  grid.classList.add("favorites-grid");

  const teams = ["yankees", "red sox", "dodgers", "mets", "cubs"];
  for (const team of teams) {
    const label = doc.createElement("label");
    label.classList.add("favorite-option");
    const input = doc.createElement("input");
    input.type = "checkbox";
    input.value = team;
    input.name = "team";
    if (checkedTeams.includes(team)) input.checked = true;
    label.appendChild(input);
    grid.appendChild(label);
  }
  doc.body.appendChild(grid);

  const statusEl = doc.createElement("div");
  statusEl.id = "favorites-status";
  statusEl.classList.add("favorites-status");
  doc.body.appendChild(statusEl);
  doc.registerElement(statusEl);

  const saveBtn = doc.createElement("button");
  saveBtn.id = "favorites-save";
  doc.body.appendChild(saveBtn);
  doc.registerElement(saveBtn);

  const clearBtn = doc.createElement("button");
  clearBtn.id = "favorites-clear";
  doc.body.appendChild(clearBtn);
  doc.registerElement(clearBtn);

  return doc;
}

beforeEach(async () => {
  installDom();
  fav = await import("../js/favorites.js?" + Math.random());
  settings = await import("../js/settings.js?" + Math.random());
});
afterEach(() => restoreDom());

test("buildState returns normalized deduped list from checked names", () => {
  const result = settings.buildState(["Yankees", "yankees", "Red+Sox"]);
  assert.deepEqual(result.sort(), ["red sox", "yankees"]);
});

test("syncCheckboxes checks correct boxes from favorites", () => {
  const doc = buildSettingsDom();
  fav.setFavorites(["yankees", "mets"]);
  settings.syncCheckboxes(doc, fav.getFavorites());
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  const checked = [...checkboxes].filter((c) => c.checked).map((c) => c.value);
  assert.deepEqual(checked.sort(), ["mets", "yankees"]);
  const unchecked = [...checkboxes].filter((c) => !c.checked).map((c) => c.value);
  assert.ok(unchecked.includes("dodgers"));
});

test("init syncs checkboxes from getFavorites on load", async () => {
  const doc = buildSettingsDom();
  fav.setFavorites(["dodgers"]);
  settings.init(doc);
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  const checked = [...checkboxes].filter((c) => c.checked).map((c) => c.value);
  assert.deepEqual(checked, ["dodgers"]);
});

test("save button sets favorites and shows status message", async () => {
  const doc = buildSettingsDom();
  settings.init(doc);
  // Check yankees and mets manually
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  for (const cb of checkboxes) {
    if (cb.value === "yankees" || cb.value === "mets") cb.checked = true;
  }
  // Simulate save click
  const saveBtn = doc.getElementById("favorites-save");
  saveBtn.dispatchEvent({ type: "click" });
  // Check favorites were saved
  const saved = fav.getFavorites();
  assert.ok(saved.includes("yankees"));
  assert.ok(saved.includes("mets"));
  // Status element should be visible (non-empty text)
  const statusEl = doc.getElementById("favorites-status");
  assert.ok(statusEl.textContent.length > 0 || statusEl.style.display !== "none");
});

test("clear button empties all checkboxes and favorites", () => {
  const doc = buildSettingsDom(["yankees", "mets"]);
  fav.setFavorites(["yankees", "mets"]);
  settings.init(doc);
  const clearBtn = doc.getElementById("favorites-clear");
  clearBtn.dispatchEvent({ type: "click" });
  const saved = fav.getFavorites();
  assert.deepEqual(saved, []);
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  const anyChecked = [...checkboxes].some((c) => c.checked);
  assert.equal(anyChecked, false);
});

test("storage event resyncs checkboxes cross-tab", () => {
  const doc = buildSettingsDom();
  settings.init(doc);
  // Simulate another tab setting favorites
  fav.setFavorites(["cubs"]);
  dispatchStorageEvent("honkbal-favorite-teams", JSON.stringify(["cubs"]));
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  const checked = [...checkboxes].filter((c) => c.checked).map((c) => c.value);
  assert.deepEqual(checked, ["cubs"]);
});

test("init registers one storage listener across repeated settings init calls", () => {
  const docA = buildSettingsDom();
  settings.init(docA);
  const docB = buildSettingsDom();
  settings.init(docB);

  assert.equal(storageListenerCount(), 1);

  fav.setFavorites(["mets"]);
  dispatchStorageEvent("honkbal-favorite-teams", JSON.stringify(["mets"]));
  const checked = [...docB.querySelectorAll('input[type="checkbox"]')]
    .filter((c) => c.checked)
    .map((c) => c.value);
  assert.deepEqual(checked, ["mets"]);
});
