from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from honkbal.clock import AMSTERDAM, Clock
from honkbal.config.teams import MLB_TEAMS, normalize_team
from honkbal.config.toggles import LIVE_GRACE_HOURS, SLEEP_SECONDS, TV_GUIDE_DAYS
from honkbal.fetch.http import Throttle, build_client
from honkbal.fetch.standings import _FULL_NAME_TO_TEAM

# ESPN watch GraphQL-API achter de espn.nl-speelkalender, live gevalideerd op 2026-08-05:
# kale GET zonder speciale headers werkt. apiKey en categoryId (= MLB) zijn publieke
# client-side constanten uit de espn.nl-paginabundel — geen secrets, maar ze kunnen roteren.
# Hervalideer ze (pagina laden, netwerkverkeer bekijken) zodra de fetch structureel faalt.
ESPN_WATCH_URL = "https://watch.graph.api.espn.com/api"
ESPN_WATCH_API_KEY = "0dbf88e8-cc6d-41da-aa83-18b5c630bc5c"
ESPN_MLB_CATEGORY_ID = "b38f959b-7865-31ac-8841-b88355519e10"
_ESPN_AIRINGS_QUERY = (
    "query Airings($countryCode:String!,$deviceType:DeviceType!,$tz:String!,"
    "$type:AiringType,$categories:[String],$day:String,$limit:Int){"
    "airings(countryCode:$countryCode,deviceType:$deviceType,tz:$tz,"
    "type:$type,categories:$categories,day:$day,limit:$limit){"
    "id name type startDateTime endDateTime feedName "
    "network{abbreviation name} subcategory{name}}}"
)

# tvgids.nl JSON-API (fallback), live gevalideerd op 2026-08-05. Kanaal-id's zijn hardcoded;
# ESPN Extra bestaat niet in tvgids. Met `channels`-param is `data` een dict per kanaal-id.
TVGIDS_PROGRAMS_URL = "https://json.tvgids.nl/v4/programs/"
_TVGIDS_CHANNELS = {"148": "espn", "468": "espn2", "469": "espn3", "470": "espn4"}

_ESPN_NETWORKS = {
    "nl_espn": "espn",
    "nl_espn1": "espn",
    "nl_espn2": "espn2",
    "nl_espn3": "espn3",
    "nl_espn4": "espn4",
    "nl_espn_extra": "espn_extra",
}

# NL-commentaar staat op allerlei manieren in titel/feedName; een kale "nl" in de titel is
# bewust géén match ("NL All-Stars", "NL East"). feedName die als geheel "nl" is telt wel.
_NL_COMMENTARY = re.compile(
    r"\(\s*nl\s*\)|nederlands(?:talig)?\s*commentaar|\bnl[- ]commentaar\b|\bnederlands\b",
    re.IGNORECASE,
)

_TITLE_PREFIX = re.compile(r"^\s*mlb\s*[:.]\s*", re.IGNORECASE)
_PARENTHETICAL = re.compile(r"\([^)]*\)")
_TEAM_SEPARATOR = re.compile(r"\s+vs\.?\s+|\s+-\s+|\s+@\s+", re.IGNORECASE)
_GAME_SUFFIX = re.compile(r"\bgame\s*\d+\b.*$", re.IGNORECASE)
_MLB_TITLE = re.compile(r"\bmlb\b|major league baseball", re.IGNORECASE)

# Magazineprogramma's ("MLB Quick Pitch", "MLB Plays of the Week") zijn geen wedstrijden;
# zonder dit filter zou de teamloze tijdpass van de matcher ze aan een game kunnen koppelen.
# Een titel telt als wedstrijd bij een teamscheider ("X vs Y", "X - Y"), een postseason-/
# all-star-aanduiding of de generieke tvgids-titel "Major League Baseball".
_EVENT_HINT = re.compile(
    r"wild card|division series|championship series|world series|postseason|"
    r"\b(?:al|nl)(?:ds|cs)\b|all[- ]star",
    re.IGNORECASE,
)
_GENERIC_GAME = re.compile(r"^\s*major league baseball\b[\s\d]*$", re.IGNORECASE)

# Carry-over-dedup: een oude en nieuwe airing op hetzelfde kanaal met starts binnen deze marge
# zijn dezelfde uitzending.
_DUPLICATE_START_TOLERANCE = timedelta(minutes=5)


class TvGuideFetchResult:
    def __init__(self, *, ok: bool, count: int, source: str | None = None):
        self.ok = ok
        self.count = count
        self.source = source


