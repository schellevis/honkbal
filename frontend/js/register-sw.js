// Service-worker registratie — honkbal.net v2 (SPEC §6.5)
// Geen inline blob: dit kleine module wordt als /js/register-sw.js geladen op elke
// gebouwde pagina via base.html. De service worker zelf staat op /sw.js (root, scope "/").
if ("serviceWorker" in globalThis.navigator) {
  globalThis.navigator.serviceWorker.register("/sw.js", {
    scope: "/",
    updateViaCache: "none",
  });
}
