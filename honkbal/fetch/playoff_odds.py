from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from honkbal.clock import Clock
from honkbal.config.teams import normalize_team
from honkbal.enrichment import PlayoffOddsByTeam, TeamPlayoffOdds
from honkbal.fetch.http import build_client
from honkbal.fetch.standings import _FULL_NAME_TO_TEAM

FANGRAPHS_URL = "https://www.fangraphs.com/api/playoff-odds/odds"
BASEBALL_REFERENCE_URL = (
    "https://www.baseball-reference.com/leagues/majors/{season}-playoff-odds.shtml"
)

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# FanGraphs playoff-odds API, live gevalideerd op 2026-06-24:
# endpoint blokkeerde kale clients met Cloudflare 403; de publieke HTML toont dezelfde kolommen.
# De API-kolommen hieronder zijn de adaptergrens; alternatieven vangen casing-wijzigingen.
_FG_FIELD = {
    "team": "TeamName",
    "make_playoffs": "MakePlayoffs",
    "win_division": "WinDiv",
    "win_world_series": "WinWS",
}

# Baseball-Reference playoff-odds HTML, live gevalideerd op 2026-06-24:
# pagina /leagues/majors/<season>-playoff-odds.shtml; kolommen "Team",
# "Division Winner", "Make Playoffs"/"Wild Card" en "World Series".
_BR_FIELD = {
    "team": "Team",
    "make_playoffs": "Make Playoffs",
    "win_division": "Division Winner",
    "win_world_series": "World Series",
}


class PlayoffOddsFetchResult:
    def __init__(self, *, ok: bool, count: int, source: str | None = None):
        self.ok = ok
        self.count = count
        self.source = source


