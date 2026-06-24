// Nav team-select — honkbal.net v2 (SPEC §2)
// Navigeert naar <team>.html bij wijziging van de team-<select> in de nav,
// of bij klik op de "toon"-knop. Geen inline blob: geladen als /js/nav.js
// via base.html (ES-module, geen onclick-attribuut).
export function init(doc) {
  const sel = doc.querySelector ? doc.querySelector("[data-team-select]") : null;
  if (!sel) return;

  const go = () => {
    const slug = sel.value;
    if (slug) globalThis.location.assign(`/${slug}.html`);
  };

  sel.addEventListener("change", go);

  const btn = doc.querySelector ? doc.querySelector("[data-team-go]") : null;
  if (btn) btn.addEventListener("click", go);
}

globalThis.document.addEventListener("DOMContentLoaded", () => {
  init(globalThis.document);
});
