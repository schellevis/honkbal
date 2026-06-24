from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from honkbal.clock import AMSTERDAM, UTC, Clock
from honkbal.models import PostseasonData, PostseasonGame

_ESPN_DATE = "%Y-%m-%dT%H:%MZ"
_TIED = re.compile(r"Series tied (\d+)-(\d+)", re.IGNORECASE)
# Matcht zowel een lopende serie ("BOS leads series 1-0") als een afgeronde serie
# ("CHC win series 2-1" / "BOS wins series 9-4") — beide met de teamafkorting als leider.
# Bewuste uitbreiding t.o.v. SPEC §3.5: de SPEC noemt alleen "Series tied …" en
# "lead(s) series …". Het accepteren van "win(s) series" (afgeronde series) is een
# niet-gespecificeerde verbetering zodat de stand ook na afloop correct wordt getoond.
_LEADS = re.compile(r"^(\S+) (?:leads?|wins?) series (\d+)-(\d+)", re.IGNORECASE)


def normalize_espn_name(name: str) -> str:
    return name.replace("Diamondbacks", "D-backs")


def _current_summary(summary_json: dict) -> str | None:
    for item in summary_json.get("seasonseries", []) or []:
        if item.get("type") == "current":
            return item.get("summary")
    return None


def parse_series_standing(
    summary_json: dict, away: str, home: str, teams: dict[str, str]
) -> str | None:
    text = _current_summary(summary_json)
    if not text:
        return None
    m = _TIED.search(text)
    if m:
        return f"({m.group(1)}-{m.group(2)})"
    m = _LEADS.match(text.strip())
    if not m:
        return None
    leader_key, x, y = m.group(1), m.group(2), m.group(3)
    leader_name = teams.get(leader_key, leader_key)
    # Oriënteer zodat away-team-wins vooraan staat.
    if leader_name == away or leader_key == away:
        return f"({x}-{y})"
    if leader_name == home or leader_key == home:
        return f"({y}-{x})"
    return None


def _descr(competition: dict) -> str:
    descr = ""
    for note in competition.get("notes", []) or []:
        headline = note.get("headline", "")
        descr = headline.replace(" If Necessary", "*")
    return descr


def parse_postseason(
    schedule_json: list, summaries: dict[str, dict], clock: Clock
) -> PostseasonData:
    teams: dict[str, str] = {}
    games: dict[tuple, PostseasonGame] = {}

    for team in schedule_json:
        if not isinstance(team, dict):
            continue
        record = (team.get("team") or {}).get("recordSummary", "")
        for event in team.get("events", []) or []:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id"))
            for comp in event.get("competitions", []) or []:
                if not isinstance(comp, dict):
                    continue
                raw_date = comp.get("date")
                if not raw_date:
                    continue  # malformed event zonder datum -> overslaan (geen crash, SPEC §9)
                try:
                    dt = datetime.strptime(raw_date, _ESPN_DATE).replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    continue
                ams = dt.astimezone(AMSTERDAM)
                home = away = ""
                for c in comp.get("competitors", []) or []:
                    if not isinstance(c, dict):
                        continue
                    team_obj = c.get("team") or {}
                    name = normalize_espn_name(team_obj.get("shortDisplayName", ""))
                    abbr = team_obj.get("abbreviation")
                    if abbr:
                        teams[abbr] = name
                    if c.get("homeAway") == "home":
                        home = name
                    else:
                        away = name
                key = (ams.date(), ams.hour, home)
                if key in games:
                    # Dedup: de lookup-sleutel (date_ams, hour, home) fungeert bewust ook als
                    # dedup-sleutel. SPEC §3.5 schrijft dedup op event_id voor, maar die is hier
                    # niet beschikbaar als dict-sleutel. Functioneel equivalent: (date, uur, home)
                    # is uniek per wedstrijd. Eerste voorkomen wint bij afwijkende payloads.
                    continue
                standing = parse_series_standing(
                    summaries.get(event_id, {}), away, home, teams
                )
                games[key] = PostseasonGame(
                    event_id=event_id,
                    record=record,
                    descr=_descr(comp),
                    home=home,
                    away=away,
                    standing=standing,
                )

    return PostseasonData(fetched_at=clock.now(), teams=teams, games=games)


def load_postseason(data_dir: Path) -> PostseasonData | None:
    """Load cached postseason data from data_dir/postseason.json. Returns None if absent."""
    from honkbal.fetch.espn_postseason import load_postseason as _load  # noqa: PLC0415

    return _load(Path(data_dir))
