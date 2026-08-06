"""Tv-gids: koppel wedstrijden aan ESPN-uitzendingen (SPEC §3.3).

`load_tv_guide` leest het genormaliseerde `.data/tv_guide.json` (geschreven door
`fetch/tv_guide.py`); `build_tv_lookup` koppelt airings aan games voor de render.
Beide falen zacht: geen bestand of onbruikbare data betekent geen zenderlogo's,
nooit een kapotte build.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, ValidationError

from honkbal.clock import AMSTERDAM
from honkbal.config.teams import normalize_team
from honkbal.config.toggles import TV_MATCH_TOLERANCE_MIN
from honkbal.models import Game

CHANNELS = frozenset({"espn", "espn2", "espn3", "espn4", "espn_extra"})


class TvAiring(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel: str
    start: datetime
    end: datetime | None = None
    teams: frozenset[str] = frozenset()
    nl_commentary: bool = False
    live: bool = True
    title: str = ""


class TvMatch(NamedTuple):
    channel: str
    nl_commentary: bool


# Sleutel: (start_epoch, away_slug, home_slug) — dezelfde velden als op RowContext, zodat de
# render per rij zonder herberekening kan opzoeken.
TvLookup = dict[tuple[int, str, str], TvMatch]


def load_tv_guide(data_dir: Path) -> list[TvAiring]:
    path = data_dir / "tv_guide.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = raw.get("airings") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return []

    airings: list[TvAiring] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            airing = TvAiring(**entry)
        except ValidationError:
            continue
        # Naïeve starttijden en onbekende kanalen zijn onbruikbaar; iets anders dan een
        # teampaar behandelen we als teamloos (tijdpass).
        if airing.channel not in CHANNELS or airing.start.tzinfo is None:
            continue
        if len(airing.teams) != 2:
            airing = airing.model_copy(update={"teams": frozenset()})
        airings.append(airing)
    return airings


def build_tv_lookup(games: list[Game], airings: list[TvAiring]) -> TvLookup:
    """Koppel elke uitzending aan hoogstens één wedstrijd.

    Teampass eerst: ongeordende teamnaam-gelijkheid + starttijd binnen de tolerantie,
    kleinste verschil wint. Daarna de tijdpass voor teamloze airings (tvgids-fallback,
    all-star): alleen toewijzen als precies één nog niet-gematchte wedstrijd binnen de
    tolerantie valt — bij ambiguïteit (doubleheaders, gelijktijdige games) liever geen
    logo dan een verkeerd logo. TBD-wedstrijden en replays matchen nooit.
    """
    tolerance = TV_MATCH_TOLERANCE_MIN * 60

    timed: list[tuple[int, str, str, frozenset[str]]] = []
    for g in games:
        if g.time_ams is None:
            continue
        epoch = int(datetime.combine(g.date_ams, g.time_ams, tzinfo=AMSTERDAM).timestamp())
        away = normalize_team(g.away)
        home = normalize_team(g.home)
        timed.append((epoch, away, home, frozenset((away, home))))

    lookup: TvLookup = {}
    live = sorted((a for a in airings if a.live), key=lambda a: a.start)
    teamless = []
    for airing in live:
        if airing.teams:
            _assign_team_match(airing, timed, lookup, tolerance)
        else:
            teamless.append(airing)
    for airing in teamless:
        _assign_time_match(airing, timed, lookup, tolerance)
    return lookup


def _assign_team_match(
    airing: TvAiring,
    timed: list[tuple[int, str, str, frozenset[str]]],
    lookup: TvLookup,
    tolerance: int,
) -> None:
    airing_epoch = int(airing.start.timestamp())
    best: tuple[int, tuple[int, str, str]] | None = None
    for epoch, away, home, teamset in timed:
        if teamset != airing.teams:
            continue
        delta = abs(epoch - airing_epoch)
        if delta > tolerance:
            continue
        if best is None or delta < best[0]:
            best = (delta, (epoch, away, home))
    if best is None:
        return
    # Een al gematchte game (bijv. simulcast) houdt zijn eerste kanaal.
    lookup.setdefault(best[1], TvMatch(airing.channel, airing.nl_commentary))


def _assign_time_match(
    airing: TvAiring,
    timed: list[tuple[int, str, str, frozenset[str]]],
    lookup: TvLookup,
    tolerance: int,
) -> None:
    airing_epoch = int(airing.start.timestamp())
    candidates = [
        (epoch, away, home)
        for epoch, away, home, _ in timed
        if (epoch, away, home) not in lookup and abs(epoch - airing_epoch) <= tolerance
    ]
    if len(candidates) == 1:
        lookup[candidates[0]] = TvMatch(airing.channel, airing.nl_commentary)
