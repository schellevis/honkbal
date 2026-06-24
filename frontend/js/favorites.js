import { canonicalTeam } from "./util/teams.js";

export const STORAGE_KEY = "honkbal-favorite-teams";
const _favoriteRoots = new Set();
let _storageListenerRegistered = false;

// Canonicaliseer naar de nickname-vorm uit config/teams.py. Dekt volledige MLB Stats API-namen
// ("Boston Red Sox" -> "red sox"), afkortingen en d-backs-varianten, zodat favorieten matchen
// ongeacht of de naam van settings, schedule-rijen of de API komt.
export function normalizeTeam(name) {
  return canonicalTeam(name);
}

export function getFavorites() {
  try {
    const raw = globalThis.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const seen = new Set();
    const result = [];
    for (const item of parsed) {
      const n = normalizeTeam(item);
      if (!seen.has(n)) { seen.add(n); result.push(n); }
    }
    return result;
  } catch {
    return [];
  }
}

export function setFavorites(list) {
  const seen = new Set();
  const result = [];
  for (const item of list) {
    const n = normalizeTeam(item);
    if (!seen.has(n)) { seen.add(n); result.push(n); }
  }
  globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify(result));
}

export function isFavoriteMatchup(away, home) {
  const favs = getFavorites();
  const a = normalizeTeam(away);
  const h = normalizeTeam(home);
  return favs.includes(a) || favs.includes(h);
}

export function applyFavoriteHighlights(root) {
  const target = root || globalThis.document;
  const rows = target.querySelectorAll("[data-away-team][data-home-team]");
  for (const row of rows) {
    const isFav = isFavoriteMatchup(row.dataset.awayTeam, row.dataset.homeTeam);
    if (isFav) {
      row.classList.add("favorite-game");
    } else {
      row.classList.remove("favorite-game");
    }
  }
}

export function initFavorites(root) {
  const target = root || globalThis.document;
  _favoriteRoots.add(target);
  applyFavoriteHighlights(target);

  if (_storageListenerRegistered) return;
  _storageListenerRegistered = true;
  globalThis.window.addEventListener("storage", (e) => {
    if (e.key !== STORAGE_KEY) return;
    for (const currentRoot of _favoriteRoots) {
      applyFavoriteHighlights(currentRoot);
    }
  });
}
