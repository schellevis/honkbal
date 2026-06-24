import { test } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom } from "./dom-stub.js";
import { installFetch, restoreFetch, lastCalls } from "./fetch-stub.js";

test("dom stub: dataset + classList + localStorage", () => {
  installDom();
  try {
    globalThis.localStorage.setItem("k", "v");
    assert.equal(globalThis.localStorage.getItem("k"), "v");
    const row = globalThis.document.createElement("tr");
    row.dataset.awayTeam = "yankees";
    row.classList.add("favorite-game");
    assert.ok(row.classList.contains("favorite-game"));
    assert.equal(row.dataset.awayTeam, "yankees");
  } finally {
    restoreDom();
  }
});

test("fetch stub: routes + offline", async () => {
  installFetch({ "/ok": { ok: true, status: 200, payload: { hi: 1 } }, "/down": new Error("offline") });
  try {
    const r = await fetch("https://x/ok");
    assert.deepEqual(await r.json(), { hi: 1 });
    await assert.rejects(() => fetch("https://x/down"));
    assert.ok(lastCalls().some((u) => u.includes("/ok")));
  } finally {
    restoreFetch();
  }
});
