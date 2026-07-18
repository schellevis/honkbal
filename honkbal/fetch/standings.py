from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from honkbal.clock import Clock
from honkbal.config.teams import normalize_team
from honkbal.enrichment import StandingsByTeam, TeamStanding
from honkbal.fetch.http import build_client

STANDINGS_URL = (
    "https://statsapi.mlb.com/api/v1/standings"
    "?leagueId=103,104&standingsTypes=regularSeason&hydrate=team&season={season}"
)

_FULL_NAME_TO_TEAM = {
    "arizona diamondbacks": "d-backs",
    "atlanta braves": "braves",
    "baltimore orioles": "orioles",
    "boston red sox": "red sox",
    "chicago cubs": "cubs",
    "chicago white sox": "white sox",
    "cincinnati reds": "reds",
    "cleveland guardians": "guardians",
    "colorado rockies": "rockies",
    "detroit tigers": "tigers",
    "houston astros": "astros",
    "kansas city royals": "royals",
    "los angeles angels": "angels",
    "los angeles dodgers": "dodgers",
    "miami marlins": "marlins",
    "milwaukee brewers": "brewers",
    "minnesota twins": "twins",
    "new york mets": "mets",
    "new york yankees": "yankees",
    "oakland athletics": "athletics",
    "athletics": "athletics",
    "philadelphia phillies": "phillies",
    "pittsburgh pirates": "pirates",
    "san diego padres": "padres",
    "san francisco giants": "giants",
    "seattle mariners": "mariners",
    "st. louis cardinals": "cardinals",
    "tampa bay rays": "rays",
    "texas rangers": "rangers",
    "toronto blue jays": "blue jays",
    "washington nationals": "nationals",
}


class StandingsFetchResult:
    def __init__(self, *, ok: bool, count: int):
        self.ok = ok
        self.count = count


def fetch_standings(
    clock: Clock,
    *,
    data_dir: Path,
    client: httpx.Client | None = None,
) -> StandingsFetchResult:
    own_client = client is None
    client = client or build_client()
    try:
        res = client.get(STANDINGS_URL.format(season=clock.now().year))
        res.raise_for_status()
        standings = parse_standings(res.json())
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return StandingsFetchResult(ok=False, count=0)
    finally:
        if own_client:
            client.close()

    if not standings:
        return StandingsFetchResult(ok=False, count=0)

    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": clock.now().isoformat(),
        "season": clock.now().year,
        "teams": {team: standing.model_dump() for team, standing in standings.items()},
    }
    (data_dir / "standings.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return StandingsFetchResult(ok=True, count=len(standings))


def load_standings(data_dir: Path) -> StandingsByTeam:
    path = data_dir / "standings.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        teams = raw.get("teams", {})
        return {
            normalize_team(team): TeamStanding(**entry)
            for team, entry in teams.items()
        }
    except (OSError, ValueError, TypeError):
        return {}


def parse_standings(payload: dict[str, Any]) -> StandingsByTeam:
    out: StandingsByTeam = {}
    for record in payload.get("records", []):
        for team_record in record.get("teamRecords", []):
            team = _team_key(team_record.get("team", {}))
            if team is None:
                continue
            out[team] = TeamStanding(
                team=team,
                wins=_int_or_none(team_record.get("wins")),
                losses=_int_or_none(team_record.get("losses")),
                winning_percentage=_pct_or_none(team_record.get("winningPercentage")),
                division_rank=_int_or_none(team_record.get("divisionRank")),
                games_back=_games_back(team_record.get("gamesBack")),
                wild_card_games_back=_games_back(team_record.get("wildCardGamesBack")),
                run_differential=_int_or_none(team_record.get("runDifferential")),
                streak=_streak(team_record),
                last_ten=_last_ten(team_record),
            )
    return out


def _team_key(team_obj: dict[str, Any]) -> str | None:
    for key in ("name", "teamName"):
        value = team_obj.get(key)
        if isinstance(value, str):
            mapped = _FULL_NAME_TO_TEAM.get(value.strip().lower())
            if mapped:
                return mapped
            normalized = normalize_team(value)
            if normalized in _FULL_NAME_TO_TEAM.values():
                return normalized
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pct_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _games_back(value: Any) -> float | None:
    if value in (None, "-", ""):
        return 0.0
    if isinstance(value, str) and value.startswith("+"):
        value = value[1:]
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _streak(team_record: dict[str, Any]) -> str | None:
    streak = team_record.get("streak")
    if isinstance(streak, dict):
        value = streak.get("streakCode")
        if isinstance(value, str):
            return value
    return None


def _last_ten(team_record: dict[str, Any]) -> str | None:
    for record in team_record.get("records", {}).get("splitRecords", []):
        if record.get("type") == "lastTen":
            wins = record.get("wins")
            losses = record.get("losses")
            if wins is not None and losses is not None:
                return f"{wins}-{losses}"
    return None
