import { applyFavoriteHighlights } from "./favorites.js";

export function tailUrl(pageName) {
  return `/${pageName}.tail.json`;
}

export function selectBlocks(tailJson, expectedVersion) {
  if (tailJson.version !== expectedVersion) {
    return { ok: false, blocks: [] };
  }
  return { ok: true, blocks: tailJson.blocks || [] };
}

export function createController({ page, tailVersion }) {
  let blocks = null;
  let index = 0;
  let loaded = false;

  // Eén fetch+parse-poging. bust=true omzeilt zowel de HTTP- als de SW-cache
  // (eigen URL via ?v=<version> + cache:"reload"), zodat een stale gecachte tail
  // niet opnieuw geserveerd wordt.
  async function fetchTail(fetchFn, bust) {
    const url = bust ? `${tailUrl(page)}?v=${encodeURIComponent(tailVersion)}` : tailUrl(page);
    const resp = await fetchFn(url, bust ? { cache: "reload" } : undefined);
    if (!resp.ok) return { status: "fail" };
    const data = await resp.json();
    const result = selectBlocks(data, tailVersion);
    if (!result.ok) return { status: "mismatch" };
    return { status: "ok", blocks: result.blocks };
  }

  async function loadTail(fetchFn) {
    if (loaded) return true;
    try {
      let r = await fetchTail(fetchFn, false);
      // SPEC §6.6: bij version-mismatch (stale cache) negeren en opnieuw van netwerk halen.
      if (r.status === "mismatch") {
        r = await fetchTail(fetchFn, true);
      }
      if (r.status !== "ok") return false; // mismatch-na-refetch of fetch-fout -> offline-melding
      blocks = r.blocks;
      loaded = true;
      return true;
    } catch {
      return false;
    }
  }

  function appendNext(container, btn) {
    if (!blocks || index >= blocks.length) return;
    const html = blocks[index++];
    container.insertAdjacentHTML("beforeend", html);
    // Apply favorites to newly added rows (the stub tracks children via insertAdjacentHTML)
    applyFavoriteHighlights(container);
    if (index >= blocks.length) {
      if (btn) {
        btn.style.display = "none";
        btn.classList.add("hidden");
      }
    }
  }

  function onError(btn, msgEl) {
    if (msgEl) msgEl.textContent = "meer laden lukt nu niet — offline";
  }

  return { loadTail, appendNext, onError };
}

export function init(doc, { fetch: fetchFn } = {}) {
  const _fetch = fetchFn || globalThis.fetch;
  const btn = doc.querySelector ? doc.querySelector(".loadmore") : null;
  if (!btn) return;

  const page = btn.dataset.page;
  const tailVersion = btn.dataset.tailVersion;
  if (!page || !tailVersion) return;

  const container = doc.querySelector ? doc.querySelector(".loadmore-container") || doc.querySelector("tbody") : null;
  const msgEl = doc.querySelector ? doc.querySelector(".loadmore-msg") : null;

  const controller = createController({ page, tailVersion });
  let tailLoaded = false;

  btn.addEventListener("click", async () => {
    if (!tailLoaded) {
      const ok = await controller.loadTail(_fetch);
      if (!ok) {
        controller.onError(btn, msgEl);
        return;
      }
      tailLoaded = true;
    }
    if (container) controller.appendNext(container, btn);
  });
}
