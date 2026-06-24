from __future__ import annotations

from datetime import date, datetime, time

from honkbal.clock import AMSTERDAM, Clock
from honkbal.config.calendar_nl import MONTHS, WEEKDAYS
from honkbal.config.teams import TEAMS_AL, normalize_team
from honkbal.config.toggles import COUNTDOWN_FROM
from honkbal.models import Game, PostseasonData
from honkbal.season import ActiveSeason


def _to_dt(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=AMSTERDAM)


def date_header_prefix(d: date, *, clock: Clock) -> str:
    today = clock.now().date()
    if d == today:
        return "vandaag"
    if (d - today).days == 1:
        return "morgen"
    return WEEKDAYS[d.isoweekday()]


def date_header_label(d: date, *, clock: Clock) -> str:
    return f"{date_header_prefix(d, clock=clock)}, {d.day} {MONTHS[d.month]}"


def special_label(
    date_et: date,
    date_ams: date,
    *,
    season: ActiveSeason,
    is_uitzondering: bool,
) -> tuple[str, str] | None:
    w = season.windows
    if date_et < w.reg.date() and not is_uitzondering:
        return ("spring training", "badge")
    if date_et >= w.new.date() and _to_dt(date_ams) > w.ps:
        return (str(season.next_year), "plain")
    if date_et == w.reg.date():
        return ("opening day", "badge")
    if w.allstargame is not None and date_et == w.allstargame.date():
        return ("all-star game", "badge")
    return None


def league_short(away: str, home: str) -> str:
    al = frozenset(TEAMS_AL)
    if normalize_team(away) in al or normalize_team(home) in al:
        return "AL"
    return "NL"


def date_derived_phase(date_et: date, away: str, home: str, *, season: ActiveSeason) -> str | None:
    w = season.windows
    short = league_short(away, home)
    if w.ws > w.ps and date_et >= w.ws.date():
        return "World Series"
    if w.cs > w.ps and date_et >= w.cs.date():
        return f"{short}CS"
    if w.ds >= w.ps and date_et >= w.ds.date():
        return f"{short}DS"
    if w.wc >= w.ps and date_et >= w.wc.date():
        return f"{short} Wild Card"
    return None


def postseason_label(
    game: Game,
    *,
    season: ActiveSeason,
    postseason: PostseasonData | None,
) -> tuple[str | None, str | None]:
    w = season.windows
    if not (w.ps.date() <= game.date_et < w.new.date()):
        return (None, None)

    if postseason is not None and game.hour_ams is not None:
        gh, gaw = normalize_team(game.home), normalize_team(game.away)
        for (d, h, _home), pg in postseason.games.items():
            if d == game.date_ams and h == game.hour_ams:
                if normalize_team(pg.home) == gh and normalize_team(pg.away) == gaw:
                    # SPEC §5.6: toon de serie-stand (al geformatteerd als "(x-y)" door
                    # parse_series_standing), NIET pg.record (= ESPN seizoen-recordSummary).
                    return (pg.descr, pg.standing)

    return (date_derived_phase(game.date_et, game.away, game.home, season=season), None)


def countdown(*, season: ActiveSeason, clock: Clock) -> tuple[str, bool] | None:
    now = clock.now()
    diff = (season.windows.reg.date() - now.date()).days
    if diff == 0:
        return ("Opening day!", True)
    if diff >= 1:
        day, month = COUNTDOWN_FROM
        from_dt = datetime(now.year, month, day, tzinfo=AMSTERDAM)
        if now >= from_dt:
            suffix = "en" if diff > 1 else ""
            return (f"Nog {diff} dag{suffix} tot opening day!", False)
    return None
