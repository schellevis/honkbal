import { escapeHtml } from "./dom.js";
import { canonicalTeam } from "./teams.js";

// All slugs with a known logo file (generated from static/img/ listing)
const KNOWN_SLUGS = new Set([
  "american+league", "angels", "astros", "athletics", "blue+jays",
  "braves", "brewers", "cardinals", "cleveland", "cubs", "d-backs",
  "dodgers", "giants", "guardians", "mariners", "marlins", "mets",
  "national+league", "nationals", "orioles", "padres", "phillies",
  "pirates", "rangers", "rays", "red+sox", "reds", "rockies",
  "royals", "tigers", "twins", "white+sox", "yankees",
]);

// Slugs that have a dark variant
const HAS_DARK = new Set([
  "braves", "cleveland", "dodgers", "guardians", "phillies",
  "rays", "royals", "tigers", "yankees",
]);

// All-star team name → logo slug mapping (mirrors Python side)
const ALLSTAR_MAP = {
  "al all-stars": "american+league",
  "american league all-stars": "american+league",
  "american": "american+league",
  "nl all-stars": "national+league",
  "national league all-stars": "national+league",
  "national": "national+league",
};

// All-star team name → volledige weergavenaam (mirror van honkbal/render/logos.py::display_name).
// De MLB Stats API levert voor de all-star game korte, dubbelzinnige vormen ("American",
// "AL All-Stars"); toon net als de schedule-pagina "American League" / "National League".
const ALLSTAR_DISPLAY = {
  "al all-stars": "American League",
  "american league all-stars": "American League",
  "american": "American League",
  "nl all-stars": "National League",
  "national league all-stars": "National League",
  "national": "National League",
};

// Geef de weergavenaam voor een team; all-star pseudo-teams krijgen hun volledige liganaam,
// alle andere namen worden ongewijzigd teruggegeven ("Yankees" -> "Yankees").
export function displayName(name) {
  return ALLSTAR_DISPLAY[String(name).trim().toLowerCase()] || name;
}

export function logoSlug(name) {
  // Check allstar mapping first
  const allstar = ALLSTAR_MAP[String(name).trim().toLowerCase()];
  if (allstar) return allstar;
  // Canonicaliseer (volledige API-namen/afkortingen -> nickname), dan slug: spaties→+.
  // Zo levert "Boston Red Sox" -> "red sox" -> "red+sox" i.p.v. "boston+red+sox".
  return canonicalTeam(name).replace(/ /g, "+");
}

export function logoPicture(name) {
  const slug = logoSlug(name);
  if (!KNOWN_SLUGS.has(slug)) {
    return `<span class="logofill">${escapeHtml(name)}</span>`;
  }
  const imgSrc = `/img/${slug}-fs8.png`;
  const alt = escapeHtml(name);
  if (HAS_DARK.has(slug)) {
    const darkSrc = `/img/${slug}-dark.png`;
    return (
      `<picture class="team">` +
      `<source srcset="${darkSrc}" media="(prefers-color-scheme: dark)">` +
      `<img src="${imgSrc}" alt="${alt}" height="20">` +
      `</picture>`
    );
  }
  return `<picture class="team"><img src="${imgSrc}" alt="${alt}" height="20"></picture>`;
}
