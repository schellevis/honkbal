"""Integratie: parse_postseason() -> build_page_context() toont de geparsede serie-stand.

Regressiewaarborg voor de bug waarbij de renderlaag pg.record (ESPN seizoen-recordSummary)
toonde i.p.v. pg.standing (de serie-stand "(x-y)") — SPEC §3.5/§5.6.
"""
from datetime import date, datetime, time
from json import load
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Game
from honkbal.parse.espn_postseason import parse_postseason
from honkbal.render.context import build_page_context
from honkbal.season import select_active_season

FIX = Path(__file__).parent.parent / "fixtures" / "espn"


def _load(name):
    with open(FIX / name) as f:
        return load(f)


def test_parsed_series_standing_reaches_rendered_row(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 15, 12, tzinfo=AMSTERDAM))
    season = select_active_season(clock)

    # Echte parser-output: standing "(1-0)" (Tigers leiden), record (recordSummary) is iets anders.
    pd = parse_postseason(
        _load("schedule_two_teams.json"),
        {"401809252": _load("summary_det_leads.json")},
        clock,
    )
    assert pd.games[(date(2026, 10, 1), 19, "Guardians")].standing == "(1-0)"

    # Game dat exact matcht (Tigers at Guardians, 2026-10-01 19:00 Amsterdam).
    g = Game(
        date_ams=date(2026, 10, 1), time_ams=time(19, 0), hour_ams=19,
        date_et=date(2026, 10, 1), away="Tigers", home="Guardians",
        is_tbd=False, source_seq=0, enrichment=None,
    )

    ctx = build_page_context(
        [g], page="alles", team_slug_q=None, season=season, postseason=pd,
        clock=clock, img_dir=tmp_path, asset_version="v1",
    )

    row = ctx.days[0].rows[0]
    # De serie-stand (niet de seizoen-record) wordt getoond:
    assert row.postseason_record == "(1-0)"
    assert row.postseason_descr == "AL Division Series*"
