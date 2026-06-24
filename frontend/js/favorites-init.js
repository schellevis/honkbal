// Favorieten-highlight entry — honkbal.net v2 (SPEC §6.1)
// Self-init op DOMContentLoaded: past highlights toe en luistert op cross-tab storage.
import { initFavorites } from "./favorites.js";

globalThis.document.addEventListener("DOMContentLoaded", () => {
  initFavorites(globalThis.document);
});
