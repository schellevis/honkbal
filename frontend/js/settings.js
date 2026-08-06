import { getFavorites, setFavorites, normalizeTeam, applyFavoriteHighlights, STORAGE_KEY } from "./favorites.js";
import { getBetaFeatures, setBetaFeatures } from "./beta.js";
import { initTvCheckboxes } from "./espn.js";

const _settingsDocs = new Set();
let _storageListenerRegistered = false;

export function buildState(checkedNames) {
  const seen = new Set();
  const result = [];
  for (const name of checkedNames) {
    const n = normalizeTeam(name);
    if (!seen.has(n)) { seen.add(n); result.push(n); }
  }
  return result;
}

// Team-checkboxes dragen name="team"; bèta-checkboxes name="beta" (aparte opslag/flow).
function teamCheckboxes(doc) {
  return [...doc.querySelectorAll('input[type="checkbox"]')].filter((cb) => cb.name === "team");
}

function betaCheckboxes(doc) {
  return [...doc.querySelectorAll('input[type="checkbox"]')].filter((cb) => cb.name === "beta");
}

export function syncCheckboxes(doc, favorites) {
  const favSet = new Set(favorites.map((f) => normalizeTeam(f)));
  for (const cb of teamCheckboxes(doc)) {
    cb.checked = favSet.has(normalizeTeam(cb.value));
  }
}

function getCheckedValues(doc) {
  const values = [];
  for (const cb of teamCheckboxes(doc)) {
    if (cb.checked) values.push(cb.value);
  }
  return values;
}

// Bètafeatures: sync uit localStorage en sla direct op bij wijziging (geen opslaan-knop nodig).
export function initBetaCheckboxes(doc) {
  const boxes = betaCheckboxes(doc);
  const enabled = new Set(getBetaFeatures());
  for (const cb of boxes) {
    cb.checked = enabled.has(cb.value);
    cb.addEventListener("change", () => {
      setBetaFeatures(boxes.filter((b) => b.checked).map((b) => b.value));
    });
  }
}

let _statusTimer = null;

function showStatus(doc, message) {
  const statusEl = doc.getElementById("favorites-status");
  if (!statusEl) return;
  statusEl.textContent = message;
  if (statusEl.style) statusEl.style.display = "";
  if (_statusTimer) clearTimeout(_statusTimer);
  _statusTimer = setTimeout(() => {
    if (statusEl.style) statusEl.style.display = "none";
    statusEl.textContent = "";
  }, 2500);
}

export function init(doc) {
  _settingsDocs.add(doc);

  // Sync checkboxes from current favorites on load
  syncCheckboxes(doc, getFavorites());
  initBetaCheckboxes(doc);
  initTvCheckboxes(doc);

  const saveBtn = doc.getElementById("favorites-save");
  const clearBtn = doc.getElementById("favorites-clear");

  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      const checked = getCheckedValues(doc);
      const normalized = buildState(checked);
      setFavorites(normalized);
      applyFavoriteHighlights(doc);
      showStatus(doc, "Opgeslagen!");
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      for (const cb of teamCheckboxes(doc)) cb.checked = false;
      setFavorites([]);
      applyFavoriteHighlights(doc);
      showStatus(doc, "Favorieten gewist.");
    });
  }

  // Cross-tab sync
  if (_storageListenerRegistered) return;
  _storageListenerRegistered = true;
  globalThis.window.addEventListener("storage", (e) => {
    if (e.key !== STORAGE_KEY) return;
    for (const currentDoc of _settingsDocs) {
      syncCheckboxes(currentDoc, getFavorites());
    }
  });
}
