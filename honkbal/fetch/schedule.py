from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx

from honkbal.clock import NEW_YORK, Clock
from honkbal.config.feeds import ALLSTAR_FEED_ID, TEAM_FEEDS
from honkbal.config.toggles import SLEEP_SECONDS
from honkbal.fetch.http import Throttle

TICKETING_URL = (
    "https://www.ticketing-client.com/ticketing-client/csv/GameTicketPromotionPrice.tiksrv"
)
MIN_SUCCESS = 24  # SPEC §3.2 last-known-good drempel (24 van 31 feeds), zie Fase-2-besluit #4
REQUIRED_COLUMNS = {"START DATE", "START TIME ET", "SUBJECT"}


@dataclass(frozen=True)
class FetchResult:
    csv_bytes: bytes
    headers: dict[str, dict]
    success_count: int
    ok: bool


def feed_params(team_id: int, year: int, begin_date: str) -> dict:
    return {
        "team_id": team_id,
        "display_in": "singlegame",
        "ticket_category": "Tickets",
        "site_section": "Default",
        "sub_category": "Default",
        "leave_empty_games": "true",
        "event_type": "T",
        "year": year,
        "begin_date": begin_date,
    }


def default_feed_ids() -> list[int]:
    ids = list(TEAM_FEEDS.values())
    if ALLSTAR_FEED_ID is not None:
        ids.append(ALLSTAR_FEED_ID)
    return ids


def valid_schedule_csv(csv_bytes: bytes) -> bool:
    text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row:
            continue
        if row[0] != "START DATE":
            continue
        return REQUIRED_COLUMNS.issubset(set(row))
    return False


def fetch_all(
    client: httpx.Client,
    clock: Clock,
    *,
    throttle: Throttle | None = None,
    feed_ids: Iterable[int] | None = None,
) -> FetchResult:
    now = clock.now()
    year = now.year
    begin_date = now.astimezone(NEW_YORK).strftime("%Y%m%d")
    ids = list(feed_ids) if feed_ids is not None else default_feed_ids()

    parts: list[bytes] = []
    headers: dict[str, dict] = {}
    success = 0
    for tid in ids:
        try:
            resp = client.get(TICKETING_URL, params=feed_params(tid, year, begin_date))
        except httpx.HTTPError:
            continue
        finally:
            if throttle is not None:
                throttle.wait()
        if resp.status_code == 200 and resp.content.strip():
            parts.append(resp.content)
            headers[str(tid)] = dict(resp.headers)
            success += 1
    csv_bytes = b"".join(parts)
    return FetchResult(
        csv_bytes=csv_bytes,
        headers=headers,
        success_count=success,
        ok=success >= MIN_SUCCESS and valid_schedule_csv(csv_bytes),
    )


def write_atomic(result: FetchResult, csv_path: Path, headers_path: Path) -> bool:
    if not result.ok or not valid_schedule_csv(result.csv_bytes):
        return False  # last-known-good cache intact (SPEC §3.2 [NEW], §12.12)
    csv_tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    headers_tmp = headers_path.with_suffix(headers_path.suffix + ".tmp")
    csv_tmp.write_bytes(result.csv_bytes)
    headers_tmp.write_text(json.dumps(result.headers))
    os.replace(csv_tmp, csv_path)
    os.replace(headers_tmp, headers_path)
    return True


def fetch_schedule(clock: Clock, *, data_dir: Path) -> FetchResult:
    """Fetch schedule from MLB feeds, write atomically to data_dir. Returns FetchResult."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30) as client:
        result = fetch_all(client, clock, throttle=Throttle(SLEEP_SECONDS, clock))
    write_atomic(result, data_dir / "all.csv", data_dir / "headers.json")
    return result
