// Centrale frontend-teammapping.
//
// Canonieke teamnamen = de nicknames uit honkbal/config/teams.py (lowercase). De settings-pagina
// slaat favorieten als deze nicknames op ("red sox", "yankees", "d-backs"), en de server-gerenderde
// schedule-rijen gebruiken dezelfde slugs. De MLB Stats API levert echter volledige namen
// ("Boston Red Sox", "New York Yankees", "Arizona Diamondbacks") en afkortingen. canonicalTeam()
// brengt al die vormen terug naar dezelfde canonieke nickname, zodat favorieten-highlight,
// -sortering én logo's matchen op scores/standings (SPEC §6.1/§6.2/§6.3/§5.5).

const ALIASES = {
  // volledige MLB Stats API team.name
  "atlanta braves": "braves",
  "miami marlins": "marlins",
  "new york mets": "mets",
  "philadelphia phillies": "phillies",
  "washington nationals": "nationals",
  "chicago cubs": "cubs",
  "st. louis cardinals": "cardinals",
  "saint louis cardinals": "cardinals",
  "milwaukee brewers": "brewers",
  "pittsburgh pirates": "pirates",
  "cincinnati reds": "reds",
  "los angeles dodgers": "dodgers",
  "san francisco giants": "giants",
  "san diego padres": "padres",
  "colorado rockies": "rockies",
  "arizona diamondbacks": "d-backs",
  "diamondbacks": "d-backs",
  "dbacks": "d-backs",
  "d backs": "d-backs",
  "baltimore orioles": "orioles",
  "new york yankees": "yankees",
  "boston red sox": "red sox",
  "toronto blue jays": "blue jays",
  "tampa bay rays": "rays",
  "chicago white sox": "white sox",
  "cleveland guardians": "guardians",
  "cleveland indians": "guardians",
  "detroit tigers": "tigers",
  "kansas city royals": "royals",
  "minnesota twins": "twins",
  "houston astros": "astros",
  "los angeles angels": "angels",
  "los angeles angels of anaheim": "angels",
  "oakland athletics": "athletics",
  "sacramento athletics": "athletics",
  "athletics": "athletics",
  "seattle mariners": "mariners",
  "texas rangers": "rangers",
  // afkortingen (ESPN + MLB Stats API varianten)
  "atl": "braves", "mia": "marlins", "nym": "mets", "phi": "phillies",
  "wsh": "nationals", "was": "nationals", "chc": "cubs", "stl": "cardinals",
  "mil": "brewers", "pit": "pirates", "cin": "reds", "lad": "dodgers",
  "sf": "giants", "sfg": "giants", "sd": "padres", "sdp": "padres",
  "col": "rockies", "ari": "d-backs", "az": "d-backs", "bal": "orioles",
  "nyy": "yankees", "bos": "red sox", "tor": "blue jays", "tb": "rays",
  "tbr": "rays", "chw": "white sox", "cws": "white sox", "cle": "guardians",
  "det": "tigers", "kc": "royals", "kcr": "royals", "min": "twins",
  "hou": "astros", "laa": "angels", "ana": "angels", "oak": "athletics",
  "ath": "athletics", "sea": "mariners", "tex": "rangers",
};

// Normaliseer naar een canonieke nickname. Idempotent op al-canonieke waarden ("red sox" -> "red
// sox"). Onbekende invoer (bv. all-star pseudo-teams, minor-league namen) -> genormaliseerde invoer.
export function canonicalTeam(name) {
  const s = String(name ?? "")
    .trim()
    .toLowerCase()
    .replace(/\+/g, " ")
    .replace(/\s+/g, " ");
  if (!s) return s;
  return ALIASES[s] || s;
}
