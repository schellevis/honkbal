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

import { syncDayHeaders } from "./util/dom.js";
import { amsCalendarDate } from "./util/time.js";

// Moet gelijk blijven aan LIVE_GRACE_HOURS in honkbal/config/toggles.py: build-time bepaalt
// welke rijen in de HTML komen, hier hoe lang ze blijven staan. Lopen ze uiteen, dan verdwijnen
// rijen te vroeg (of blijven ze te lang hangen).
export const GRACE_MS = 4 * 3600 * 1000;

// Herweging van een openstaande pagina, zodat een wedstrijd die tijdens het kijken over de
// grace-grens gaat verdwijnt zonder reload.
export const RECHECK_MS = 60 * 1000;

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

export function init(doc, { recheckMs = RECHECK_MS } = {}) {
  const container = doc.querySelector ? doc.querySelector(".loadmore-container") : null;
  if (!container) return null;

  pruneStaleRows(doc);

  // "Meer laden" plakt rijen bij (SPEC §6.6); weeg die net zo.
  if (globalThis.MutationObserver) {
    new MutationObserver(() => pruneStaleRows(doc))
      .observe(container, { childList: true, subtree: true });
  }

  if (!globalThis.setInterval || !recheckMs) return null;
  const timer = globalThis.setInterval(() => pruneStaleRows(doc), recheckMs);
  // Node (tests) levert een Timeout-object; laat dat de eventloop niet openhouden.
  if (timer && typeof timer.unref === "function") timer.unref();
  return timer;
}
