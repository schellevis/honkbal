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
  assert.equal(beta.isBetaEnabled("interest"), false);
});

test("setBetaFeatures round-trips and isBetaEnabled reflects it", () => {
  beta.setBetaFeatures(["interest"]);
  assert.deepEqual(beta.getBetaFeatures(), ["interest"]);
  assert.equal(beta.isBetaEnabled("interest"), true);
  assert.equal(beta.isBetaEnabled("spookfeature"), false);
});

test("unknown feature names are dropped on save and on read", () => {
  beta.setBetaFeatures(["interest", "spookfeature"]);
  assert.deepEqual(beta.getBetaFeatures(), ["interest"]);
  globalThis.localStorage.setItem(beta.BETA_KEY, JSON.stringify(["oud", "interest"]));
  assert.deepEqual(beta.getBetaFeatures(), ["interest"]);
});

// "live" is uit bèta: de naam is geen bekende feature meer en verdwijnt uit oude payloads.
test("graduated feature live is no longer a beta feature", () => {
  assert.ok(!beta.BETA_FEATURES.includes("live"));
  globalThis.localStorage.setItem(beta.BETA_KEY, JSON.stringify(["live", "interest"]));
  assert.deepEqual(beta.getBetaFeatures(), ["interest"]);
  assert.equal(beta.isBetaEnabled("live"), false);
});

test("corrupt storage payload yields empty feature set", () => {
  globalThis.localStorage.setItem(beta.BETA_KEY, "geen json{");
  assert.deepEqual(beta.getBetaFeatures(), []);
  globalThis.localStorage.setItem(beta.BETA_KEY, JSON.stringify({ interest: true }));
  assert.deepEqual(beta.getBetaFeatures(), []);
});
