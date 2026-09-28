// Live entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1; cachebuster via js_root,
// SPEC §7). Self-init op DOMContentLoaded, op de avond-tab en altijd op de voorpagina
// (SPEC §6.8). De sectie is geen bètafeature meer: hij staat voor iedereen aan.
import { init, applyNuAvondLabel } from "./live.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  applyNuAvondLabel(globalThis.document);
  init(globalThis.document);
});
