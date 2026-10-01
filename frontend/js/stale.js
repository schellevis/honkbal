// stale.js — laat het statische schema client-side verouderen (SPEC §6.10).
//
// Build-time filtert de render alleen wedstrijden met start > nu − LIVE_GRACE_HOURS (SPEC §3.2),
// maar de gerenderde pagina blijft daarna uren staan: tussen de nachtbuild (01:00) en de
// ochtendbuild (10:00) zit een gat van negen uur. Een bezoeker die donderdag om 05:55 kijkt naar
// een pagina die om 01:00 gebouwd is, ziet dus nog de wedstrijden van woensdagavond (21:45, 22:10)
// staan: op bouwmoment vielen die binnen het grace-window, nu al lang niet meer.
//
// Deze module past exact hetzelfde filter opnieuw toe in de browser, met dezelfde grens, zodat de
// pagina zich gedraagt alsof hij op dít moment gebouwd is. Getimede rijen gaan op `data-start`
// (moment-nauwkeurig), rijen zonder starttijd (TBD) op de `data-date` van hun dagblok
// (datum-granulair) — dezelfde tweedeling als het build-time filter.
//
// Daarnaast verbergt hij rijen binnen het grace-window waarvan de wedstrijd volgens de MLB Stats
// API al afgelopen is (`final-hidden`): een game die om 02:00 begon en om 05:00 klaar is, hoeft
// niet tot 06:00 in het schema te blijven staan. Alleen dan is er een API-call.

import { syncDayHeaders } from "./util/dom.js";
import { amsCalendarDate, mmddyyyy } from "./util/time.js";
import { normalizeTeam } from "./favorites.js";

// Moet gelijk blijven aan LIVE_GRACE_HOURS in honkbal/config/toggles.py: build-time bepaalt
// welke rijen in de HTML komen, hier hoe lang ze blijven staan. Lopen ze uiteen, dan verdwijnen
// rijen te vroeg (of blijven ze te lang hangen).
export const GRACE_MS = 4 * 3600 * 1000;

// Herweging van een openstaande pagina, zodat een wedstrijd die tijdens het kijken over de
// grace-grens gaat verdwijnt zonder reload.
export const RECHECK_MS = 60 * 1000;

// Status-check van rijen binnen het grace-window: hoe vaak (zolang er zulke rijen zijn) en hoe ver
// de API-gameDate van data-start mag afwijken om als dezelfde wedstrijd te gelden (zoals §6.8).
export const FINAL_RECHECK_MS = 5 * 60 * 1000;
export const FINAL_MATCH_TOLERANCE_MS = 60 * 60 * 1000;

// Dagblokken binnen de schematabel: normaal één <tbody> per dag, maar een minimale shell kan
// `.loadmore-container` op de <tbody> zelf hebben — dan is de container zelf het enige dagblok.
function dayGroups(container) {
  const bodies = container.querySelectorAll ? [...container.querySelectorAll("tbody")] : [];
  return bodies.length ? bodies : [container];
}

// `dayDate` = ISO-datum (YYYY-MM-DD) van het dagblok, `todayAms` = vandaag in Amsterdam.
export function isStaleRow(row, nowMs, todayAms, dayDate) {
  const raw = row.dataset ? row.dataset.start : undefined;
  if (raw !== undefined && raw !== "") {
    const start = Number(raw);
    // Onleesbare data-start → niet verbergen; het statische schema blijft leidend.
    if (!Number.isFinite(start)) return false;
    return nowMs >= start * 1000 + GRACE_MS;
  }
  // TBD-rij: zonder starttijd valt niet te bepalen of hij vandaag al voorbij is, dus pas
  // verbergen zodra de dag zelf voorbij is (SPEC §3.2). Geen dagdatum → niets te beslissen.
  if (!dayDate || !todayAms) return false;
  return dayDate < todayAms;
}

// Verbergt via een eigen CSS-klasse (niet row.hidden), zodat de veroudering nooit vecht met de
// dedup van de live-sectie (live.js gebruikt row.hidden, SPEC §6.8) of met het interessefilter.
// Retourneert het aantal verborgen rijen.
export function pruneStaleRows(doc, nowMs = Date.now()) {
  if (!doc.querySelectorAll) return 0;
  const todayAms = amsCalendarDate(new Date(nowMs));
  let hidden = 0;
  for (const container of doc.querySelectorAll(".loadmore-container")) {
    for (const group of dayGroups(container)) {
      const dayDate = group.dataset ? group.dataset.date : undefined;
      for (const row of group.querySelectorAll("[data-away-team]")) {
        const stale = isStaleRow(row, nowMs, todayAms, dayDate);
        if (row.classList) row.classList.toggle("stale-hidden", stale);
        if (stale) hidden++;
      }
    }
  }
  // Dagkoppen zonder zichtbare rijen mee verbergen (gedeeld met §6.8/§6.9).
  syncDayHeaders(doc);
  return hidden;
}

