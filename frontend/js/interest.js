// interest.js — interessefilter-slider op schemapagina's (SPEC §6.9, bètafeature).
// Schema-rijen dragen een build-time data-interest-percentiel (enrichment, SPEC §11); de
// slider verbergt rijen onder het gekozen percentiel ("drempel 75" = toon de top 25%).
// Rijen zónder attribuut (postseason, all-star) vallen buiten het filter en blijven altijd
// zichtbaar; draagt geen enkele rij een score (postseason-fase), dan komt er geen slider.

import { syncDayHeaders } from "./util/dom.js";

export const THRESHOLD_KEY = "honkbal-interest-threshold";

export function getThreshold() {
  const raw = globalThis.localStorage.getItem(THRESHOLD_KEY);
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 && n <= 100 ? n : 0;
}

export function setThreshold(value) {
  globalThis.localStorage.setItem(THRESHOLD_KEY, String(value));
}

// Percentiel van een rij, of null voor rijen zonder data-interest (buiten het filter).
export function rowScore(row) {
  const raw = row.dataset?.interest;
  if (raw === undefined) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

// Verbergt via een eigen CSS-klasse (niet row.hidden), zodat het filter nooit vecht met de
// dedup van de live-sectie (live.js gebruikt row.hidden, SPEC §6.8).
export function applyThreshold(doc, threshold) {
  for (const table of doc.querySelectorAll(".loadmore-container")) {
    for (const row of table.querySelectorAll("[data-away-team]")) {
      const score = rowScore(row);
      row.classList.toggle("interest-hidden", score !== null && score < threshold);
    }
  }
  // Dagkoppen zonder zichtbare rijen mee verbergen (gedeeld met de live-dedup, SPEC §6.8/§6.9).
  syncDayHeaders(doc);
}

export function init(doc) {
  const table = doc.querySelector ? doc.querySelector(".loadmore-container") : null;
  if (!table || !table.insertAdjacentHTML) return;
  // Geen enkele gescoorde rij (postseason-fase, SPEC §11) → filter heeft niets te filteren.
  if (!table.querySelector("[data-interest]")) return;

  table.insertAdjacentHTML(
    "beforebegin",
    `<div class="interest-filter">` +
      `<label class="interest-filter-label" for="interest-slider">interessefilter</label>` +
      `<input type="range" id="interest-slider" min="0" max="95" step="5">` +
      `<span id="interest-value" class="interest-filter-value" aria-live="polite"></span>` +
      `</div>`
  );

  const slider = doc.getElementById("interest-slider");
  const valueEl = doc.getElementById("interest-value");
  if (!slider) return;

  function apply(threshold) {
    if (valueEl) {
      valueEl.textContent = threshold > 0 ? `top ${100 - threshold}%` : "uit";
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
