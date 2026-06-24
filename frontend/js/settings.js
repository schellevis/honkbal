import { getFavorites, setFavorites, normalizeTeam, applyFavoriteHighlights, STORAGE_KEY } from "./favorites.js";

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

export function syncCheckboxes(doc, favorites) {
  const favSet = new Set(favorites.map((f) => normalizeTeam(f)));
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  for (const cb of checkboxes) {
    cb.checked = favSet.has(normalizeTeam(cb.value));
  }
}

function getCheckedValues(doc) {
  const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
  const values = [];
  for (const cb of checkboxes) {
    if (cb.checked) values.push(cb.value);
  }
  return values;
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
      const checkboxes = doc.querySelectorAll('input[type="checkbox"]');
      for (const cb of checkboxes) cb.checked = false;
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
