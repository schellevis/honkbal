import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { installDom, restoreDom } from "./dom-stub.js";
import { installFetch, restoreFetch, lastCalls } from "./fetch-stub.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
function fixture(name) {
  return JSON.parse(readFileSync(join(__dirname, "fixtures", name), "utf8"));
}

let lm, fav;
beforeEach(async () => {
  installDom();
  fav = await import("../js/favorites.js?" + Math.random());
  lm = await import("../js/loadmore.js?" + Math.random());
});
afterEach(() => { restoreFetch(); restoreDom(); });

// --- tailUrl ---
test("tailUrl returns root-relative path", () => {
  assert.equal(lm.tailUrl("avond"), "/avond.tail.json");
});

// --- selectBlocks ---
test("selectBlocks with matching version returns blocks", () => {
  const tail = fixture("avond.tail.json");
  const result = lm.selectBlocks(tail, "testv1");
  assert.equal(result.ok, true);
  assert.equal(result.blocks.length, 2);
});

test("selectBlocks with mismatched version returns ok:false", () => {
  const tail = fixture("avond.tail.json");
  const result = lm.selectBlocks(tail, "wrongversion");
  assert.equal(result.ok, false);
  assert.equal(result.blocks.length, 0);
});

// --- block ordering ---
test("appendNext inserts blocks in order", async () => {
  installFetch({ "avond.tail.json": { ok: true, status: 200, payload: fixture("avond.tail.json") } });

  const container = globalThis.document.createElement("tbody");
  const btn = globalThis.document.createElement("button");
  btn.dataset.page = "avond";
  btn.dataset.tailVersion = "testv1";

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  await controller.loadTail(globalThis.fetch);
  controller.appendNext(container, btn);
  // First block appended
  assert.ok(container._insertedBlocks[0].includes("mets"));
  controller.appendNext(container, btn);
  // Second block appended
  assert.ok(container._insertedBlocks[1].includes("reds"));
});

// --- button hidden after last block ---
test("appendNext hides button after last block", async () => {
  installFetch({ "avond.tail.json": { ok: true, status: 200, payload: fixture("avond.tail.json") } });

  const container = globalThis.document.createElement("tbody");
  const btn = globalThis.document.createElement("button");
  btn.dataset.page = "avond";
  btn.dataset.tailVersion = "testv1";

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  await controller.loadTail(globalThis.fetch);
  controller.appendNext(container, btn); // block 0
  controller.appendNext(container, btn); // block 1 → last
  // Button should be hidden
  assert.ok(btn.style.display === "none" || btn.classList.contains("hidden"));
});

// --- favorites applied to new rows ---
test("appendNext applies favorite-game class to matching rows", async () => {
  installFetch({ "avond.tail.json": { ok: true, status: 200, payload: fixture("avond.tail.json") } });
  fav.setFavorites(["mets"]);

  const container = globalThis.document.createElement("tbody");
  const btn = globalThis.document.createElement("button");
  btn.dataset.page = "avond";
  btn.dataset.tailVersion = "testv1";

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  await controller.loadTail(globalThis.fetch);
  controller.appendNext(container, btn);
  // Find the mets row in children
  const metsRow = container._children.find((c) => c.dataset && c.dataset.awayTeam === "mets");
  assert.ok(metsRow, "mets row should exist");
  assert.ok(metsRow.classList.contains("favorite-game"));
});

// --- offline: loadTail fails gracefully ---
test("loadTail offline: onError returns false, does not throw", async () => {
  installFetch({ "avond.tail.json": new Error("network down") });

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  const result = await controller.loadTail(globalThis.fetch);
  assert.equal(result, false);
});

// --- in-memory cache: second appendNext does not refetch ---
test("loadTail only fetches once (in-memory cache)", async () => {
  const tailData = fixture("avond.tail.json");
  installFetch({ "avond.tail.json": { ok: true, status: 200, payload: tailData } });

  const container = globalThis.document.createElement("tbody");
  const btn = globalThis.document.createElement("button");
  btn.dataset.page = "avond";
  btn.dataset.tailVersion = "testv1";

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  await controller.loadTail(globalThis.fetch);
  await controller.loadTail(globalThis.fetch); // second call should not fetch again
  const calls = lastCalls().filter((u) => u.includes("avond.tail.json"));
  assert.equal(calls.length, 1);
});

// --- SPEC §6.6: version mismatch → refetch from network (cache-bypass) ---
test("version mismatch then cache-bypass refetch with correct version loads", async () => {
  const right = fixture("avond.tail.json"); // version "testv1", 2 blocks
  const stale = { version: "OLD", blocks: [] };
  // De ?v=-bust-URL matcht de eerste route (specifieker); de kale URL de tweede.
  installFetch({
    "avond.tail.json?v=": { ok: true, status: 200, payload: right },
    "avond.tail.json": { ok: true, status: 200, payload: stale },
  });

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  const ok = await controller.loadTail(globalThis.fetch);
  assert.equal(ok, true, "refetch met juiste version moet slagen");

  // Tweede fetch (cache-bypass) is daadwerkelijk gedaan:
  const busted = lastCalls().filter((u) => u.includes("avond.tail.json?v="));
  assert.equal(busted.length, 1);

  // En de blokken zijn bruikbaar:
  const container = globalThis.document.createElement("tbody");
  const btn = globalThis.document.createElement("button");
  controller.appendNext(container, btn);
  assert.ok(container._insertedBlocks[0].includes("mets"));
});

test("persistent version mismatch (refetch still wrong) returns false → offline", async () => {
  const stale = { version: "OLD", blocks: [] };
  // Zowel kale als ?v=-URL leveren de verkeerde version.
  installFetch({ "avond.tail.json": { ok: true, status: 200, payload: stale } });

  const controller = lm.createController({ page: "avond", tailVersion: "testv1" });
  const ok = await controller.loadTail(globalThis.fetch);
  assert.equal(ok, false, "aanhoudende mismatch → false (nette offline-melding via onError)");
});

test("genuine fetch failure: init() DOES show offline message", async () => {
  installFetch({ "avond.tail.json": new Error("network down") });

  const btn = globalThis.document.createElement("button");
  btn.dataset.page = "avond";
  btn.dataset.tailVersion = "testv1";

  const msgEl = globalThis.document.createElement("div");

  const origQS = globalThis.document.querySelector.bind(globalThis.document);
  globalThis.document.querySelector = (sel) => {
    if (sel === ".loadmore") return btn;
    if (sel === ".loadmore-container") return null;
    if (sel === "tbody") return globalThis.document.createElement("tbody");
    if (sel === ".loadmore-msg") return msgEl;
    return origQS(sel);
  };

  lm.init(globalThis.document, { fetch: globalThis.fetch });

  const clickHandlers = btn._listeners?.click || [];
  for (const h of clickHandlers) await h();

  globalThis.document.querySelector = origQS;

  assert.ok(
    msgEl._textContent.includes("offline"),
    `offline message SHOULD be shown on genuine fetch failure, but got: "${msgEl._textContent}"`
  );
});