function allRows(doc) {
  if (!doc.querySelectorAll) return [];
  return [...doc.querySelectorAll(".loadmore-container")].flatMap((c) => [
    ...c.querySelectorAll("[data-away-team]"),
  ]);
}

// Getimede rijen die begonnen zijn maar nog binnen het grace-window vallen: mogelijk al afgelopen.
export function graceRows(doc, nowMs = Date.now()) {
  return allRows(doc).filter((row) => {
    const start = Number(row.dataset ? row.dataset.start : NaN);
    if (!Number.isFinite(start) || start <= 0) return false;
    const startMs = start * 1000;
    return nowMs >= startMs && nowMs < startMs + GRACE_MS;
  });
}

// Eén schedule-call over de NY-kalenderdagen van deze rijen (NY-datum ligt op of vóór de
// UTC-datum, dus van een dag vóór de vroegste tot de laatste start).
export function finalUrl(rows) {
  const starts = rows.map((r) => Number(r.dataset.start) * 1000);
  const from = new Date(Math.min(...starts) - 24 * 3600 * 1000);
  const to = new Date(Math.max(...starts));
  return `https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate=${mmddyyyy(from)}&endDate=${mmddyyyy(to)}`;
}

// Geeft rijen class `final-hidden` als de best passende API-game (zelfde teampaar, gameDate binnen
// 60 min; bij een doubleheader de dichtstbijzijnde) Final is. Retourneert het aantal.
export function applyFinished(rows, games) {
  let hidden = 0;
  for (const row of rows) {
    const key = `${row.dataset.awayTeam}|${row.dataset.homeTeam}`;
    const startMs = Number(row.dataset.start) * 1000;
    let pick = null;
    let best = Infinity;
    for (const g of games) {
      const gKey = `${normalizeTeam(g.teams?.away?.team?.name ?? "")}|${normalizeTeam(g.teams?.home?.team?.name ?? "")}`;
      if (gKey !== key) continue;
      const dist = Math.abs(Date.parse(g.gameDate) - startMs);
      if (dist <= FINAL_MATCH_TOLERANCE_MS && dist < best) {
        best = dist;
        pick = g;
      }
    }
    const done = pick?.status?.abstractGameState === "Final";
    if (row.classList) row.classList.toggle("final-hidden", done);
    if (done) hidden++;
  }
  return hidden;
}

// Haalt de status op voor rijen binnen het grace-window. Geen zulke rijen → geen call.
// Netwerkfout → niets wijzigen (het schema blijft leidend).
export async function hideFinished(doc, { fetch: fetchFn, nowMs = Date.now() } = {}) {
  const rows = graceRows(doc, nowMs);
  if (!rows.length) return 0;
  const _fetch = fetchFn || globalThis.fetch;
  try {
    const resp = await _fetch(finalUrl(rows));
    if (!resp.ok) return 0;
    const data = await resp.json();
    const games = (data?.dates ?? []).flatMap((d) => d.games ?? []);
    const n = applyFinished(rows, games);
    syncDayHeaders(doc);
    return n;
  } catch {
    return 0;
  }
}

export function init(doc, { recheckMs = RECHECK_MS, finalRecheckMs = FINAL_RECHECK_MS } = {}) {
  const container = doc.querySelector ? doc.querySelector(".loadmore-container") : null;
  if (!container) return null;

  pruneStaleRows(doc);
  hideFinished(doc);

  // "Meer laden" plakt rijen bij (SPEC §6.6); weeg die net zo.
  if (globalThis.MutationObserver) {
    new MutationObserver(() => pruneStaleRows(doc))
      .observe(container, { childList: true, subtree: true });
  }

  if (globalThis.setInterval && finalRecheckMs) {
    const t = globalThis.setInterval(() => hideFinished(doc), finalRecheckMs);
    if (t && typeof t.unref === "function") t.unref();
  }

  if (!globalThis.setInterval || !recheckMs) return null;
  const timer = globalThis.setInterval(() => pruneStaleRows(doc), recheckMs);
  // Node (tests) levert een Timeout-object; laat dat de eventloop niet openhouden.
  if (timer && typeof timer.unref === "function") timer.unref();
  return timer;
}
