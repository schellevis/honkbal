from __future__ import annotations

# team_id <-> team mapping voor de MLB-ticketing-CSV-feed.
# Eenmalig vastgesteld via fetch.discover_feeds.discover over range 105..161 (SPEC §3.2) en
# live gevalideerd op 2026-06-22 (30/30 teams + all-star kloppen, 0 mismatches; affiliate=105-107).
# De dagelijkse build haalt ALLEEN deze feeds op (30 MLB-teams + all-star), niet de hele range.
# Hervalideer met een live discover-run bij twijfel/feed-wijzigingen.
TEAM_FEEDS: dict[str, int] = {
    "angels": 108,
    "astros": 117,
    "athletics": 133,
    "blue jays": 141,
    "braves": 144,
    "brewers": 158,
    "cardinals": 138,
    "cubs": 112,
    "d-backs": 109,
    "dodgers": 119,
    "giants": 137,
    "guardians": 114,
    "marlins": 146,
    "mariners": 136,
    "mets": 121,
    "nationals": 120,
    "orioles": 110,
    "padres": 135,
    "phillies": 143,
    "pirates": 134,
    "rangers": 140,
    "rays": 139,
    "red sox": 111,
    "reds": 113,
    "rockies": 115,
    "royals": 118,
    "tigers": 116,
    "twins": 142,
    "white sox": 145,
    "yankees": 147,
}
ALLSTAR_FEED_ID: int = 159  # live gevalideerd 2026-06-22
