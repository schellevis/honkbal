// live.js — "nu bezig"-sectie op de avond-tab (SPEC §6.8).
// Toont de wedstrijden die op dit moment bezig zijn (incl. warmup/delayed) met live scores,
// boven het statische schema. Geen localStorage-cache: de sectie is per definitie "nu".
import { classifyGame, liveScore, renderScoresHtml, refreshIntervalMs } from "./scores.js";
import { nyDateWindow, mmddyyyy } from "./util/time.js";
import { escapeHtml, syncDayHeaders } from "./util/dom.js";
import { isFavoriteMatchup, applyFavoriteHighlights, initFavorites, normalizeTeam } from "./favorites.js";

// Poll-venster per game (moet gelijk zijn aan LIVE_WINDOW_HOURS in config/toggles.py):
// binnen [start, start + 5u] kan een wedstrijd bezig zijn, daarbuiten pollen we niet.
export const LIVE_WINDOW_MS = 5 * 3600 * 1000;

// Ticketingfeed en Stats API kunnen enkele minuten verschillen. Een ruimere afwijking betekent
// dat het om een andere wedstrijd gaat (bijvoorbeeld dezelfde matchup later op de dag).
export const LIVE_MATCH_TOLERANCE_MS = 60 * 60 * 1000;

// data-live-windows-attribuut (JSON-array van epoch-seconden, SPEC §6.8) → array of null.
// null = attribuut afwezig/onleesbaar → altijd pollen (gedrag van vóór de venster-gating).
export function parseLiveWindows(raw) {
  if (raw == null) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed.filter((s) => Number.isFinite(s));
  } catch {
    return null;
  }
}

// 0 = nu binnen een venster (pollen); >0 = ms tot de eerstvolgende vensterstart (wachten);
// null = geen venster meer over (stoppen; een nieuwe build/reload brengt een verse lijst).
export function nextPollDelay(windows, nowMs) {
  let next = null;
  for (const startSec of windows) {
    const startMs = startSec * 1000;
    if (nowMs >= startMs && nowMs < startMs + LIVE_WINDOW_MS) return 0;
    if (startMs > nowMs && (next === null || startMs < next)) next = startMs;
  }
  return next === null ? null : next - nowMs;
}

// Server-side heet de avond-tab gewoon "avond"; zodra deze module draait wordt het label
// client-side "nu + avond" (SPEC §6.8) — zonder JS is er ook geen live-sectie.
// Alleen de tab in de schedule-subnav (.nav-pills): de topnavigatielink "schema" wijst óók
// naar /avond.html en moet "schema" blijven heten.
export function applyNuAvondLabel(doc) {
  if (!doc.querySelectorAll) return;
  for (const subnav of doc.querySelectorAll(".nav-pills")) {
    for (const link of subnav.querySelectorAll(".nav-link")) {
      const href = link.getAttribute ? link.getAttribute("href") ?? "" : "";
      if (href.includes("/avond.html")) link.textContent = "nu + avond";
    }
  }
}

// Sortering van de "nu bezig"-sectie: favorieten altijd bovenaan (SPEC §6.8), daarbinnen
// live vóór preview/warmup/delayed, daarbinnen vergevorderde innings eerst / vroegste start.
export function sortNowSection(games, isFav) {
  const rank = (g) => (classifyGame(g) === "live" ? 0 : 1);
  return [...games].sort((a, b) => {
    const aFav = isFav(a.teams.away.team.name, a.teams.home.team.name) ? 0 : 1;
    const bFav = isFav(b.teams.away.team.name, b.teams.home.team.name) ? 0 : 1;
    if (aFav !== bFav) return aFav - bFav;
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    if (rank(a) === 0) return liveScore(a) - liveScore(b);
    return new Date(a.gameDate) - new Date(b.gameDate);
  });
}

// Eén tabel met kop "nu bezig"; lege rijenset → lege string (sectie verborgen, SPEC §6.8).
export function renderLiveHtml(games, isFav) {
  const rows = renderScoresHtml(games, [], [], isFav);
  if (!rows) return "";
  return (
    `<table class="table table-striped">` +
    `<thead><tr><th colspan="3">${escapeHtml("nu bezig")}</th></tr></thead>` +
    `<tbody>${rows}</tbody>` +
    `</table>`
  );
}

