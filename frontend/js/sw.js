// Service Worker — honkbal.net v2
// CACHE name: bump to "honkbal-v2", "honkbal-v3", etc. on EVERY change to PRECACHE or strategy.
// This forces old caches to be deleted on activate.
const CACHE = "honkbal-v2";

// Root-relative paths only. Scope is "/".
// Explicitly NOT precaching: CSS, manifest.json, logos (/img/*), *.tail.json
// (those are handled by runtime strategies or not needed offline).
const PRECACHE = [
  "/",
  "/index.html",
  "/avond.html",
  "/ochtend.html",
  "/nacht.html",
  "/alles.html",
  "/scores.html",
  "/standings.html",
  "/settings.html",
  "/debug.html",
  "/offline.html",
  "/favicon.ico",
  "/icon.png",
  // 30 team pages (slugs from honkbal/config/teams.py)
  "/braves.html",
  "/marlins.html",
  "/mets.html",
  "/phillies.html",
  "/nationals.html",
  "/cubs.html",
  "/cardinals.html",
  "/brewers.html",
  "/pirates.html",
  "/reds.html",
  "/dodgers.html",
  "/giants.html",
  "/padres.html",
  "/rockies.html",
  "/d-backs.html",
  "/orioles.html",
  "/yankees.html",
  "/red+sox.html",
  "/blue+jays.html",
  "/rays.html",
  "/white+sox.html",
  "/guardians.html",
  "/tigers.html",
  "/royals.html",
  "/twins.html",
  "/astros.html",
  "/angels.html",
  "/athletics.html",
  "/mariners.html",
  "/rangers.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin + a few CDN patterns; let cross-origin (non-asset) pass through.
  // Tail JSON: network-first → cache (offline more-loading)
  if (url.pathname.endsWith(".tail.json")) {
    event.respondWith(networkFirstCache(request));
    return;
  }

  // HTML / navigation: network-first → cache → offline.html
  if (
    request.mode === "navigate" ||
    request.headers.get("Accept")?.includes("text/html")
  ) {
    event.respondWith(networkFirstHtml(request));
    return;
  }

  // CSS / stylesheets: network-first (fast deploys)
  if (
    url.pathname.endsWith(".css") ||
    request.destination === "style"
  ) {
    event.respondWith(networkFirstCache(request));
    return;
  }

  // Images / fonts / CDN: cache-first
  if (
    request.destination === "image" ||
    request.destination === "font" ||
    url.pathname.startsWith("/img/")
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Default: network-first with cache fallback
  event.respondWith(networkFirstCache(request));
});

async function networkFirstHtml(request) {
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, resp.clone());
    }
    return resp;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match("/offline.html");
    return offline || new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } });
  }
}

async function networkFirstCache(request) {
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, resp.clone());
    }
    return resp;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, resp.clone());
    }
    return resp;
  } catch {
    return new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } });
  }
}
