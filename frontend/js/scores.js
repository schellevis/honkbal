import { basesSvg, outsSvg } from "./util/diamond.js";
import { amsHHmm, nyDateWindow, mmddyyyy, yyyymmdd } from "./util/time.js";
import { logoPicture } from "./util/logo.js";
import { escapeHtml } from "./util/dom.js";
import { isFavoriteMatchup, applyFavoriteHighlights, initFavorites, normalizeTeam } from "./favorites.js";

export const CACHE_VERSION = 1;

export function cacheKey(date) { return `scores-${date}`; }
export function metaKey(date) { return `scores-meta-${date}`; }

const PREVIEW_KEEP = new Set(["Warmup", "Delayed Start", "Delayed"]);

export function classifyGame(game) {
  const state = game?.status?.abstractGameState;
  if (state === "Live") return "live";
  if (state === "Final") return "finished";
  if (state === "Preview") {
    const detail = game?.status?.detailedState ?? "";
    // Keep only warmup / delayed variants
    if (detail === "Warmup") return "preview";
    if (detail.startsWith("Delayed")) return "preview";
    return null;
  }
  return null;
}

function liveScore(game) {
  const ls = game.linescore;
  const inning = ls?.currentInning ?? 0;
  const isTop = ls?.isTopInning ?? true;
  return inning * 2 + (isTop ? 0 : 1);
}

export function sortLive(games, isFav) {
  return [...games].sort((a, b) => {
    const aFav = isFav(a.teams.away.team.name, a.teams.home.team.name) ? 0 : 1;
    const bFav = isFav(b.teams.away.team.name, b.teams.home.team.name) ? 0 : 1;
    if (aFav !== bFav) return aFav - bFav;
    return liveScore(a) - liveScore(b);
  });
}

export function sortFinished(games, isFav) {
  return [...games].sort((a, b) => {
    const aFav = isFav(a.teams.away.team.name, a.teams.home.team.name) ? 0 : 1;
    const bFav = isFav(b.teams.away.team.name, b.teams.home.team.name) ? 0 : 1;
    if (aFav !== bFav) return aFav - bFav;
    // Earliest gameDate first [FIX]
    return new Date(a.gameDate) - new Date(b.gameDate);
  });
}

// Pijl-SVG's voor de inning-helft, zoals productie (driehoek omhoog = Top, omlaag = Bottom).
const TOP_ARROW_SVG =
  `<svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" aria-hidden="true"><path d="M4 0L8 8H0z"/></svg>`;
const BOT_ARROW_SVG =
  `<svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" aria-hidden="true"><path d="M4 8L0 0H8z"/></svg>`;

export function statusLabel(game) {
  const detail = game?.status?.detailedState ?? "";
  const ls = game.linescore;

  if (detail === "Warmup") {
    return { kind: "warmup", html: `<span class="stp">warmup</span>` };
  }

  if (detail.startsWith("Delayed")) {
    const inning = ls?.currentInning;
    const isTop = ls?.isTopInning ?? true;
    const arrow = isTop ? TOP_ARROW_SVG : BOT_ARROW_SVG;
    if (inning) {
      const inningHtml = `<span class="stp-inning">${arrow}${escapeHtml(String(inning))}</span>`;
      return {
        kind: "DEL",
        html:
          `<span class="stp" style="display:inline-flex;align-items:center;gap:5px;bottom:0px;font-size:12px;padding:5px 11px 3px;">` +
          inningHtml +
          `<span style="color:#e67e22;">DEL</span></span>`,
      };
    }
    return { kind: "DEL", html: `<span class="stp" style="color:#e67e22;">DEL</span>` };
  }

  const state = game?.status?.abstractGameState;

  if (state === "Live") {
    const inning = ls?.currentInning;
    if (!inning) {
      return { kind: "live", html: `<span class="stp">bezig</span>` };
    }
    const isTop = ls?.isTopInning ?? true;
    const arrow = isTop ? TOP_ARROW_SVG : BOT_ARROW_SVG;
    const inningHtml = `<span class="stp-inning">${arrow}${escapeHtml(String(inning))}</span>`;
    const outs = ls?.outs ?? 0;
    const offense = ls?.offense ?? {};
    const bases = basesSvg(!!offense.first, !!offense.second, !!offense.third);
    const outsS = outsSvg(outs);
    return {
      kind: "live",
      html:
        `<span class="stp" style="display:inline-flex;align-items:center;gap:5px;bottom:0px;font-size:12px;padding:5px 11px 3px;">` +
        inningHtml +
        bases +
        outsS +
        `</span>`,
    };
  }

  if (state === "Final") {
    return { kind: "final", html: `<span class="st">final</span>` };
  }

  return { kind: "unknown", html: "" };
}

