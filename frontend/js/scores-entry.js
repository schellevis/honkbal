// Scores entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1; cachebuster via ?asset_version
// in de template, SPEC §7). Self-init op DOMContentLoaded.
import { init } from "./scores.js";

globalThis.document.addEventListener("DOMContentLoaded", () => init(globalThis.document));
