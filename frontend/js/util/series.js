// series.js — postseason-serie-info uit een MLB-Stats-API-schedulegame (SPEC §6.12).
// Werkt op de gewone `hydrate=linescore,team`-payload: gameType, seriesGameNumber, ifNecessary,
// team.league en (in de postseason) teams.*.leagueRecord = winst/verlies binnen de serie.

const PHASE = { F: "WC", D: "DS", L: "CS" };
const LEAGUE = { 103: "AL", 104: "NL" };

function leagueShort(game) {
  for (const side of ["home", "away"]) {
    const short = LEAGUE[game?.teams?.[side]?.team?.league?.id];
    if (short) return short;
  }
  const m = /^(AL|NL)\b/.exec(game?.seriesDescription ?? "");
  return m ? m[1] : "";
}

// "NLWC - Game 3", "ALDS - Game 5*", "World Series - Game 1" — zelfde vorm als de ESPN-labels
// van het statische schema; `*` = if necessary. null buiten de postseason.
export function seriesLabel(game) {
  const type = game?.gameType;
  let phase;
  if (type === "W") phase = "World Series";
  else if (PHASE[type]) phase = `${leagueShort(game)}${PHASE[type]}`;
  else return null;
  const n = game.seriesGameNumber;
  if (!n) return phase;
  return `${phase} - Game ${n}${game.ifNecessary === "Y" ? "*" : ""}`;
}

// Serie-stand "(x-y)" met de overwinningen van het uitteam vooraan (zoals de rij "Away @ Home").
// leagueRecord telt in de postseason alleen de huidige serie; vóór game 1 (0-0) → null.
export function seriesRecord(game) {
  if (!seriesLabel(game)) return null;
  const away = game.teams?.away?.leagueRecord?.wins;
  const home = game.teams?.home?.leagueRecord?.wins;
  if (!Number.isInteger(away) || !Number.isInteger(home)) return null;
  if (away === 0 && home === 0) return null;
  return `(${away}-${home})`;
}

// Badge-tekst: label + evt. stand, bv. "NLWC - Game 3 (1-1)".
export function seriesBadgeText(game) {
  const label = seriesLabel(game);
  if (!label) return null;
  const record = seriesRecord(game);
  return record ? `${label} ${record}` : label;
}
