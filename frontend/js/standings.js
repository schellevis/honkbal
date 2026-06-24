import { logoPicture } from "./util/logo.js";
import { escapeHtml } from "./util/dom.js";
import { isFavoriteMatchup, applyFavoriteHighlights, initFavorites, normalizeTeam } from "./favorites.js";

export const CACHE_VERSION = 1;
export const DIVISIONS = { al: [201, 202, 200], nl: [204, 205, 203] };
export const LEAGUES = { 103: "AL", 104: "NL" };

// Known division IDs
const KNOWN_DIVISIONS = new Set([200, 201, 202, 203, 204, 205]);

export function cacheKey(season) { return `standings-${season}`; }
export function metaKey(season) { return `standings-meta-${season}`; }
export const tabKey = "standings-tab";

export function resolveSeason(doc) {
  const val = doc?.body?.dataset?.season;
  if (val && /^\d{4}$/.test(val)) return parseInt(val, 10);
  console.warn("standings: data-season attribute missing or invalid on body; falling back to current year");
  return new Date().getFullYear();
}

export function flatten(apiJson) {
  const rows = [];
  for (const record of apiJson?.records ?? []) {
    const divisionId = record?.division?.id;
    const leagueId = record?.league?.id;
    for (const tr of record?.teamRecords ?? []) {
      // L10 zit genest onder tr.records.splitRecords (niet tr.splitRecords); streak onder
      // tr.streak.streakCode (niet tr.streakCode) — paden zoals de echte MLB Stats API ze levert.
      const split = tr.records?.splitRecords ?? tr.splitRecords ?? [];
      const lastTen = split.find((s) => s.type === "lastTen");
      const l10 = lastTen ? `${lastTen.wins}-${lastTen.losses}` : undefined;
      const wcr = tr.wildCardRank != null ? parseInt(tr.wildCardRank, 10) : undefined;
      rows.push({
        // Korte weergavenaam ("Yankees") zoals productie; canonicalTeam matcht 'm alsnog.
        teamName: tr.team?.teamName ?? tr.team?.clubName ?? tr.team?.name,
        teamAbbr: tr.team?.abbreviation,
        divisionId: divisionId,
        leagueId: leagueId,
        wins: tr.wins,
        losses: tr.losses,
        pct: tr.winningPercentage,
        gamesBack: tr.gamesBack === "-" ? "—" : tr.gamesBack,
        wcGamesBack: tr.wildCardGamesBack,
        divisionRank: tr.divisionRank != null ? parseInt(tr.divisionRank, 10) : undefined,
        leagueRank: tr.leagueRank != null ? parseInt(tr.leagueRank, 10) : undefined,
        wildCardRank: wcr,
        l10: l10,
        streak: tr.streak?.streakCode ?? tr.streakCode,
        isWildcardHolder: tr.wildCardGamesBack != null && String(tr.wildCardGamesBack).startsWith("+"),
      });
    }
  }
  return rows;
}

export function validateRow(row, view) {
  // pct: presence-check i.p.v. truthiness, anders zou een geldige ".000"/0 weggegooid worden.
  if (!row.teamName || row.wins == null || row.losses == null || row.pct == null) return false;
  if (view === "division") return row.divisionId != null && row.divisionRank != null;
  if (view === "al" || view === "nl") return row.leagueRank != null;
  if (view === "wildcard") {
    return row.wildCardRank != null && row.wildCardRank >= 1 && row.wildCardRank <= 6 && row.wcGamesBack != null;
  }
  // mlb: no rank required
  return true;
}

export function viewDivision(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!KNOWN_DIVISIONS.has(row.divisionId)) continue;
    if (!validateRow(row, "division")) continue;
    if (!groups.has(row.divisionId)) groups.set(row.divisionId, []);
    groups.get(row.divisionId).push(row);
  }
  // Sort each group
  for (const [, arr] of groups) {
    arr.sort((a, b) => a.divisionRank - b.divisionRank || parsePct(b.pct) - parsePct(a.pct));
  }
  return [...groups.entries()].map(([id, rows]) => ({ divisionId: id, rows }));
}

export function viewLeague(rows, league) {
  const leagueId = league === "AL" ? 103 : 104;
  const filtered = rows.filter((r) => r.leagueId === leagueId && validateRow(r, league === "AL" ? "al" : "nl"));
  return filtered.sort((a, b) => {
    if (a.leagueRank !== b.leagueRank) return a.leagueRank - b.leagueRank;
    const pctDiff = parsePct(b.pct) - parsePct(a.pct);
    if (pctDiff !== 0) return pctDiff;
    return b.wins - a.wins;
  });
}

export function viewMlb(rows) {
  const filtered = rows.filter((r) => validateRow(r, "mlb"));
  return filtered.sort((a, b) => {
    const pctDiff = parsePct(b.pct) - parsePct(a.pct);
    if (pctDiff !== 0) return pctDiff;
    return b.wins - a.wins;
  });
}

export function viewWildcard(rows, league) {
  const leagueId = league === "AL" ? 103 : 104;
  const filtered = rows.filter((r) => r.leagueId === leagueId && validateRow(r, "wildcard"));
  return filtered.sort((a, b) => a.wildCardRank - b.wildCardRank);
}

