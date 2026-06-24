from datetime import date, datetime, time

import pytest

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Game
from honkbal.render.filters import passes_time_filter, should_render, uitzondering_code
from honkbal.season import select_active_season


def _game(hour, *, away="Red Sox", home="Yankees", d=date(2026, 6, 21),
          et=None, tbd=False, seq=0):
    return Game(
        date_ams=d,
        time_ams=None if tbd else time(hour, 5),
        hour_ams=None if tbd else hour,
        date_et=et or d,
        away=away, home=home, is_tbd=tbd, source_seq=seq, enrichment=None,
    )


@pytest.mark.parametrize("hour,avond,ochtend,nacht", [
    (2,  False, False, True),
    (3,  False, True,  True),
    (4,  False, True,  False),
    (5,  False, True,  False),
    (6,  False, True,  False),
    (7,  False, False, False),
    (13, False, False, False),
    (14, True,  False, False),
    (22, True,  False, False),
    (23, True,  False, True),
    (0,  False, False, True),
    (1,  False, False, True),
])
def test_time_filter_boundaries(hour, avond, ochtend, nacht):
    assert passes_time_filter("avond", hour) is avond
    assert passes_time_filter("ochtend", hour) is ochtend
    assert passes_time_filter("nacht", hour) is nacht
    assert passes_time_filter("alles", hour) is True


def test_tbd_only_on_alles_and_team():
    assert passes_time_filter("avond", None) is False
    assert passes_time_filter("alles", None) is True


def _season(y=2026, m=6, d=21):
    return select_active_season(FrozenClock(datetime(y, m, d, 12, 0, tzinfo=AMSTERDAM)))


def test_should_render_tbd_skipped_on_avond_kept_on_alles():
    g = _game(0, tbd=True)
    s = _season()
    assert should_render(g, page="avond", team_slug_q=None, season=s) is False
    assert should_render(g, page="alles", team_slug_q=None, season=s) is True


def test_should_render_team_page_matches_slug():
    g = _game(20, away="Red Sox", home="Yankees")
    s = _season()
    assert should_render(g, page="team", team_slug_q="yankees", season=s) is True
    assert should_render(g, page="team", team_slug_q="red+sox", season=s) is True
    assert should_render(g, page="team", team_slug_q="mets", season=s) is False


def test_should_render_allowlist_blocks_non_mlb():
    g = _game(20, away="River Cats", home="Chihuahuas")
    s = _season()
    assert should_render(g, page="alles", team_slug_q=None, season=s) is False


def test_uitzondering_code_uses_original_names():
    g = _game(20, away="Dodgers", home="Cubs", d=date(2026, 3, 18))
    assert uitzondering_code(g) == "1803DodgersCubs"


def test_should_render_before_showfrom_blocked_unless_uitzondering():
    s = _season()
    early = _game(20, away="Mets", home="Phillies", d=date(2026, 3, 20))
    assert should_render(early, page="alles", team_slug_q=None, season=s) is False
    uitz = _game(20, away="Dodgers", home="Cubs", d=date(2026, 3, 18))
    assert should_render(uitz, page="alles", team_slug_q=None, season=s) is False


def test_should_render_hide_blocks_overview_keeps_team():
    s = _season()
    late = _game(20, away="Mets", home="Phillies", d=date(2027, 2, 2))
    assert should_render(late, page="alles", team_slug_q=None, season=s) is False
    assert should_render(late, page="team", team_slug_q="mets", season=s) is True


def test_newreg_none_disables_next_season_skip():
    s = _season()
    g = _game(20, away="Mets", home="Phillies", d=date(2027, 1, 15), et=date(2027, 1, 15))
    assert should_render(g, page="alles", team_slug_q=None, season=s) is True
