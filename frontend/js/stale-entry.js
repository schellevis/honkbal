// Stale entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1). Self-init op
// DOMContentLoaded op elke schemapagina: laat het statische schema mee verouderen met de
// klok van de bezoeker (SPEC §6.10).
import { init } from "./stale.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  init(globalThis.document);
});