function parsePct(pct) {
  return pct ? parseFloat(pct) : 0;
}

export function writeCache(season, payload, now) {
  const meta = { cachedAt: now.toISOString(), version: CACHE_VERSION };
  globalThis.localStorage.setItem(cacheKey(season), JSON.stringify(payload));
  globalThis.localStorage.setItem(metaKey(season), JSON.stringify(meta));
}

export function readCache(season) {
  try {
    const metaRaw = globalThis.localStorage.getItem(metaKey(season));
    if (!metaRaw) return null;
    const meta = JSON.parse(metaRaw);
    if (meta.version !== CACHE_VERSION) return null;
    const raw = globalThis.localStorage.getItem(cacheKey(season));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// Eén team-cel zoals productie: logo + naam (.score-name/.score-abbr) in een flex-div met ellipsis.
function renderTeamCell(name, abbr) {
  return (
    `<div style="display:flex;align-items:center;min-width:0;">` +
    logoPicture(name) +
    `<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">` +
    `<span class="score-name">${escapeHtml(name)}</span>` +
    `<span class="score-abbr">${escapeHtml(abbr)}</span>` +
    `</span></div>`
  );
}

// Één tabel met sectie-kop + kolomkop (productie-markup, in .standings-table-wrap).
function renderTable(title, rows, { gbLabel = "GB", isWildCard = false } = {}) {
  if (!rows.length) return "";
  const body = rows.map((r) => renderStandingsRow(r, { isWildCard })).join("");
  return (
    `<div class="standings-table-wrap">` +
    `<table class="table table-striped">` +
    `<thead><tr><th colspan="7">${escapeHtml(title)}</th></tr></thead>` +
    `<thead><tr><th>Team</th><th style="text-align:right">W</th><th style="text-align:right">L</th>` +
    `<th style="text-align:right">PCT</th><th style="text-align:right">${escapeHtml(gbLabel)}</th>` +
    `<th style="text-align:right">L10</th><th style="text-align:right">Streak</th></tr></thead>` +
    `<tbody>${body}</tbody>` +
    `</table>` +
    `</div>`
  );
}

function formatGamesBack(value) {
  return value === "-" || value === "—" ? "—" : escapeHtml(value ?? "");
}

const CELL_STYLE = "width:1%;white-space:nowrap;text-align:right;padding-left:16px";

function renderStandingsRow(row, { isWildCard = false } = {}) {
  const isFav = isFavoriteMatchup(row.teamName, row.teamName);
  const classes = [];
  if (isWildCard && row.isWildcardHolder) classes.push("standings-wildcard-holder");
  if (isFav) classes.push("favorite-game");
  const clsAttr = classes.length ? ` class="${classes.join(" ")}"` : "";
  const name = row.teamName;
  const abbr = row.teamAbbr || name;
  const gb = isWildCard ? row.wcGamesBack : row.gamesBack;
  // Alle API-tekst geëscapet (SPEC §2/§6.3). data-team-attributen worden naar dezelfde
  // genormaliseerde vorm gebracht als favorites.normalizeTeam, zodat de highlight matcht.
  const teamAttr = escapeHtml(normalizeTeam(name));
  return (
    `<tr${clsAttr} data-away-team="${teamAttr}" data-home-team="${teamAttr}">` +
    `<td style="width:auto">${renderTeamCell(name, abbr)}</td>` +
    `<td style="${CELL_STYLE}">${escapeHtml(row.wins ?? "")}</td>` +
    `<td style="${CELL_STYLE}">${escapeHtml(row.losses ?? "")}</td>` +
    `<td style="${CELL_STYLE}">${escapeHtml(row.pct ?? "")}</td>` +
    `<td style="${CELL_STYLE}">${formatGamesBack(gb)}</td>` +
    `<td style="${CELL_STYLE}">${escapeHtml(row.l10 ?? "")}</td>` +
    `<td style="${CELL_STYLE}">${escapeHtml(row.streak ?? "")}</td>` +
    `</tr>`
  );
}

// Geëxporteerd voor tests: wildcard-rij (holder-klasse, escaping, canonieke data-attr).
export function renderWildcardRow(row) {
  return renderStandingsRow(row, { isWildCard: true });
}

// Track whether the storage listener has been registered for the current module instance.
// This prevents a new listener from being added on every recursive init() cycle.
let _storageListenerRegistered = false;

const LEAGUE_NAMES = {
  division: { 200: "American League West", 201: "American League East", 202: "American League Central",
    203: "National League West", 204: "National League East", 205: "National League Central" },
};

const amsterdamTimeFormatter = new Intl.DateTimeFormat("nl-NL", {
  timeZone: "Europe/Amsterdam",
  hour: "2-digit",
  minute: "2-digit",
});

function formatCacheTime(cachedAt) {
  if (!cachedAt) return "";
  return amsterdamTimeFormatter.format(new Date(cachedAt));
}

export async function init(doc, { now, fetch: fetchFn } = {}) {
  const _fetch = fetchFn || globalThis.fetch;
  const _now = now || new Date();

  initFavorites(doc);

  const season = resolveSeason(doc);
  const container = doc.querySelector ? doc.querySelector("#standings-container") : null;
  const tabs = doc.querySelector ? doc.querySelector("#standings-tabs") : null;
  const metaEl = doc.querySelector ? doc.querySelector("#standings-meta") : null;
  if (!container) return;

  let activeTab = getSavedTab(tabs);
  let currentRows = [];

  function setTabActive(tab) {
    if (!tabs || !tabs.querySelectorAll) return;
    for (const link of tabs.querySelectorAll("[data-tab]")) {
      if (link.classList) link.classList.toggle("active", link.dataset.tab === tab);
    }
  }

  function renderMeta(entry) {
    if (!metaEl) return;
    if (entry && entry.source === "cache" && entry.cachedAt) {
      metaEl.textContent = `Offline of fallback-cache, laatst bijgewerkt om ${formatCacheTime(entry.cachedAt)}`;
    } else if (entry && entry.cachedAt) {
      metaEl.textContent = `Laatst bijgewerkt om ${formatCacheTime(entry.cachedAt)}`;
    } else {
      metaEl.textContent = "";
    }
  }

  function renderActive() {
    container.innerHTML = renderStandingsHtml(currentRows, activeTab) || "<p>Geen standings beschikbaar</p>";
    applyFavoriteHighlights(container);
  }

  function renderFromData(data, entry) {
    currentRows = flatten(data);
    renderMeta(entry);
    renderActive();
  }

  // Render from cache
  const cached = readCache(season);
  if (cached) {
    const cachedAt = readCachedAt(season);
    renderFromData(cached, { source: "cache", cachedAt });
  }

  // Fetch fresh
  const url = `https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&standingsTypes=regularSeason&hydrate=team&season=${season}`;
  try {
    const resp = await _fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    writeCache(season, data, _now);
    renderFromData(data, { source: "network", cachedAt: _now.toISOString() });
  } catch {
    // fallback to cache already rendered
  }

  // Wire tab switching (productie: <a data-tab> in #standings-tabs)
  setTabActive(activeTab);
  if (tabs && tabs.addEventListener && !tabs._wired) {
    tabs._wired = true;
    tabs.addEventListener("click", (event) => {
      const link = event.target && event.target.closest
        ? event.target.closest("a[data-tab]")
        : null;
      if (!link) return;
      if (event.preventDefault) event.preventDefault();
      activeTab = link.dataset.tab;
      saveTab(activeTab);
      setTabActive(activeTab);
      renderActive();
    });
  }

  // Cross-tab storage listener — register exactly once per module instance
  if (!_storageListenerRegistered) {
    _storageListenerRegistered = true;
    globalThis.window.addEventListener("storage", (e) => {
      if (e.key === "honkbal-favorite-teams") applyFavoriteHighlights(container);
    });
  }

  return setTimeout(() => init(doc, { now: new Date(), fetch: fetchFn }), 300000);
}

function getSavedTab(tabs) {
  try {
    const saved = globalThis.localStorage.getItem(tabKey);
    if (!saved) return "division";
    if (tabs && tabs.querySelector && !tabs.querySelector(`[data-tab="${saved}"]`)) {
      return "division";
    }
    return saved;
  } catch {
    return "division";
  }
}

function saveTab(tab) {
  try {
    globalThis.localStorage.setItem(tabKey, tab);
  } catch {
    // ignore
  }
}

function readCachedAt(season) {
  try {
    const metaRaw = globalThis.localStorage.getItem(metaKey(season));
    if (!metaRaw) return null;
    return JSON.parse(metaRaw).cachedAt || null;
  } catch {
    return null;
  }
}

// Exported for testing: reset listener registration state.
export function _resetStorageListenerForTest() {
  _storageListenerRegistered = false;
}

function renderStandingsHtml(rows, activeTab) {
  if (activeTab === "division") return renderDivisionView(rows);
  if (activeTab === "al") return renderTable("American League", viewLeague(rows, "AL"));
  if (activeTab === "nl") return renderTable("National League", viewLeague(rows, "NL"));
  if (activeTab === "mlb") return renderTable("Major League Baseball", viewMlb(rows));
  if (activeTab === "wildcard") return renderWildcardView(rows);
  return "";
}

// Vaste productie-volgorde: AL East, AL Central, AL West, NL East, NL Central, NL West.
const DIVISION_ORDER = [201, 202, 200, 204, 205, 203];

function renderDivisionView(rows) {
  const byId = new Map(viewDivision(rows).map((g) => [g.divisionId, g]));
  return DIVISION_ORDER.map((id) => {
    const g = byId.get(id);
    if (!g) return "";
    return renderTable(LEAGUE_NAMES.division[id] || "", g.rows);
  }).join("");
}

function renderWildcardView(rows) {
  const al = renderTable("American League wild card", viewWildcard(rows, "AL"), {
    gbLabel: "WC GB",
    isWildCard: true,
  });
  const nl = renderTable("National League wild card", viewWildcard(rows, "NL"), {
    gbLabel: "WC GB",
    isWildCard: true,
  });
  return al + nl;
}
