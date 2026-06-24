from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from honkbal.config.teams import normalize_team
from honkbal.enrichment import PlayoffOddsByTeam, TeamPlayoffOdds


def load_playoff_odds(data_dir: Path) -> PlayoffOddsByTeam:
    """Load optional normalized playoff odds from data_dir/playoff_odds.json.

    The first implementation deliberately avoids scraping a third-party odds page during the
    production build. If an external process writes normalized odds into the cache, render uses
    them; otherwise enrichment falls back to standings/rivalry signals.
    """
    path = data_dir / "playoff_odds.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return parse_playoff_odds(raw)
    except (OSError, ValueError, TypeError):
        return {}


def parse_playoff_odds(payload: dict[str, Any]) -> PlayoffOddsByTeam:
    teams = payload.get("teams", {})
    if isinstance(teams, dict):
        iterable = teams.items()
    elif isinstance(teams, list):
        iterable = ((_team_name(entry), entry) for entry in teams)
    else:
        return {}

    out: PlayoffOddsByTeam = {}
    for key, entry in iterable:
        if not isinstance(entry, dict):
            continue
        team = normalize_team(str(entry.get("team") or key))
        out[team] = TeamPlayoffOdds(
            team=team,
            make_playoffs=_prob(entry.get("make_playoffs")),
            win_division=_prob(entry.get("win_division")),
            win_world_series=_prob(entry.get("win_world_series")),
        )
    return out


def _team_name(entry: Any) -> str:
    if isinstance(entry, dict):
        value = entry.get("team")
        if isinstance(value, str):
            return value
    return ""


def _prob(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
            try:
                return float(cleaned) / 100.0
            except ValueError:
                return None
        value = cleaned
    try:
        prob = float(value)
    except (TypeError, ValueError):
        return None
    if prob > 1.0:
        prob = prob / 100.0
    return max(0.0, min(1.0, prob))
