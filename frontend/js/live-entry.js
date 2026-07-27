// Live entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1; cachebuster via js_root,
// SPEC §7). Self-init op DOMContentLoaded. Alleen geladen op de avond-tab (SPEC §6.8).
import { init } from "./live.js";

globalThis.document.addEventListener("DOMContentLoaded", () => init(globalThis.document));
