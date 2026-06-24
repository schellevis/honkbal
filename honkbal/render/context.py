from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from markupsafe import Markup

import honkbal.render.labels as _labels
from honkbal.clock import Clock
from honkbal.config.teams import normalize_team
from honkbal.models import Game, PostseasonData
from honkbal.render.filters import should_render, uitzondering_code
from honkbal.render.labels import date_header_label, postseason_label, special_label
from honkbal.render.logos import display_name, logo_html
from honkbal.season import ActiveSeason


@dataclass(frozen=True)
class RowContext:
    away_slug: str
    home_slug: str
    time_label: str
    away_logo: Markup
    home_logo: Markup
    away_name: str
    home_name: str
    postseason_descr: str | None
    postseason_record: str | None
    is_postseason_row: bool


@dataclass(frozen=True)
class DayBlock:
    header_label: str
    special: tuple[str, str] | None
    date_ams: date
    rows: list[RowContext] = field(default_factory=list)


@dataclass(frozen=True)
class PageContext:
    page: str
    default_tab: str
    countdown: tuple[str, bool] | None
    days: list[DayBlock]
    total_rows: int
    has_postseason_footnote: bool
    is_empty: bool


def default_tab(*, season: ActiveSeason, clock: Clock) -> str:
    now = clock.now()
    if now >= season.windows.ps or now >= season.windows.einde:
        return "alles"
    return "avond"


def build_page_context(
    games: list[Game],
    *,
    page: str,
    team_slug_q: str | None,
    season: ActiveSeason,
    postseason: PostseasonData | None,
    clock: Clock,
    img_dir: Path,
    asset_version: str,
) -> PageContext:
    filtered = [
        g for g in games
        if should_render(g, page=page, team_slug_q=team_slug_q, season=season)
    ]

    days: list[DayBlock] = []
    has_ps_footnote = False
    w = season.windows

    for day_date, day_games in itertools.groupby(filtered, key=lambda g: g.date_ams):
        day_list = list(day_games)
        first = day_list[0]
        uf = uitzondering_code(first)
        is_uitz = uf in w.uitzondering
        header = date_header_label(day_date, clock=clock)
        special = special_label(
            first.date_et, first.date_ams, season=season, is_uitzondering=is_uitz
        )

        rows: list[RowContext] = []
        for g in day_list:
            time_label = g.time_ams.strftime("%H:%M") if g.time_ams is not None else "TBD"

            away_logo = logo_html(g.away, img_dir=img_dir, asset_version=asset_version)
            home_logo = logo_html(g.home, img_dir=img_dir, asset_version=asset_version)
            away_nm = display_name(g.away)
            home_nm = display_name(g.home)

            # postseason_label retourneert de serie-stand al geformatteerd ("(x-y)") of None.
            ps_descr, ps_standing = postseason_label(g, season=season, postseason=postseason)
            is_ps_row = w.ps.date() <= g.date_et < w.new.date()

            if ps_descr is not None and "*" in ps_descr:
                has_ps_footnote = True

            rows.append(RowContext(
                away_slug=normalize_team(g.away),
                home_slug=normalize_team(g.home),
                time_label=time_label,
                away_logo=away_logo,
                home_logo=home_logo,
                away_name=away_nm,
                home_name=home_nm,
                postseason_descr=ps_descr,
                postseason_record=ps_standing,
                is_postseason_row=is_ps_row,
            ))

        days.append(DayBlock(
            header_label=header,
            special=special,
            date_ams=day_date,
            rows=rows,
        ))

    total = sum(len(d.rows) for d in days)
    tab = default_tab(season=season, clock=clock)
    ctd = _labels.countdown(season=season, clock=clock)

    return PageContext(
        page=page,
        default_tab=tab,
        countdown=ctd,
        days=days,
        total_rows=total,
        has_postseason_footnote=has_ps_footnote,
        is_empty=(total == 0),
    )
