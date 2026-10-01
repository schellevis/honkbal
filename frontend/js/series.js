// series.js — postseason-serie-stand in het statische schema (SPEC §6.12).
// De build zet het serie-label in de badge (`.stp`) van elke postseason-rij (`tr.ps-row`); deze
// module haalt bij het laden de actuele stand op via de MLB Stats API en zet die erachter
// ("NLWC - Game 3 (1-1)"). Faalt stil: zonder API blijft het build-time label staan.
import { mmddyyyy } from "./util/time.js";
import { seriesLabel, seriesRecord } from "./util/series.js";
import { normalizeTeam } from "./favorites.js";

const DAY_MS = 24 * 3600 * 1000;
// Een rij hoort bij de API-game van hetzelfde teampaar met de dichtstbijzijnde starttijd; verder
// dan een dag ernaast is het een andere wedstrijd (bv. een serie die al voorbij is).
export const SERIES_MATCH_TOLERANCE_MS = DAY_MS;

function rowStartMs(row) {
  const s = Number(row.dataset.start);
  return Number.isFinite(s) && s > 0 ? s * 1000 : null;
}

// Eén schedule-call over alle getimede postseason-rijen (±1 dag marge voor NY/UTC-verschil).
// null = geen getimede postseason-rijen → niets op te halen.
export function seriesUrl(rows) {
  const starts = rows.map(rowStartMs).filter((s) => s !== null);
  if (!starts.length) return null;
  const from = new Date(Math.min(...starts) - DAY_MS);
  const to = new Date(Math.max(...starts) + DAY_MS);
  return (
    `https://statsapi.mlb.com/api/v1/schedule?sportId=1&gameType=F,D,L,W` +
    `&startDate=${mmddyyyy(from)}&endDate=${mmddyyyy(to)}`
  );
}

// Werkt de badge van elke rij bij met label + stand van de best passende API-game.
// Geeft het aantal bijgewerkte rijen terug.
export function applySeries(rows, games) {
  let updated = 0;
  for (const row of rows) {
    const badge = row.querySelector(".stp");
    const startMs = rowStartMs(row);
    if (!badge || startMs === null) continue;
    const key = `${row.dataset.awayTeam}|${row.dataset.homeTeam}`;
    let pick = null;
    let best = Infinity;
    for (const g of games) {
      const gKey = `${normalizeTeam(g.teams?.away?.team?.name ?? "")}|${normalizeTeam(g.teams?.home?.team?.name ?? "")}`;
      if (gKey !== key) continue;
      const dist = Math.abs(Date.parse(g.gameDate) - startMs);
      if (dist <= SERIES_MATCH_TOLERANCE_MS && dist < best) {
        best = dist;
        pick = g;
      }
    }
    if (!pick) continue;
    // Het label komt van de game zelf, behalve als we op een andere game van de serie terugvallen
    // (dan klopt het gamenummer niet): houd dan het build-time label zonder stand.
    const sameGame = best <= 60 * 60 * 1000;
    const buildLabel = badge.dataset.seriesBase ?? badge.textContent.replace(/\s*\(\d+-\d+\)\s*$/, "").trim();
    badge.dataset.seriesBase = buildLabel;
    const label = (sameGame && seriesLabel(pick)) || buildLabel;
    const record = seriesRecord(pick);
    badge.textContent = record ? `${label} ${record}` : label;
    updated++;
  }
  return updated;
}

export async function init(doc, { fetch: fetchFn } = {}) {
  const _fetch = fetchFn || globalThis.fetch;
  const rows = [...doc.querySelectorAll(".ps-row")];
  const url = seriesUrl(rows);
  if (!url) return;
  try {
    const resp = await _fetch(url);
    if (!resp.ok) return;
    const data = await resp.json();
    const games = (data?.dates ?? []).flatMap((d) => d.games ?? []);
    applySeries(rows, games);
  } catch {
    // Netwerkfout: build-time label blijft staan.
  }
}
