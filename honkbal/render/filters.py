from __future__ import annotations

from datetime import date, datetime, time

from honkbal.clock import AMSTERDAM
from honkbal.config.teams import ALLOWLIST_RENDER, normalize_team, team_slug
from honkbal.models import Game
from honkbal.season import ActiveSeason

_AVOND = frozenset(range(14, 24))
_OCHTEND = frozenset(range(3, 7))  # 3..6 (legacy site.php:152-153: skip tm>=7 of tm<=2)
_NACHT = frozenset({23, 0, 1, 2, 3})


def passes_time_filter(page: str, hour_ams: int | None) -> bool:
    if page in ("alles", "team"):
        return True
    if hour_ams is None:
        return False
    if page == "avond":
        return hour_ams in _AVOND
    if page == "ochtend":
        return hour_ams in _OCHTEND
    if page == "nacht":
        return hour_ams in _NACHT
    return True


def to_dt(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=AMSTERDAM)


def uitzondering_code(game: Game) -> str:
    return f"{game.date_ams.strftime('%d%m')}{game.away}{game.home}"


def should_render(
    game: Game,
    *,
    page: str,
    team_slug_q: str | None,
    season: ActiveSeason,
) -> bool:
    w = season.windows
    is_team_page = page == "team"

    if not passes_time_filter(page, game.hour_ams):
        return False

    if not is_team_page and to_dt(game.date_ams) >= w.hide:
        return False

    if (
        w.newreg is not None
        and to_dt(game.date_ams) > w.new
        and to_dt(game.date_et) < w.newreg
        and uitzondering_code(game) not in season.next_uitzondering
    ):
        return False

    if is_team_page and team_slug_q is not None:
        if team_slug(game.away) != team_slug_q and team_slug(game.home) != team_slug_q:
            return False

    if game.is_tbd and page != "alles" and not is_team_page:
        return False

    if (
        normalize_team(game.away) not in ALLOWLIST_RENDER
        and normalize_team(game.home) not in ALLOWLIST_RENDER
    ):
        return False

    uf = uitzondering_code(game)
    if not (
        to_dt(game.date_ams) >= w.showfrom
        or uf in w.uitzondering
        or uf in season.next_uitzondering
    ):
        return False

    return True
