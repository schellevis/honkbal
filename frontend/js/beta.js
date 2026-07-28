// beta.js — bètafeatures (SPEC §6.9).
// Opt-in via de instellingenpagina; opslag als JSON-array van feature-namen in localStorage.
// Browser-lokaal, net als favorieten.

export const BETA_KEY = "honkbal-beta-features";

// Bekende features; onbekende namen worden bij het opslaan weggefilterd zodat een oude
// localStorage-payload geen spookfeatures kan aanzetten. Uitgestudeerde features (zoals "live",
// dat nu voor iedereen aanstaat) verdwijnen hier: bestaande payloads verliezen de naam vanzelf.
export const BETA_FEATURES = ["interest"];

export function getBetaFeatures() {
  try {
    const raw = globalThis.localStorage.getItem(BETA_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((f) => BETA_FEATURES.includes(f));
  } catch {
    return [];
  }
}

export function setBetaFeatures(features) {
  const clean = [...new Set(features)].filter((f) => BETA_FEATURES.includes(f));
  globalThis.localStorage.setItem(BETA_KEY, JSON.stringify(clean));
}

export function isBetaEnabled(feature) {
  return getBetaFeatures().includes(feature);
}
