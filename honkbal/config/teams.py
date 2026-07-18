from __future__ import annotations

TEAMS_NL: tuple[str, ...] = (
    "braves", "marlins", "mets", "phillies", "nationals",
    "cubs", "cardinals", "brewers", "pirates", "reds",
    "dodgers", "giants", "padres", "rockies", "d-backs",
)
TEAMS_AL: tuple[str, ...] = (
    "orioles", "yankees", "red sox", "blue jays", "rays",
    "white sox", "guardians", "tigers", "royals", "twins",
    "astros", "angels", "athletics", "mariners", "rangers",
)
EXTRA: tuple[str, ...] = (
    "national league", "american league", "al all-stars", "nl all-stars",
)

MLB_TEAMS: frozenset[str] = frozenset(TEAMS_NL) | frozenset(TEAMS_AL)
ALLOWLIST_RENDER: frozenset[str] = MLB_TEAMS | frozenset(EXTRA)

TEAM_ABBR: tuple[str, ...] = (
    "nym", "nyy", "atl", "bal", "bos", "chc", "chw", "cin", "cle", "col",
    "det", "hou", "kc", "laa", "lad", "mia", "mil", "min", "oak", "phi",
    "pit", "sd", "sf", "sea", "stl", "tb", "tex", "tor", "wsh", "ari",
)

TEAM_DIVISIONS: dict[str, str] = {
    "orioles": "AL East",
    "yankees": "AL East",
    "red sox": "AL East",
    "blue jays": "AL East",
    "rays": "AL East",
    "white sox": "AL Central",
    "guardians": "AL Central",
    "tigers": "AL Central",
    "royals": "AL Central",
    "twins": "AL Central",
    "astros": "AL West",
    "angels": "AL West",
    "athletics": "AL West",
    "mariners": "AL West",
    "rangers": "AL West",
    "braves": "NL East",
    "marlins": "NL East",
    "mets": "NL East",
    "phillies": "NL East",
    "nationals": "NL East",
    "cubs": "NL Central",
    "cardinals": "NL Central",
    "brewers": "NL Central",
    "pirates": "NL Central",
    "reds": "NL Central",
    "dodgers": "NL West",
    "giants": "NL West",
    "padres": "NL West",
    "rockies": "NL West",
    "d-backs": "NL West",
}


def normalize_team(name: str) -> str:
    n = name.strip().lower().replace("+", " ")
    if n in ("diamondbacks", "dbacks"):
        return "d-backs"
    return n


def team_slug(name: str) -> str:
    n = name.strip().lower()
    if n in ("diamondbacks", "dbacks"):
        n = "d-backs"
    return n.replace(" ", "+")


def league_of(name: str) -> str | None:
    n = normalize_team(name)
    if n in frozenset(TEAMS_AL):
        return "AL"
    if n in frozenset(TEAMS_NL):
        return "NL"
    return None


def division_of(name: str) -> str | None:
    return TEAM_DIVISIONS.get(normalize_team(name))