// Dedup met het statische schema: verberg per live wedstrijd één overeenkomstige statische rij
// (data-away-team/data-home-team-match én start binnen 60 minuten). Bij elke refresh opnieuw
// bepaald, dus een afgelopen wedstrijd laat z'n statische rij weer terugkomen. Bij een
// doubleheader wint de geldige rij waarvan data-start (epoch-seconden, build-time) het dichtst
// bij de gameDate van de API ligt.
export function syncHiddenRows(doc, games) {
  const wanted = games.map((g) => ({
    key: `${normalizeTeam(g.teams.away.team.name)}|${normalizeTeam(g.teams.home.team.name)}`,
    startMs: g.gameDate ? Date.parse(g.gameDate) : NaN,
  }));
  for (const container of doc.querySelectorAll(".loadmore-container")) {
    const rows = [...container.querySelectorAll("[data-away-team]")];
    const hidden = new Set();
    for (const w of wanted) {
      if (!Number.isFinite(w.startMs)) continue;
      let pick = null;
      let best = Infinity;
      for (const r of rows) {
        if (hidden.has(r) || `${r.dataset.awayTeam}|${r.dataset.homeTeam}` !== w.key) continue;
        const rowStart = Number(r.dataset.start);
        if (!Number.isFinite(rowStart) || rowStart <= 0) continue;
        const dist = Math.abs(rowStart * 1000 - w.startMs);
        if (dist <= LIVE_MATCH_TOLERANCE_MS && dist < best) {
          best = dist;
          pick = r;
        }
      }
      if (pick) hidden.add(pick);
    }
    for (const row of rows) row.hidden = hidden.has(row);
  }
  // Zijn alle games van een dag naar de "nu bezig"-sectie verplaatst, verberg dan de nu lege
  // dagkop (SPEC §6.8) — anders blijft er een verweesd datumkopje staan.
  syncDayHeaders(doc);
}

export async function init(doc, { fetch: fetchFn } = {}) {
  const _fetch = fetchFn || globalThis.fetch;
  const container = doc.querySelector ? doc.querySelector("#live-container") : null;
  if (!container) return;

  initFavorites(doc);
  const isFav = (away, home) => isFavoriteMatchup(away, home);

  const windows = parseLiveWindows(
    container.getAttribute ? container.getAttribute("data-live-windows") : null
  );
  // "Status wint van het venster": zagen we live games, dan blijven we pollen tot de API
  // zegt dat ze klaar zijn — ook als het 5-uursvenster inmiddels dicht is (uitlopers).
  let sawLive = false;

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

    // Netwerkfout → sectie ongewijzigd laten; het statische schema blijft leidend (SPEC §6.8).
    if (allOk) {
      const current = sortNowSection(
        games.filter((g) => ["live", "preview"].includes(classifyGame(g))),
        isFav
      );
      sawLive = current.length > 0;
      container.innerHTML = renderLiveHtml(current, isFav);
      applyFavoriteHighlights(container);
      syncHiddenRows(doc, current);
    }
  }

  async function tick(forceInitial = false) {
    const inWindow =
      forceInitial || windows === null || sawLive || nextPollDelay(windows, Date.now()) === 0;
    if (inWindow) {
      await fetchAndRender();
      return setTimeout(tick, refreshIntervalMs(sawLive));
    }
    const delay = nextPollDelay(windows, Date.now());
    if (delay === null) return; // geen vensters meer over — niets te verwachten
    return setTimeout(tick, delay);
  }

  // Altijd één keer pollen bij het laden: een wedstrijd die nú bezig is moet direct verschijnen,
  // óók als het build-time venster hem mist (game die al >5u loopt door delay/extra innings, of
  // een verouderde data-live-windows). Daarna gate't de gewone tick de vervolg-polls en houdt
  // sawLive een lopende wedstrijd vanzelf actief (SPEC §6.8).
  // Return the in-flight promise so callers/tests can await the first render cycle.
  return tick(true);
}
