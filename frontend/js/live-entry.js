// Live entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1; cachebuster via js_root,
// SPEC §7). Self-init op DOMContentLoaded, alleen op de avond-tab én als de bètafeature
// "live" aanstaat (SPEC §6.8/§6.9).
import { isBetaEnabled } from "./beta.js";
import { init, applyNuAvondLabel } from "./live.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  if (!isBetaEnabled("live")) return;
  applyNuAvondLabel(globalThis.document);
  init(globalThis.document);
});
