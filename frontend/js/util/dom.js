export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Klassen waarmee een module een schema-rij kan verbergen zonder row.hidden te claimen
// (dat hoort bij de live-dedup, SPEC §6.8): interessefilter (§6.9), veroudering (§6.10) en
// niet meer gespeelde games van een beslist serie (§6.12).
const HIDDEN_CLASSES = ["interest-hidden", "stale-hidden", "series-decided"];

export function isRowVisible(row) {
  if (row.hidden) return false;
  if (!row.classList) return true;
  return !HIDDEN_CLASSES.some((cls) => row.classList.contains(cls));
}

// Verberg elke dagkop (thead) waarvan de bijbehorende tbody geen zichtbare rij meer heeft.
// Een rij telt als zichtbaar zolang hij niet door de live-dedup (row.hidden, SPEC §6.8), niet
// door het interessefilter (class interest-hidden, SPEC §6.9) én niet door de veroudering
// (class stale-hidden, SPEC §6.10) verborgen is. Gedeeld door live.js, interest.js en stale.js:
// wie als laatste een rij wijzigt herberekent hiermee de koppen, zodat een kop nooit verweesd
// achterblijft (alle games bezig) of onterecht verborgen blijft.
export function syncDayHeaders(doc) {
  if (!doc.querySelectorAll) return;
  for (const table of doc.querySelectorAll(".loadmore-container")) {
    for (const tbody of table.querySelectorAll("tbody")) {
      const rows = [...tbody.querySelectorAll("[data-away-team]")];
      if (!rows.length) continue;
      const anyVisible = rows.some(isRowVisible);
      const thead = tbody.previousElementSibling;
      if (thead && thead.classList) thead.classList.toggle("day-hidden", !anyVisible);
    }
  }
}

export function el(tag, attrs = {}, children = []) {
  const parts = [`<${tag}`];
  for (const [k, v] of Object.entries(attrs)) {
    parts.push(` ${k}="${escapeHtml(v)}"`);
  }
  parts.push(">");
  for (const c of children) parts.push(c);
  parts.push(`</${tag}>`);
  return parts.join("");
}
