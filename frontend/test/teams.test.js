import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalTeam, teamAbbr } from "../js/util/teams.js";

test("canonicalTeam maps full MLB Stats API names to nicknames", () => {
  assert.equal(canonicalTeam("Boston Red Sox"), "red sox");
  assert.equal(canonicalTeam("New York Yankees"), "yankees");
  assert.equal(canonicalTeam("Arizona Diamondbacks"), "d-backs");
  assert.equal(canonicalTeam("St. Louis Cardinals"), "cardinals");
  assert.equal(canonicalTeam("Toronto Blue Jays"), "blue jays");
  assert.equal(canonicalTeam("Oakland Athletics"), "athletics");
  assert.equal(canonicalTeam("Cleveland Guardians"), "guardians");
});

test("canonicalTeam maps abbreviations (ESPN + MLB Stats variants)", () => {
  assert.equal(canonicalTeam("BOS"), "red sox");
  assert.equal(canonicalTeam("NYY"), "yankees");
  assert.equal(canonicalTeam("ARI"), "d-backs");
  assert.equal(canonicalTeam("AZ"), "d-backs");
  assert.equal(canonicalTeam("CWS"), "white sox");
  assert.equal(canonicalTeam("CHW"), "white sox");
});

test("canonicalTeam is idempotent on already-canonical nicknames", () => {
  assert.equal(canonicalTeam("red sox"), "red sox");
  assert.equal(canonicalTeam("yankees"), "yankees");
  assert.equal(canonicalTeam("d-backs"), "d-backs");
  assert.equal(canonicalTeam("Red+Sox"), "red sox");
});

test("canonicalTeam leaves unknown/pseudo teams as normalized input", () => {
  assert.equal(canonicalTeam("AL All-Stars"), "al all-stars");
  assert.equal(canonicalTeam(""), "");
});

test("teamAbbr resolves a standard abbreviation from any known team form", () => {
  // Fallback wanneer het API-team-object geen `abbreviation` heeft (SPEC §6.2): de volledige
  // naam mag niet in de afkorting-kolom belanden (anders "New York Mets" -> "N...").
  assert.equal(teamAbbr("Houston Astros"), "HOU");
  assert.equal(teamAbbr("New York Mets"), "NYM");
  assert.equal(teamAbbr("Washington Nationals"), "WSH");
  assert.equal(teamAbbr("Chicago White Sox"), "CWS");
  assert.equal(teamAbbr("astros"), "HOU"); // al-canonieke nickname
});

test("teamAbbr returns empty string for unknown/pseudo teams", () => {
  assert.equal(teamAbbr("AL All-Stars"), "");
  assert.equal(teamAbbr(""), "");
});