def fetch_tv_guide(
    clock: Clock,
    *,
    data_dir: Path,
    client: httpx.Client | None = None,
    throttle: Throttle | None = None,
) -> TvGuideFetchResult:
    own_client = client is None
    client = client or build_client()
    throttle = throttle or Throttle(SLEEP_SECONDS, clock)
    try:
        source, airings = _fetch_from_sources(clock, client=client, throttle=throttle)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return TvGuideFetchResult(ok=False, count=0)
    finally:
        if own_client:
            client.close()

    # ESPN geeft alleen UPCOMING terug; behoud lopende uitzendingen uit de vorige cache zodat
    # een game die nog in zijn grace-window zit zijn logo niet verliest bij een build midden
    # in de wedstrijd.
    airings = _carry_over_running(airings, data_dir=data_dir, now=clock.now())
    airings = _dedupe(airings)
    airings.sort(key=lambda a: (a["start"], a["channel"]))

    payload = {
        "fetched_at": clock.now().isoformat(),
        "season": clock.now().year,
        "source": source,
        "airings": airings,
    }
    if not _write_cache(data_dir, payload):
        return TvGuideFetchResult(ok=False, count=0)
    return TvGuideFetchResult(ok=True, count=len(airings), source=source)


def _write_cache(data_dir: Path, payload: dict[str, Any]) -> bool:
    """Schrijf atomair; een I/O-fout laat de last-known-good cache intact."""
    path = data_dir / "tv_guide.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def _fetch_from_sources(
    clock: Clock, *, client: httpx.Client, throttle: Throttle
) -> tuple[str, list[dict[str, Any]]]:
    try:
        return "espn", _fetch_espn(clock, client=client, throttle=throttle)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        pass
    return "tvgids", _fetch_tvgids(clock, client=client, throttle=throttle)


def _fetch_espn(clock: Clock, *, client: httpx.Client, throttle: Throttle) -> list[dict[str, Any]]:
    airings: list[dict[str, Any]] = []
    ok_days = 0
    for i in range(TV_GUIDE_DAYS):
        if i:
            throttle.wait()
        day = clock.now() + timedelta(days=i)
        try:
            res = client.get(
                ESPN_WATCH_URL,
                params={
                    "apiKey": ESPN_WATCH_API_KEY,
                    "query": _ESPN_AIRINGS_QUERY,
                    "variables": json.dumps(
                        {
                            "countryCode": "NL",
                            "deviceType": "DESKTOP",
                            "tz": _tz_param(day),
                            "type": "UPCOMING",
                            "categories": [ESPN_MLB_CATEGORY_ID],
                            "day": day.date().isoformat(),
                            "limit": 1000,
                        }
                    ),
                },
            )
            res.raise_for_status()
            rows = res.json()["data"]["airings"]
            if not isinstance(rows, list):
                raise ValueError("ESPN airings-payload is geen lijst")
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            continue
        ok_days += 1
        for row in rows:
            airing = _airing_from_espn(row)
            if airing is not None:
                airings.append(airing)
    if ok_days == 0:
        raise ValueError("alle ESPN-dagcalls mislukt")
    # Een dag zonder MLB-uitzendingen is legitiem; geslaagde dagen met nul airings tellen dus
    # als succes en overschrijven de cache (anders blijven spooklogo's staan).
    return airings


