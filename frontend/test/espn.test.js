import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom, dispatchStorageEvent } from "./dom-stub.js";

let espn;
beforeEach(async () => {
  installDom();
  espn = await import("../js/espn.js?" + Math.random());
});
afterEach(() => restoreDom());

function makeCheckbox(doc, value) {
  const cb = doc.createElement("input");
  cb.type = "checkbox";
  cb.name = "tv";
  cb.value = value;
  doc.body.appendChild(cb);
  return cb;
}

test("defaults zonder localStorage: logo's aan, NL-filter uit", () => {
  assert.equal(espn.getShowLogos(), true);
  assert.equal(espn.getNlOnly(), false);
});

test("setters round-trippen via localStorage", () => {
  espn.setShowLogos(false);
  espn.setNlOnly(true);
  assert.equal(espn.getShowLogos(), false);
  assert.equal(espn.getNlOnly(), true);
  assert.equal(globalThis.localStorage.getItem(espn.LOGOS_KEY), "0");
  assert.equal(globalThis.localStorage.getItem(espn.NL_ONLY_KEY), "1");

  espn.setShowLogos(true);
  espn.setNlOnly(false);
  assert.equal(espn.getShowLogos(), true);
  assert.equal(espn.getNlOnly(), false);
});

test("applyTvClasses: waarheidstabel van body-klassen", () => {
  const doc = globalThis.document;
  const cases = [
    [true, false, false, false],
    [false, false, true, false],
    [true, true, false, true],
    [false, true, true, true],
  ];
  for (const [logos, nlOnly, expectOff, expectNl] of cases) {
    espn.setShowLogos(logos);
    espn.setNlOnly(nlOnly);
    espn.applyTvClasses(doc);
    assert.equal(doc.body.classList.contains("espn-off"), expectOff, `logos=${logos}`);
    assert.equal(doc.body.classList.contains("espn-nl-only"), expectNl, `nlonly=${nlOnly}`);
  }
});

test("init past klassen toe en volgt cross-tab storage-events", () => {
  const doc = globalThis.document;
  espn.init(doc);
  assert.equal(doc.body.classList.contains("espn-off"), false);

  globalThis.localStorage.setItem(espn.LOGOS_KEY, "0");
  dispatchStorageEvent(espn.LOGOS_KEY, "0");
  assert.equal(doc.body.classList.contains("espn-off"), true);

  // Events voor andere keys veranderen niets.
  globalThis.localStorage.setItem(espn.LOGOS_KEY, "1");
  dispatchStorageEvent("honkbal-favorites", "[]");
  assert.equal(doc.body.classList.contains("espn-off"), true);
});

test("initTvCheckboxes: sync bij laden en direct opslaan bij wijziging", () => {
  const doc = globalThis.document;
  espn.setNlOnly(true);
  const logosCb = makeCheckbox(doc, "logos");
  const nlCb = makeCheckbox(doc, "nlonly");

  espn.initTvCheckboxes(doc);
  assert.equal(logosCb.checked, true);
  assert.equal(nlCb.checked, true);

  logosCb.checked = false;
  logosCb.dispatchEvent({ type: "change" });
  assert.equal(espn.getShowLogos(), false);
  assert.equal(doc.body.classList.contains("espn-off"), true);

  nlCb.checked = false;
  nlCb.dispatchEvent({ type: "change" });
  assert.equal(espn.getNlOnly(), false);
  assert.equal(doc.body.classList.contains("espn-nl-only"), false);
});

test("corrupte storage-toegang faalt zacht naar defaults", () => {
  globalThis.localStorage = {
    getItem() { throw new Error("storage kapot"); },
  };
  assert.equal(espn.getShowLogos(), true);
  assert.equal(espn.getNlOnly(), false);
});