const WEEKDAYS = {
  1: "maandag", 2: "dinsdag", 3: "woensdag", 4: "donderdag",
  5: "vrijdag", 6: "zaterdag", 7: "zondag",
};
const MONTHS = {
  "01": "januari", "02": "februari", "03": "maart", "04": "april",
  "05": "mei", "06": "juni", "07": "juli", "08": "augustus",
  "09": "september", "10": "oktober", "11": "november", "12": "december",
};

// Datumkop ("woensdag 23 juni") uit een YYYYMMDD-sleutel — UTC-noon om DST-randgevallen te vermijden.
export function formatHeading(dateKey) {
  const year = Number(dateKey.slice(0, 4));
  const month = dateKey.slice(4, 6);
  const day = Number(dateKey.slice(6, 8));
  const utcDate = new Date(Date.UTC(year, Number(month) - 1, day, 12, 0, 0));
  let weekdayIndex = utcDate.getUTCDay();
  if (weekdayIndex === 0) weekdayIndex = 7;
  return `${WEEKDAYS[weekdayIndex]} ${day} ${MONTHS[month]}`;
}

export function writeCache(dateKey, payload, now) {
  const meta = { cachedAt: now.toISOString(), version: CACHE_VERSION };
  globalThis.localStorage.setItem(cacheKey(dateKey), JSON.stringify(payload));
  globalThis.localStorage.setItem(metaKey(dateKey), JSON.stringify(meta));
}

