from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from honkbal.clock import AMSTERDAM, NEW_YORK, UTC, Clock, SystemClock
from honkbal.config.teams import ALLOWLIST_RENDER, normalize_team
from honkbal.models import Game, ScheduleMeta, sort_games

_ET_TIMED_FORMAT = "%m/%d/%y %I:%M %p"
_DATE_FORMAT = "%m/%d/%y"
_HTTP_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"
_TBD_MARKER = "Time TBD"
# Strip de "- Time TBD"-suffix tolerant: één of twee (of meer) spaties rond het streepje en
# omringende whitespace (SPEC quote toont een dubbele spatie). Gedrag verder identiek.
_TBD_STRIP = re.compile(r"\s*-\s*Time TBD\s*$", re.IGNORECASE)


def parse_subject(subject: str) -> tuple[str, str] | None:
    # Teamnamen bevatten geen " at " -> split op de laatste voorkomst is veilig.
    if " at " not in subject:
        return None
    away, home = subject.rsplit(" at ", 1)
    away, home = away.strip(), home.strip()
    if not away or not home:
        return None
    return away, home


def parse_meta(headers: dict, clock: Clock) -> ScheduleMeta:
    refreshed = clock.now()
    newest: datetime | None = None
    for entry in headers.values():
        if not isinstance(entry, dict):
            continue
        raw = None
        for key, value in entry.items():
            if str(key).lower() == "last-modified":
                raw = value
                break
        if not raw:
            continue
        try:
            m = datetime.strptime(raw, _HTTP_DATE_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            continue
        if newest is None or m > newest:
            newest = m
    modified = newest.astimezone(AMSTERDAM) if newest is not None else refreshed
    return ScheduleMeta(modified=modified, refreshed=refreshed)


def _allowed(away: str, home: str) -> bool:
    return (
        normalize_team(away) in ALLOWLIST_RENDER
        or normalize_team(home) in ALLOWLIST_RENDER
    )


def _dedupe_team_feed_rows(games: list[Game]) -> list[Game]:
    """Collapse exact duplicates from combined team feeds while preserving doubleheaders.

    The schedule fetch concatenates both teams' ticketing feeds, so a normal game appears
    twice with identical schedule fields. Keeping ceil(n/2) exact duplicates restores the
    actual game count while still retaining two identical TBD rows for a TBD doubleheader
    that arrives four times across the two team feeds.

    Aanname: elke echte wedstrijd verschijnt een even aantal keer in de gecombineerde feed
    (normaal 2×, TBD-doubleheader 4×, all-star/eenzijdig 1× of 2×). ceil(n/2) is alleen
    correct onder die pariteitsgarantie. Bij het toevoegen van een derde feed of bij feeds
    die een game een oneven aantal keer > 1 opleveren, levert dit spookduplicaten. Zie
    ook test_dedupe_pariteit_aanname in tests/unit/test_parse_schedule.py.
    """

    def key(game: Game) -> tuple:
        return (
            game.date_ams,
            game.time_ams,
            game.date_et,
            game.away,
            game.home,
            game.is_tbd,
        )

    counts = Counter(key(game) for game in games)
    keep_remaining = {k: (count + 1) // 2 for k, count in counts.items()}
    deduped: list[Game] = []
    for game in games:
        game_key = key(game)
        if keep_remaining[game_key] <= 0:
            continue
        deduped.append(game)
        keep_remaining[game_key] -= 1
    return deduped


def parse_schedule(
    csv_bytes: bytes, headers: dict, clock: Clock
) -> tuple[list[Game], ScheduleMeta]:
    # The `>now` date filter lives in the build layer, not here, so the parser
    # remains a pure bytes→model transform. The clock is retained for parse_meta.
    text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))

    games: list[Game] = []
    seq = -1  # 0-based index van datarijen (header niet meegeteld)
    for row in reader:
        if not row or row[0] == "START DATE":
            continue
        if len(row) < 4:
            continue
        seq += 1
        start_date, et_time, subject = row[0], row[2], row[3]
        parsed = parse_subject(_TBD_STRIP.sub("", subject))
        if parsed is None:
            continue
        away, home = parsed
        if not _allowed(away, home):
            continue

        if _TBD_MARKER in subject:
            try:
                et_dt = datetime.strptime(start_date, _DATE_FORMAT).replace(tzinfo=NEW_YORK)
            except ValueError:
                continue
            # TBD heeft geen tijd: date_et == date_ams (NY-kalenderdatum), geen verschuiving.
            games.append(
                Game(
                    date_ams=et_dt.date(),
                    time_ams=None,
                    hour_ams=None,
                    date_et=et_dt.date(),
                    away=away,
                    home=home,
                    is_tbd=True,
                    source_seq=seq,
                )
            )
            continue

        if not et_time:
            continue
        try:
            et_dt = datetime.strptime(f"{start_date} {et_time}", _ET_TIMED_FORMAT).replace(
                tzinfo=NEW_YORK
            )
        except ValueError:
            continue
        ams = et_dt.astimezone(AMSTERDAM)
        games.append(
            Game(
                date_ams=ams.date(),
                time_ams=ams.time().replace(second=0, microsecond=0),
                hour_ams=ams.hour,
                date_et=et_dt.date(),
                away=away,
                home=home,
                is_tbd=False,
                source_seq=seq,
            )
        )

    return sort_games(_dedupe_team_feed_rows(games)), parse_meta(headers, clock)


def load_games(
    data_dir: Path, clock: Clock | None = None
) -> tuple[list[Game], ScheduleMeta] | None:
    """Load cached schedule from data_dir. Returns None if no cache present.

    Pass a Clock to override the default SystemClock (useful for reproducible builds
    and tests: the injected clock is used for ScheduleMeta.refreshed).
    """
    csv_path = Path(data_dir) / "all.csv"
    headers_path = Path(data_dir) / "headers.json"
    if not csv_path.exists() or not headers_path.exists():
        return None
    return parse_schedule(
        csv_path.read_bytes(),
        json.loads(headers_path.read_text(encoding="utf-8")),
        clock if clock is not None else SystemClock(),
    )
