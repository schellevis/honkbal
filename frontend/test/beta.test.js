import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { installDom, restoreDom } from "./dom-stub.js";

let beta;
beforeEach(async () => {
  installDom();
  beta = await import("../js/beta.js?" + Math.random());
});
afterEach(() => restoreDom());

test("beta features default to off", () => {
  assert.deepEqual(beta.getBetaFeatures(), []);
  assert.equal(beta.isBetaEnabled("live"), false);
});

test("setBetaFeatures round-trips and isBetaEnabled reflects it", () => {
  beta.setBetaFeatures(["live"]);
  assert.deepEqual(beta.getBetaFeatures(), ["live"]);
  assert.equal(beta.isBetaEnabled("live"), true);
  assert.equal(beta.isBetaEnabled("interest"), false);
});

test("unknown feature names are dropped on save and on read", () => {
  beta.setBetaFeatures(["live", "spookfeature"]);
  assert.deepEqual(beta.getBetaFeatures(), ["live"]);
  globalThis.localStorage.setItem(beta.BETA_KEY, JSON.stringify(["oud", "interest"]));
  assert.deepEqual(beta.getBetaFeatures(), ["interest"]);
});

test("corrupt storage payload yields empty feature set", () => {
  globalThis.localStorage.setItem(beta.BETA_KEY, "geen json{");
  assert.deepEqual(beta.getBetaFeatures(), []);
  globalThis.localStorage.setItem(beta.BETA_KEY, JSON.stringify({ live: true }));
  assert.deepEqual(beta.getBetaFeatures(), []);
});
