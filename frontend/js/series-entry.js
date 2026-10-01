// Series entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1). Self-init op
// DOMContentLoaded op elke schemapagina: zet de actuele postseason-serie-stand in de badges
// (SPEC §6.12). Zonder postseason-rijen doet de module niets (geen API-call).
import { init } from "./series.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  init(globalThis.document);
});
