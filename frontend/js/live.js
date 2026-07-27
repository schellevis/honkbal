// live.js — "nu bezig"-sectie op de avond-tab (SPEC §6.8).
// Toont de wedstrijden die op dit moment bezig zijn (incl. warmup/delayed) met live scores,
// boven het statische schema. Geen localStorage-cache: de sectie is per definitie "nu".
import { classifyGame, sortLive, renderScoresHtml, refreshIntervalMs } from "./scores.js";
import { nyDateWindow, mmddyyyy } from "./util/time.js";
import { escapeHtml } from "./util/dom.js";
import { isFavoriteMatchup, applyFavoriteHighlights, initFavorites, normalizeTeam } from "./favorites.js";

// Zolang de live-sectie een bètafeature is (SPEC §6.9) heet de avond-tab server-side gewoon
// "avond"; met de feature aan wordt het label client-side "nu + avond" (SPEC §6.8).
export function applyNuAvondLabel(doc) {
  if (!doc.querySelectorAll) return;
  for (const link of doc.querySelectorAll(".nav-link")) {
    const href = link.getAttribute ? link.getAttribute("href") ?? "" : "";
    if (href.includes("/avond.html")) link.textContent = "nu + avond";
  }
}

// Eén tabel met kop "nu bezig"; lege rijenset → lege string (sectie verborgen, SPEC §6.8).
export function renderLiveHtml(live, preview, isFav) {
  const rows = renderScoresHtml(live, [], preview, isFav);
  if (!rows) return "";
  return (
    `<table class="table table-striped">` +
    `<thead><tr><th colspan="3">${escapeHtml("nu bezig")}</th></tr></thead>` +
    `<tbody>${rows}</tbody>` +
    `</table>`
  );
}

// Dedup met het statische schema: verberg per live wedstrijd één overeenkomstige statische rij
// (data-away-team/data-home-team-match). Bij elke refresh opnieuw bepaald, dus een afgelopen
// wedstrijd laat z'n statische rij weer terugkomen. Bij een doubleheader (twee identieke rijen)
// wordt er per live game precies één verborgen.
export function syncHiddenRows(doc, games) {
  const counts = new Map();
  for (const g of games) {
    const key =
      `${normalizeTeam(g.teams.away.team.name)}|${normalizeTeam(g.teams.home.team.name)}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  for (const container of doc.querySelectorAll(".loadmore-container")) {
    for (const row of container.querySelectorAll("[data-away-team]")) {
      const key = `${row.dataset.awayTeam}|${row.dataset.homeTeam}`;
      const remaining = counts.get(key) ?? 0;
      if (remaining > 0) {
        row.hidden = true;
        counts.set(key, remaining - 1);
      } else {
        row.hidden = false;
      }
    }
  }
}

export async function init(doc, { fetch: fetchFn } = {}) {
  const _fetch = fetchFn || globalThis.fetch;
  const container = doc.querySelector ? doc.querySelector("#live-container") : null;
  if (!container) return;

  initFavorites(doc);
  const isFav = (away, home) => isFavoriteMatchup(away, home);

  async function fetchAndRender() {
    // 2-daags venster (NY-vandaag + NY-gisteren): een wedstrijd die in de Nederlandse ochtend
    // nog loopt hoort bij de NY-kalenderdag van gisteren (SPEC §6.8).
    const days = nyDateWindow(new Date(), 2);
    const games = [];
    let allOk = true;
    for (const day of days) {
      const url = `https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=linescore,team&date=${mmddyyyy(day)}`;
      try {
        const resp = await _fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        for (const d of data?.dates ?? []) {
          for (const g of d.games ?? []) games.push(g);
        }
      } catch {
        allOk = false;
      }
    }

    let hasLive = false;
    // Netwerkfout → sectie ongewijzigd laten; het statische schema blijft leidend (SPEC §6.8).
    if (allOk) {
      const live = sortLive(games.filter((g) => classifyGame(g) === "live"), isFav);
      const preview = games.filter((g) => classifyGame(g) === "preview");
      hasLive = live.length + preview.length > 0;
      container.innerHTML = renderLiveHtml(live, preview, isFav);
      applyFavoriteHighlights(container);
      syncHiddenRows(doc, [...live, ...preview]);
    }
    return setTimeout(fetchAndRender, refreshIntervalMs(hasLive));
  }

  // Return the in-flight promise so callers/tests can await the first render cycle.
  return fetchAndRender();
}
