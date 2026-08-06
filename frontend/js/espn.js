// espn.js — tv-gids-instellingen (SPEC §6.11).
//
// Zenderlogo's (SPEC §3.3) staan voor iedereen aan; wie wil kan ze uitzetten of beperken tot
// uitzendingen met Nederlands commentaar. Opslag per browser, net als favorieten. De defaults
// vereisen géén localStorage-entry: zonder opgeslagen keuze zijn de logo's zichtbaar en staat
// het NL-filter uit.
//
// Toepassing via body-klassen (espn-off / espn-nl-only) in plaats van per-rij JS: de CSS-regels
// gelden dan vanzelf ook voor tail-rijen die "meer laden" later bijplakt (SPEC §6.6), zonder
// MutationObserver of coördinatie met stale-/interessefilter.

export const LOGOS_KEY = "honkbal-espn-logos";
export const NL_ONLY_KEY = "honkbal-espn-nl-only";

function read(key) {
  try {
    return globalThis.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getShowLogos() {
  return read(LOGOS_KEY) !== "0";
}

export function setShowLogos(on) {
  globalThis.localStorage.setItem(LOGOS_KEY, on ? "1" : "0");
}

export function getNlOnly() {
  return read(NL_ONLY_KEY) === "1";
}

export function setNlOnly(on) {
  globalThis.localStorage.setItem(NL_ONLY_KEY, on ? "1" : "0");
}

export function applyTvClasses(doc) {
  const body = doc.body;
  if (!body || !body.classList) return;
  body.classList.toggle("espn-off", !getShowLogos());
  body.classList.toggle("espn-nl-only", getNlOnly());
}

// Tv-checkboxes op de instellingenpagina dragen name="tv" (values "logos"/"nlonly");
// wijzigingen worden direct opgeslagen, zoals bij bètafeatures.
export function initTvCheckboxes(doc) {
  const boxes = [...doc.querySelectorAll('input[type="checkbox"]')]
    .filter((cb) => cb.name === "tv");
  for (const cb of boxes) {
    cb.checked = cb.value === "logos" ? getShowLogos() : getNlOnly();
    cb.addEventListener("change", () => {
      if (cb.value === "logos") setShowLogos(cb.checked);
      else setNlOnly(cb.checked);
      applyTvClasses(doc);
    });
  }
}

export function init(doc) {
  applyTvClasses(doc);
  if (!globalThis.window || !globalThis.window.addEventListener) return;
  // Cross-tab sync: instellingen gewijzigd op /settings.html werken direct door in open tabs.
  globalThis.window.addEventListener("storage", (e) => {
    if (e.key !== LOGOS_KEY && e.key !== NL_ONLY_KEY) return;
    applyTvClasses(doc);
  });
}
