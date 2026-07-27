// interest.js — interessefilter-slider op schemapagina's (SPEC §6.9, bètafeature).
// Schema-rijen dragen een build-time data-interest-score (enrichment, SPEC §11); de slider
// verbergt rijen onder de gekozen drempel. Rijen zonder score tellen als 0.

export const THRESHOLD_KEY = "honkbal-interest-threshold";

export function getThreshold() {
  const raw = globalThis.localStorage.getItem(THRESHOLD_KEY);
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 && n <= 100 ? n : 0;
}

export function setThreshold(value) {
  globalThis.localStorage.setItem(THRESHOLD_KEY, String(value));
}

export function rowScore(row) {
  const n = Number(row.dataset?.interest ?? 0);
  return Number.isFinite(n) ? n : 0;
}

// Verbergt via een eigen CSS-klasse (niet row.hidden), zodat het filter nooit vecht met de
// dedup van de live-sectie (live.js gebruikt row.hidden, SPEC §6.8).
export function applyThreshold(doc, threshold) {
  for (const table of doc.querySelectorAll(".loadmore-container")) {
    for (const row of table.querySelectorAll("[data-away-team]")) {
      row.classList.toggle("interest-hidden", rowScore(row) < threshold);
    }
    // Dagkoppen zonder zichtbare rijen mee verbergen (thead hoort bij de volgende tbody).
    for (const tbody of table.querySelectorAll("tbody")) {
      const rows = tbody.querySelectorAll("[data-away-team]");
      const anyVisible = [...rows].some((r) => !r.classList.contains("interest-hidden"));
      const thead = tbody.previousElementSibling;
      if (thead && thead.classList) thead.classList.toggle("interest-hidden", !anyVisible);
    }
  }
}

export function init(doc) {
  const table = doc.querySelector ? doc.querySelector(".loadmore-container") : null;
  if (!table || !table.insertAdjacentHTML) return;

  table.insertAdjacentHTML(
    "beforebegin",
    `<div class="interest-filter">` +
      `<label class="interest-filter-label" for="interest-slider">interessefilter</label>` +
      `<input type="range" id="interest-slider" min="0" max="100" step="1">` +
      `<span id="interest-value" class="interest-filter-value" aria-live="polite"></span>` +
      `</div>`
  );

  const slider = doc.getElementById("interest-slider");
  const valueEl = doc.getElementById("interest-value");
  if (!slider) return;

  function apply(threshold) {
    if (valueEl) {
      valueEl.textContent = threshold > 0 ? `≥ ${threshold}` : "uit";
      if (valueEl.classList) valueEl.classList.toggle("is-active", threshold > 0);
    }
    // Gevulde track tot de thumb (CSS leest --interest-fill), zodat de slider dezelfde
    // accent-taal spreekt als de nav-pills.
    if (slider.style && slider.style.setProperty) {
      slider.style.setProperty("--interest-fill", `${threshold}%`);
    }
    applyThreshold(doc, threshold);
  }

  const initial = getThreshold();
  slider.value = String(initial);
  apply(initial);

  slider.addEventListener("input", () => {
    const threshold = Number(slider.value) || 0;
    setThreshold(threshold);
    apply(threshold);
  });

  // "Meer laden" plakt rijen bij (SPEC §6.6); herpas het filter op nieuwe rijen.
  if (globalThis.MutationObserver) {
    new MutationObserver(() => applyThreshold(doc, getThreshold()))
      .observe(table, { childList: true, subtree: true });
  }
}
