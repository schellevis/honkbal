from __future__ import annotations

from honkbal.config.teams import normalize_team

# Handmatige MLB-rivalrylijst. Tier 3 zijn historische/landelijk herkenbare rivalries,
# tier 2 zijn vaste regionale/interleague rivalries, tier 1 zijn lichtere actuele signalen.
_RAW_RIVALRIES: tuple[tuple[int, tuple[str, str]], ...] = (
    (3, ("yankees", "red sox")),
    (3, ("dodgers", "giants")),
    (3, ("cubs", "cardinals")),
    (2, ("yankees", "mets")),
    (2, ("dodgers", "angels")),
    (2, ("cubs", "white sox")),
    (2, ("rangers", "astros")),
    (2, ("orioles", "nationals")),
    (2, ("rays", "marlins")),
    (2, ("reds", "guardians")),
    (2, ("royals", "cardinals")),
    (2, ("phillies", "pirates")),
    (2, ("padres", "mariners")),
    (1, ("dodgers", "padres")),
    (1, ("mets", "phillies")),
    (1, ("mets", "braves")),
    (1, ("braves", "phillies")),
    (1, ("astros", "mariners")),
    (1, ("blue jays", "yankees")),
    (1, ("brewers", "cubs")),
)

RIVALRY_TIERS: dict[frozenset[str], int] = {
    frozenset((normalize_team(a), normalize_team(b))): tier
    for tier, (a, b) in _RAW_RIVALRIES
}


def rivalry_tier(away: str, home: str) -> int:
    return RIVALRY_TIERS.get(
        frozenset((normalize_team(away), normalize_team(home))), 0
    )
