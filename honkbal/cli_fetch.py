from __future__ import annotations

import os
import sys
from pathlib import Path

from honkbal.clock import Clock
from honkbal.fetch.espn_postseason import fetch_postseason
from honkbal.fetch.schedule import fetch_schedule
from honkbal.fetch.standings import fetch_standings
from honkbal.season import ConfigError, select_active_season


def cmd_fetch(args, *, clock: Clock) -> int:
    if os.environ.get("HONKBAL_NO_FETCH") == "1":
        print("[skip] HONKBAL_NO_FETCH=1 — fetch overgeslagen, bestaande cache behouden")
        return 0

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        season = select_active_season(clock)
    except ConfigError as exc:
        print(f"[FOUT] config-validatie mislukt: {exc}", file=sys.stderr)
        return 2

    res = fetch_schedule(clock, data_dir=data_dir)
    if not res.ok:
        print(
            f"[waarschuwing] schedule-fetch onder drempel (count={res.success_count}); "
            "last-known-good behouden",
            file=sys.stderr,
        )

    if clock.now() < season.windows.ps:
        standings = fetch_standings(clock, data_dir=data_dir)
        if not standings.ok:
            print(
                "[waarschuwing] standings-fetch mislukt; enrichment gebruikt bestaande cache "
                "of valt terug op basisregels",
                file=sys.stderr,
            )
    else:
        print("[info] postseason — standings-fetch voor enrichment overgeslagen")

    if clock.now() >= season.windows.ps:
        ps = fetch_postseason(clock, data_dir=data_dir)
        if not ps.ok:
            print(
                "[waarschuwing] ESPN-postseason-fetch mislukt; date-derived labels gebruikt",
                file=sys.stderr,
            )
    else:
        print("[info] vóór postseason — ESPN-postseason-fetch overgeslagen")

    return 0
