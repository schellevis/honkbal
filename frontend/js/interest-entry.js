// Interest entry — honkbal.net v2.
// Externe versioned entrypoint (geen inline script blob, SPEC §6.1). Self-init op
// DOMContentLoaded, alleen als de bètafeature "interest" aanstaat (SPEC §6.9).
import { isBetaEnabled } from "./beta.js";
import { init } from "./interest.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  if (isBetaEnabled("interest")) init(globalThis.document);
});
