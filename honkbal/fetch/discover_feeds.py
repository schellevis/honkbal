from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Callable, Iterable

from honkbal.config.teams import EXTRA, MLB_TEAMS, normalize_team
from honkbal.parse.schedule import parse_subject

FeedClassification = tuple[str | None, str]

_ALLSTAR = frozenset(EXTRA)


def _rows(csv_bytes: bytes) -> list[list[str]]:
    text = csv_bytes.decode("utf-8", errors="replace")
    return [r for r in csv.reader(io.StringIO(text)) if r and r[0] != "START DATE"]


def classify_feed(csv_bytes: bytes) -> FeedClassification:
    rows = _rows(csv_bytes)
    if not rows:
        return (None, "empty")

    home_counts: Counter[str] = Counter()
    saw_mlb = saw_allstar = False
    for row in rows:
        if len(row) < 4:
            continue
        parsed = parse_subject(row[3].replace(" - Time TBD", ""))
        if parsed is None:
            continue
        away, home = (normalize_team(parsed[0]), normalize_team(parsed[1]))
        for side in (away, home):
            if side in MLB_TEAMS:
                saw_mlb = True
            if side in _ALLSTAR:
                saw_allstar = True
        if home in MLB_TEAMS:
            home_counts[home] += 1
        elif home in _ALLSTAR:
            home_counts[home] += 1

    if home_counts:
        top = home_counts.most_common(1)[0][0]
        if top in MLB_TEAMS:
            return (top, "mlb")
        if top in _ALLSTAR:
            return (top, "allstar")
    if saw_allstar:
        return ("nl all-stars", "allstar")
    if saw_mlb:
        # MLB-team komt voor maar nooit als home in deze feed -> behandel als affiliate-ruis.
        return (None, "affiliate")
    return (None, "affiliate")


def discover(
    fetch_one: Callable[[int], bytes],
    team_ids: Iterable[int] = range(105, 162),
) -> dict:
    team_feeds: dict[str, int] = {}
    allstar_feed_id: int | None = None
    affiliate: list[int] = []
    empty: list[int] = []

    for tid in sorted(team_ids):
        name, kind = classify_feed(fetch_one(tid))
        if kind == "mlb" and name is not None:
            if name not in team_feeds:  # laagste id wint (deterministisch)
                team_feeds[name] = tid
        elif kind == "allstar":
            if allstar_feed_id is None:
                allstar_feed_id = tid
        elif kind == "empty":
            empty.append(tid)
        else:
            affiliate.append(tid)

    return {
        "team_feeds": team_feeds,
        "allstar_feed_id": allstar_feed_id,
        "affiliate": affiliate,
        "empty": empty,
    }


def render_feeds_module(result: dict) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "# Gegenereerd door discover_feeds.discover.",
    ]
    lines.append("TEAM_FEEDS: dict[str, int] = {")
    for name, tid in sorted(result["team_feeds"].items()):
        lines.append(f"    {name!r}: {tid},")
    lines.append("}")
    lines.append(f"ALLSTAR_FEED_ID: int = {result['allstar_feed_id']}")
    return "\n".join(lines) + "\n"
