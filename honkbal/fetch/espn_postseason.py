from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx

from honkbal.clock import AMSTERDAM, UTC, Clock
from honkbal.config.teams import TEAM_ABBR
from honkbal.config.toggles import ESPNCAP, SLEEP_SECONDS
from honkbal.fetch.http import Throttle
from honkbal.models import PostseasonData, PostseasonGame
from honkbal.parse.espn_postseason import parse_postseason

SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams/{abbr}/schedule"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary"
_ESPN_DATE = "%Y-%m-%dT%H:%MZ"


def cache_is_fresh(parsed_at_epoch: float | None, clock: Clock, espncap: int = ESPNCAP) -> bool:
    if parsed_at_epoch is None:
        return False
    return (clock.now().timestamp() - parsed_at_epoch) < espncap


def fetch_team_schedules(
    client: httpx.Client, *, abbrs=TEAM_ABBR, throttle: Throttle | None = None
) -> list[dict]:
    out: list[dict] = []
    for abbr in abbrs:
        try:
            resp = client.get(SCHEDULE_URL.format(abbr=abbr))
        except httpx.HTTPError:
            continue
        finally:
            if throttle is not None:
                throttle.wait()
        if resp.status_code == 200 and resp.content.strip():
            out.append(resp.json())
    return out


def fetch_summaries(
    client: httpx.Client,
    schedule_json: list,
    clock: Clock,
    cache_dir: Path,
    *,
    throttle: Throttle | None = None,
) -> dict[str, dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    now = clock.now()
    summaries: dict[str, dict] = {}
    for team in schedule_json:
        for event in team.get("events", []) or []:
            event_id = str(event.get("id"))
            cache_file = cache_dir / f"{event_id}.json"
            if cache_file.exists():
                summaries[event_id] = json.loads(cache_file.read_text())
                continue
            # Alleen toekomstige events ophalen (legacy: dateTime > time).
            future = False
            for comp in event.get("competitions", []) or []:
                if not isinstance(comp, dict):
                    continue
                raw_date = comp.get("date")
                if not raw_date:
                    continue  # malformed -> overslaan (SPEC §9)
                try:
                    dt = datetime.strptime(raw_date, _ESPN_DATE).replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    continue
                if dt.astimezone(AMSTERDAM) > now:
                    future = True
            if not future:
                continue
            try:
                resp = client.get(SUMMARY_URL, params={"event": event_id})
            except httpx.HTTPError:
                continue
            finally:
                if throttle is not None:
                    throttle.wait()
            if resp.status_code == 200 and resp.content.strip():
                cache_file.write_text(resp.text)
                summaries[event_id] = resp.json()
    return summaries


def refresh_postseason(
    client: httpx.Client,
    clock: Clock,
    cache_dir: Path,
    parsed_at_epoch: float | None = None,
    *,
    throttle: Throttle | None = None,
) -> PostseasonData | None:
    if cache_is_fresh(parsed_at_epoch, clock):
        return None  # "te recent nog gedaan" — geen werk (SPEC §3.5)
    schedules = fetch_team_schedules(client, throttle=throttle)
    summaries = fetch_summaries(client, schedules, clock, cache_dir, throttle=throttle)
    return parse_postseason(schedules, summaries, clock)


@dataclass(frozen=True)
class PostseasonFetchResult:
    ok: bool
    count: int


def _serialize_postseason(ps: PostseasonData) -> dict:
    games_list = []
    for (d, hour, home), game in ps.games.items():
        entry = game.model_dump()
        entry["_date"] = d.isoformat()
        entry["_hour"] = hour
        entry["_home"] = home
        games_list.append(entry)
    return {
        "fetched_at": ps.fetched_at.isoformat(),
        "teams": ps.teams,
        "games_list": games_list,
    }


def _deserialize_postseason(data: dict) -> PostseasonData:
    fetched_at = datetime.fromisoformat(data["fetched_at"])
    teams = data["teams"]
    games: dict[tuple[date, int, str], PostseasonGame] = {}
    for entry in data.get("games_list", []):
        d = date.fromisoformat(entry.pop("_date"))
        hour = entry.pop("_hour")
        home = entry.pop("_home")
        games[(d, hour, home)] = PostseasonGame(**entry)
    return PostseasonData(fetched_at=fetched_at, teams=teams, games=games)


def fetch_postseason(clock: Clock, *, data_dir: Path) -> PostseasonFetchResult:
    """Fetch ESPN postseason data, write to data_dir/postseason.json. Returns result."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = data_dir / "espnapi"
    ps_path = data_dir / "postseason.json"

    parsed_at_epoch: float | None = None
    if ps_path.exists():
        try:
            existing = json.loads(ps_path.read_text(encoding="utf-8"))
            parsed_at_epoch = datetime.fromisoformat(existing["fetched_at"]).timestamp()
        except Exception:
            pass

    # Een fout tijdens fetch/parse mag de build niet laten crashen: zet ok=False zodat
    # cli_fetch de waarschuwing toont en op date-derived labels terugvalt (SPEC §9/§3.5).
    try:
        with httpx.Client(timeout=30) as client:
            result = refresh_postseason(
                client,
                clock,
                cache_dir,
                parsed_at_epoch,
                throttle=Throttle(SLEEP_SECONDS, clock),
            )
    except Exception:
        return PostseasonFetchResult(ok=False, count=0)

    if result is not None:
        try:
            ps_path.write_text(
                json.dumps(_serialize_postseason(result), ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            return PostseasonFetchResult(ok=False, count=0)
        return PostseasonFetchResult(ok=True, count=len(result.games))
    # Cache was fresh — no update needed, existing file is still valid
    return PostseasonFetchResult(ok=True, count=0)


def load_postseason(data_dir: Path) -> PostseasonData | None:
    """Load cached postseason data from data_dir. Returns None if no cache present."""
    ps_path = Path(data_dir) / "postseason.json"
    if not ps_path.exists():
        return None
    try:
        data = json.loads(ps_path.read_text(encoding="utf-8"))
        return _deserialize_postseason(data)
    except Exception:
        return None