def fetch_playoff_odds(
    clock: Clock,
    *,
    data_dir: Path,
    client: httpx.Client | None = None,
) -> PlayoffOddsFetchResult:
    own_client = client is None
    client = client or build_client()
    try:
        source, odds = _fetch_from_sources(clock, client=client)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return PlayoffOddsFetchResult(ok=False, count=0)
    finally:
        if own_client:
            client.close()

    if not odds:
        return PlayoffOddsFetchResult(ok=False, count=0)

    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": clock.now().isoformat(),
        "season": clock.now().year,
        "source": source,
        "teams": [
            {
                "team": team,
                "make_playoffs": entry.make_playoffs,
                "win_division": entry.win_division,
                "win_world_series": entry.win_world_series,
            }
            for team, entry in sorted(odds.items())
        ],
    }
    (data_dir / "playoff_odds.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return PlayoffOddsFetchResult(ok=True, count=len(odds), source=source)


def load_playoff_odds(data_dir: Path) -> PlayoffOddsByTeam:
    """Load optional normalized playoff odds from data_dir/playoff_odds.json.

    The file is written by fetch_playoff_odds (FanGraphs primary, Baseball-Reference fallback).
    If it is absent or unreadable, render proceeds without odds and enrichment falls back to
    standings/rivalry signals.
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


def parse_fangraphs_playoff_odds(payload: Any) -> PlayoffOddsByTeam:
    rows = payload
    if isinstance(payload, dict):
        for key in ("data", "teams", "odds"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
    if not isinstance(rows, list):
        raise ValueError("FanGraphs playoff-odds payload is not a row list")

    out: PlayoffOddsByTeam = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        team = _team_key(_value(row, _FG_FIELD["team"], "Team", "teamName", "team_name", "name"))
        if team is None:
            continue
        out[team] = TeamPlayoffOdds(
            team=team,
            make_playoffs=_prob(
                _value(row, _FG_FIELD["make_playoffs"], "makePlayoffs", "PlayoffPct")
            ),
            win_division=_prob(
                _value(row, _FG_FIELD["win_division"], "winDivision", "WinDivision")
            ),
            win_world_series=_prob(
                _value(row, _FG_FIELD["win_world_series"], "winWS", "WinWorldSeries")
            ),
        )
    if not out:
        raise ValueError("FanGraphs playoff-odds payload had no usable team rows")
    return out


def parse_baseball_reference_playoff_odds(html: str) -> PlayoffOddsByTeam:
    tables = _parse_html_tables(html)
    out: PlayoffOddsByTeam = {}
    for table in tables:
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        if not _looks_like_bref_odds_table(headers):
            continue
        for row in rows:
            team = _team_key(_row_value(row, _BR_FIELD["team"], "Tm", "team_ID", "team_name"))
            if team is None:
                continue
            make_playoffs = _prob(
                _row_value(row, _BR_FIELD["make_playoffs"], "Playoffs", "playoffs")
            )
            wild_card = _prob(_row_value(row, "Wild Card", "Wild Card 1", "Wild Card 2"))
            if make_playoffs is None and wild_card is not None:
                division = _prob(_row_value(row, _BR_FIELD["win_division"], "Division"))
                make_playoffs = min(1.0, (division or 0.0) + wild_card)
            out[team] = TeamPlayoffOdds(
                team=team,
                make_playoffs=make_playoffs,
                win_division=_prob(_row_value(row, _BR_FIELD["win_division"], "Division")),
                win_world_series=_prob(_row_value(row, _BR_FIELD["win_world_series"], "Win WS")),
            )
    if not out:
        raise ValueError("Baseball-Reference playoff-odds HTML had no usable team rows")
    return out


def _team_name(entry: Any) -> str:
    if isinstance(entry, dict):
        value = entry.get("team")
        if isinstance(value, str):
            return value
    return ""


def _fetch_from_sources(clock: Clock, *, client: httpx.Client) -> tuple[str, PlayoffOddsByTeam]:
    try:
        res = client.get(
            _fangraphs_url(clock.now().year),
            headers={
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.fangraphs.com/standings/playoff-odds/fg/div",
                "User-Agent": BROWSER_UA,
            },
        )
        res.raise_for_status()
        return "fangraphs", parse_fangraphs_playoff_odds(res.json())
    except (httpx.HTTPError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        pass

    res = client.get(
        BASEBALL_REFERENCE_URL.format(season=clock.now().year),
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": BROWSER_UA,
        },
    )
    res.raise_for_status()
    return "baseball-reference", parse_baseball_reference_playoff_odds(res.text)


def _fangraphs_url(season: int) -> str:
    params = {
        "projmode": "combo",
        "standingsType": "div",
        "season": str(season),
        "dateDelta": "",
    }
    return f"{FANGRAPHS_URL}?{urlencode(params)}"


def _team_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    mapped = _FULL_NAME_TO_TEAM.get(cleaned.lower())
    if mapped:
        return mapped
    normalized = normalize_team(cleaned)
    if normalized in _FULL_NAME_TO_TEAM.values():
        return normalized
    return None


def _value(row: dict[str, Any], *keys: str) -> Any:
    lowered = {key.lower(): value for key, value in row.items()}
    for key in keys:
        if key in row:
            return row[key]
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return None


def _row_value(row: dict[str, str], *labels: str) -> str | None:
    lowered = {key.lower(): value for key, value in row.items()}
    for label in labels:
        value = row.get(label) or lowered.get(label.lower())
        if value not in (None, ""):
            return value
    return None


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


def _looks_like_bref_odds_table(headers: list[str]) -> bool:
    normalized = {header.lower() for header in headers}
    has_team = bool(normalized & {"team", "tm", "team_id", "team_name"})
    has_division = bool(normalized & {"division winner", "division"})
    has_playoffs = bool(normalized & {"make playoffs", "playoffs", "wild card"})
    has_world_series = bool(normalized & {"world series", "win ws"})
    return has_team and has_division and has_playoffs and has_world_series


def _parse_html_tables(html: str) -> list[dict[str, Any]]:
    parser = _OddsTableParser()
    parser.feed(html)
    for comment in parser.comments:
        if "<table" in comment:
            parser.feed(comment)
    return parser.tables


class _OddsTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, Any]] = []
        self.comments: list[str] = []
        self._in_table = False
        self._headers: list[str] = []
        self._rows: list[dict[str, str]] = []
        self._row_cells: list[tuple[str | None, str]] = []
        self._current_cell: str | None = None
        self._current_stat: str | None = None
        self._buffer: list[str] = []

    def handle_comment(self, data: str) -> None:
        self.comments.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table":
            self._in_table = True
            self._headers = []
            self._rows = []
        elif self._in_table and tag == "tr":
            self._row_cells = []
        elif self._in_table and tag in {"th", "td"}:
            self._current_cell = tag
            self._current_stat = attrs_dict.get("data-stat")
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._in_table and tag in {"th", "td"} and self._current_cell == tag:
            text = " ".join("".join(self._buffer).split())
            self._row_cells.append((self._current_stat, text))
            self._current_cell = None
            self._current_stat = None
            self._buffer = []
        elif self._in_table and tag == "tr":
            values = [text for _, text in self._row_cells if text]
            if values:
                if not self._headers or self._is_header_row(values):
                    self._headers = values
                else:
                    row = self._row_dict(values)
                    if row:
                        self._rows.append(row)
            self._row_cells = []
        elif tag == "table" and self._in_table:
            self.tables.append({"headers": self._headers, "rows": self._rows})
            self._in_table = False

    def _is_header_row(self, values: list[str]) -> bool:
        normalized = {value.lower() for value in values}
        return bool(normalized & {"team", "tm"}) and bool(
            normalized & {"world series", "win ws", "division winner"}
        )

    def _row_dict(self, values: list[str]) -> dict[str, str]:
        row: dict[str, str] = {}
        for header, value in zip(self._headers, values, strict=False):
            row[header] = value
        for data_stat, value in self._row_cells:
            if data_stat:
                row[data_stat] = value
        return row