def _airing_from_espn(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    network = row.get("network") or {}
    if not isinstance(network, dict):
        return None
    channel = _ESPN_NETWORKS.get(str(network.get("abbreviation") or "").strip().lower())
    start = _utc_to_ams(row.get("startDateTime"))
    if channel is None or start is None:
        return None
    end = _utc_to_ams(row.get("endDateTime"))
    title = str(row.get("name") or "")
    if not _looks_like_game(title):
        return None
    feed = str(row.get("feedName") or "")
    return {
        "channel": channel,
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "teams": _parse_teams(title),
        "nl_commentary": _detect_nl_commentary(title, feed),
        "live": str(row.get("type") or "").upper() in {"UPCOMING", "LIVE"},
        "title": title,
    }


def _fetch_tvgids(
    clock: Clock, *, client: httpx.Client, throttle: Throttle
) -> list[dict[str, Any]]:
    airings: list[dict[str, Any]] = []
    ok_days = 0
    for i in range(TV_GUIDE_DAYS):
        if i:
            throttle.wait()
        try:
            res = client.get(
                TVGIDS_PROGRAMS_URL,
                params={"day": i, "channels": ",".join(_TVGIDS_CHANNELS)},
            )
            res.raise_for_status()
            payload = res.json()
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            continue
        ok_days += 1
        for ch_id, programs in _tvgids_programs(payload):
            channel = _TVGIDS_CHANNELS.get(str(ch_id))
            if channel is None:
                continue
            for program in programs:
                airing = _airing_from_tvgids(program, channel)
                if airing is not None:
                    airings.append(airing)
    if ok_days == 0:
        raise ValueError("alle tvgids-dagcalls mislukt")
    return airings


def _tvgids_programs(payload: Any) -> list[tuple[Any, list[dict[str, Any]]]]:
    # Met `channels`-param is `data` een dict {ch_id: [programma's]}, zonder een lijst waarin
    # elk programma zelf een ch_id draagt. Beide vormen afhandelen.
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        return [(ch_id, programs) for ch_id, programs in data.items() if isinstance(programs, list)]
    if isinstance(data, list):
        return [
            (program.get("ch_id"), [program])
            for program in data
            if isinstance(program, dict) and program.get("ch_id") is not None
        ]
    return []


def _airing_from_tvgids(program: Any, channel: str) -> dict[str, Any] | None:
    if not isinstance(program, dict):
        return None
    title = str(program.get("title") or "")
    if not _MLB_TITLE.search(title) or not _looks_like_game(title):
        return None
    start = _epoch_to_ams(program.get("s"))
    if start is None:
        return None
    end = _epoch_to_ams(program.get("e"))
    return {
        "channel": channel,
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "teams": _parse_teams(title),
        # tvgids kent geen commentaartaal-vlag; detecteer alleen expliciete markeringen in de titel.
        "nl_commentary": _detect_nl_commentary(title, ""),
        "live": program.get("live") in (True, "true"),
        "title": title,
    }


def _carry_over_running(
    airings: list[dict[str, Any]], *, data_dir: Path, now: datetime
) -> list[dict[str, Any]]:
    path = data_dir / "tv_guide.json"
    if not path.exists():
        return airings
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return airings
    previous = payload.get("airings", []) if isinstance(payload, dict) else []
    if not isinstance(previous, list):
        return airings

    window_start = now - timedelta(hours=LIVE_GRACE_HOURS)
    new_starts = [(new["channel"], _parse_iso(new["start"])) for new in airings]
    kept = list(airings)
    for old in previous:
        if not isinstance(old, dict):
            continue
        start = _parse_iso(old.get("start"))
        if start is None or start.tzinfo is None or not (window_start <= start <= now):
            continue
        if any(
            channel == old.get("channel")
            and new_start is not None
            and abs(new_start - start) <= _DUPLICATE_START_TOLERANCE
            for channel, new_start in new_starts
        ):
            continue
        kept.append(old)
    return kept


def _dedupe(airings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for airing in airings:
        key = (airing["channel"], airing["start"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(airing)
    return unique


def _looks_like_game(title: str) -> bool:
    body = _TITLE_PREFIX.sub("", title)
    return bool(
        _TEAM_SEPARATOR.search(body)
        or _EVENT_HINT.search(body)
        or _GENERIC_GAME.match(body)
    )


def _detect_nl_commentary(title: str, feed_name: str) -> bool:
    haystack = f"{title} {feed_name}".lower()
    if _NL_COMMENTARY.search(haystack):
        return True
    return feed_name.strip().lower() == "nl"


def _parse_teams(title: str) -> list[str]:
    body = _TITLE_PREFIX.sub("", title)
    body = _PARENTHETICAL.sub(" ", body)
    # Een commentaarlabel na een streepje is metadata, geen derde teamseparator.
    body = _NL_COMMENTARY.sub(" ", body)
    body = re.sub(r"\s+-\s*$", "", body)
    parts = _TEAM_SEPARATOR.split(body)
    if len(parts) != 2:
        return []
    teams = []
    for part in parts:
        team = _team_key(_GAME_SUFFIX.sub("", part).strip())
        if team is None:
            return []
        teams.append(team)
    if teams[0] == teams[1]:
        return []
    return sorted(teams)


def _team_key(value: str) -> str | None:
    mapped = _FULL_NAME_TO_TEAM.get(value.lower())
    if mapped:
        return mapped
    normalized = normalize_team(value)
    if normalized in MLB_TEAMS:
        return normalized
    return None


def _tz_param(moment: datetime) -> str:
    offset = moment.utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"UTC{sign}{total // 3600:02d}{(total % 3600) // 60:02d}"


def _utc_to_ams(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(AMSTERDAM)
    except ValueError:
        return None


def _epoch_to_ams(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=AMSTERDAM)
    except (TypeError, ValueError, OSError):
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
