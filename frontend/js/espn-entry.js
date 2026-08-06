// Tv-gids entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1). Self-init op
// DOMContentLoaded op elke schemapagina: past de tv-gids-instellingen toe (SPEC §6.11).
import { init } from "./espn.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  init(globalThis.document);
});