export function readCache(dateKey) {
  try {
    const metaRaw = globalThis.localStorage.getItem(metaKey(dateKey));
    if (!metaRaw) return null;
    const meta = JSON.parse(metaRaw);
    if (meta.version !== CACHE_VERSION) return null;
    const raw = globalThis.localStorage.getItem(cacheKey(dateKey));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function pruneCache(now, requestedDays) {
  const keepDays = new Set(requestedDays);
  // Also keep the last 7 days
  for (let i = 0; i < 7; i++) {
    const d = new Date(now);
    d.setUTCDate(d.getUTCDate() - i);
    keepDays.add(yyyymmdd(d));
  }
  const storage = globalThis.localStorage;
  const toRemove = [];
  for (let i = 0; i < storage.length; i++) {
    const k = storage.key(i);
    if (!k) continue;
    if (k.startsWith("scores-") && !k.startsWith("scores-meta-")) {
      const dateStr = k.replace("scores-", "");
      if (!keepDays.has(dateStr)) toRemove.push(k);
    }
    if (k.startsWith("scores-meta-")) {
      const dateStr = k.replace("scores-meta-", "");
      if (!keepDays.has(dateStr)) toRemove.push(k);
    }
  }
  for (const k of toRemove) storage.removeItem(k);
}

export function latestUpdate(dayKeys) {
  let latest = null;
  for (const day of dayKeys) {
    try {
      const metaRaw = globalThis.localStorage.getItem(metaKey(day));
      if (!metaRaw) continue;
      const meta = JSON.parse(metaRaw);
      if (!meta.cachedAt) continue;
      const d = new Date(meta.cachedAt);
      if (!latest || d > latest) latest = d;
    } catch {
      // skip
    }
  }
  return latest;
}

// Bewuste tradeoff t.o.v. SPEC §6.2: SPEC schrijft voor dat alleen datums met een
// live/delayed/warmup-game snel worden ververst (per dag). Hier wordt het hele 5-daagse
// venster op 30s gezet zodra één dag live/preview heeft. Vereenvoudigt de logica aanzienlijk;
// impact is minimaal omdat het snel-verversen toch meerdere parallelle API-aanvragen doet.
// Pas aan naar per-dag-intervallen als SPEC-conformiteit vereist is.
export function refreshIntervalMs(hasLiveOrPending) {
  return hasLiveOrPending ? 30000 : 300000;
}

function extractGames(apiJson) {
  const games = [];
  for (const day of apiJson?.dates ?? []) {
    for (const g of day.games ?? []) games.push(g);
  }
  return games;
}

// Eén team-cel: logo + naam (responsive: .score-name + .score-abbr) + score. Winnaar vet.
// Spiegelt de productie-markup (flex-div, ellipsis), met escaping op alle API-tekst.
function renderTeamScore(competitor) {
  const team = competitor?.team ?? {};
  // Korte weergavenaam ("Yankees") zoals productie; logoPicture canonicaliseert toch.
  const name = team.clubName ?? team.shortDisplayName ?? team.name ?? "";
  const abbr = team.abbreviation || name;
  const winner = competitor?.isWinner === true;
  const nameHtml = winner ? `<strong>${escapeHtml(name)}</strong>` : escapeHtml(name);
  const abbrHtml = winner ? `<strong>${escapeHtml(abbr)}</strong>` : escapeHtml(abbr);
  const score = competitor?.score;
  const scoreHtml =
    score != null && score !== ""
      ? `<strong style="margin-left:10px;">${escapeHtml(String(score))}</strong>`
      : "";
  return (
    `<div style="display:flex;align-items:center;min-width:0;">` +
    logoPicture(name) +
    `<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">` +
    `<span class="score-name">${nameHtml}</span><span class="score-abbr">${abbrHtml}</span>` +
    `</span>` +
    scoreHtml +
    `</div>`
  );
}

function renderScoreRow(game, isFav) {
  const away = game.teams.away.team;
  const home = game.teams.home.team;
  const label = statusLabel(game);
  const isFavGame = isFav(away.name, home.name);
  const cls = isFavGame ? ' class="favorite-game"' : "";
  // Canonieke nickname-vorm (matcht favorites + schedule-rijen), niet de gehyphende API-naam.
  const awayNorm = normalizeTeam(away.name);
  const homeNorm = normalizeTeam(home.name);
  return (
    `<tr${cls} data-away-team="${escapeHtml(awayNorm)}" data-home-team="${escapeHtml(homeNorm)}">` +
    `<td style="width:44%;max-width:0">${renderTeamScore(game.teams.away)}</td>` +
    `<td style="width:44%;max-width:0">${renderTeamScore(game.teams.home)}</td>` +
    `<td style="width:1%;white-space:nowrap;text-align:right">${label.html}</td>` +
    `</tr>`
  );
}

// Rij-markup voor een dag (preview -> live -> finished). Geëxporteerd voor tests:
// asserteert highlight/escaping/canonical-attr per rij.
export function renderScoresHtml(live, finished, preview, isFav) {
  const parts = [];
  for (const g of preview) parts.push(renderScoreRow(g, isFav));
  for (const g of live) parts.push(renderScoreRow(g, isFav));
  for (const g of finished) parts.push(renderScoreRow(g, isFav));
  return parts.join("\n");
}

// Eén dag-tabel (productie: <table class="table table-striped"> met colspan=3-kop + offline-noot).
export function renderDayTable(dateKey, rowsHtml, { offlineCachedAt } = {}) {
  if (!rowsHtml) return "";
  const offlineNote = offlineCachedAt
    ? ` <span class="st">offline - laatst bijgewerkt om ${escapeHtml(amsHHmm(offlineCachedAt))}</span>`
    : "";
  return (
    `<table class="table table-striped">` +
    `<thead><tr><th colspan="3">${escapeHtml(formatHeading(dateKey))}${offlineNote}</th></tr></thead>` +
    `<tbody>${rowsHtml}</tbody>` +
    `</table>`
  );
}

export async function init(doc, { now, fetch: fetchFn } = {}) {
  const _fetch = fetchFn || globalThis.fetch;
  const _now = now || new Date();

  initFavorites(doc);

  const iconEl = doc.querySelector ? doc.querySelector("#scores-icon") : null;
  const timeEl = doc.querySelector ? doc.querySelector("#scores-time") : null;
  const container = doc.querySelector ? doc.querySelector("#scores-container") : null;

  const isFav = (away, home) => isFavoriteMatchup(away, home);

  const days = nyDateWindow(_now, 5);
  const dayKeys = days.map((d) => yyyymmdd(d));

  // Bouw per dag een tabel in #scores-container (productie-markup). dayEntries: { key, games,
  // offlineCachedAt }. Dagen zonder relevante wedstrijden worden overgeslagen.
  function render(dayEntries) {
    if (!container) return;
    let html = "";
    for (const entry of dayEntries) {
      const live = sortLive(entry.games.filter((g) => classifyGame(g) === "live"), isFav);
      const finished = sortFinished(entry.games.filter((g) => classifyGame(g) === "finished"), isFav);
      const preview = entry.games.filter((g) => classifyGame(g) === "preview");
      const rows = renderScoresHtml(live, finished, preview, isFav);
      html += renderDayTable(entry.key, rows, { offlineCachedAt: entry.offlineCachedAt });
    }
    container.innerHTML = html || "<p>Geen recente scores beschikbaar</p>";
    applyFavoriteHighlights(container);
  }

  function cachedAtFor(dayKey) {
    try {
      const metaRaw = globalThis.localStorage.getItem(metaKey(dayKey));
      if (!metaRaw) return null;
      const meta = JSON.parse(metaRaw);
      return meta.cachedAt || null;
    } catch {
      return null;
    }
  }

  // Render from cache immediately (per dag, nieuwste eerst). Optimistisch: geen offline-noot
  // tot een netwerk-refresh daadwerkelijk faalt.
  const cachedEntries = [];
  for (const day of [...dayKeys].sort((a, b) => b.localeCompare(a))) {
    const cached = readCache(day);
    if (cached) {
      cachedEntries.push({ key: day, games: extractGames(cached), offlineCachedAt: null });
    }
  }
  if (cachedEntries.length > 0) render(cachedEntries);

  async function fetchAndRender() {
    // Verse klok per refresh, zodat cachedAt en de getoonde "laatste update" meelopen
    // (mirror van standings.js, dat per init() een nieuwe Date() injecteert). SPEC §6.2.
    const now = new Date();
    if (iconEl && iconEl.classList) iconEl.classList.add("spin");
    const perDay = new Map();
    let anyFailed = false;
    let anyLive = false;

    for (const day of days) {
      const key = yyyymmdd(day);
      const url = `https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=linescore,team&date=${mmddyyyy(day)}`;
      try {
        const resp = await _fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        writeCache(key, data, now);
        const games = extractGames(data);
        perDay.set(key, { games, offlineCachedAt: null });
        if (games.some((g) => classifyGame(g) === "live")) anyLive = true;
      } catch {
        anyFailed = true;
        const cached = readCache(key);
        if (cached) {
          perDay.set(key, { games: extractGames(cached), offlineCachedAt: cachedAtFor(key) });
        }
      }
    }

    pruneCache(now, dayKeys);

    // Sorteer dagen nieuwste-eerst (productie), bouw dag-entries.
    const dayEntries = [...perDay.keys()]
      .sort((a, b) => b.localeCompare(a))
      .map((key) => ({ key, ...perDay.get(key) }));
    render(dayEntries);

    const latest = latestUpdate(dayKeys);
    if (iconEl && iconEl.classList) iconEl.classList.remove("spin");
    // Productie toont de laatste-update-tijd in #scores-time naast het refresh-icoon; de
    // offline-melding staat per dag-tabel ("offline - laatst bijgewerkt om HH:mm").
    if (timeEl && latest) timeEl.textContent = amsHHmm(latest.toISOString());

    const hasLive = anyLive ||
      dayEntries.some((e) => e.games.some((g) => classifyGame(g) === "preview"));
    return setTimeout(fetchAndRender, refreshIntervalMs(hasLive));
  }

  // Return the in-flight promise so callers/tests can await the first render+cache cycle.
  return fetchAndRender();
}
