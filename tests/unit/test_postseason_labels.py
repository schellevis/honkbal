from datetime import date, datetime, time

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Game, PostseasonData, PostseasonGame
from honkbal.render.labels import date_derived_phase, postseason_label
from honkbal.season import select_active_season


def _season():
    return select_active_season(FrozenClock(datetime(2026, 10, 15, 12, tzinfo=AMSTERDAM)))


def _psgame(hour, away, home, d=date(2026, 10, 14)):
    return Game(date_ams=d, time_ams=time(hour, 0), hour_ams=hour, date_et=d,
                away=away, home=home, is_tbd=False, source_seq=0, enrichment=None)


def test_date_derived_phase_boundaries():
    s = _season()
    assert date_derived_phase(date(2026, 10, 1), "Yankees", "Red Sox", season=s) == "AL Wild Card"
    assert date_derived_phase(date(2026, 10, 5), "Yankees", "Red Sox", season=s) == "ALDS"
    assert date_derived_phase(date(2026, 10, 13), "Yankees", "Red Sox", season=s) == "ALCS"
    assert date_derived_phase(date(2026, 10, 25), "Yankees", "Red Sox", season=s) == "World Series"
    assert date_derived_phase(date(2026, 10, 5), "Mets", "Cubs", season=s) == "NLDS"
    assert date_derived_phase(date(2026, 9, 30), "Yankees", "Red Sox", season=s) is None


def test_postseason_label_espn_match_wins_over_fallback():
    s = _season()
    g = _psgame(20, "Yankees", "Red Sox")
    pd = PostseasonData(
        fetched_at=datetime(2026, 10, 14, 8, tzinfo=AMSTERDAM),
        teams={"NYY": "Yankees", "BOS": "Red Sox"},
        # standing is wat parse_series_standing levert (al "(x-y)"); record is de seizoen-W-L
        # die NIET als serie-stand getoond mag worden.
        games={(date(2026, 10, 14), 20, "Red Sox"):
               PostseasonGame(event_id="42", record="92-70", standing="(2-1)",
                              descr="ALDS Game 1*", home="Red Sox", away="Yankees")},
    )
    descr, standing = postseason_label(g, season=s, postseason=pd)
    assert descr == "ALDS Game 1*"
    assert standing == "(2-1)"  # de serie-stand, niet de seizoen-record "92-70"


def test_postseason_label_fallback_when_no_espn():
    s = _season()
    g = _psgame(20, "Yankees", "Red Sox", d=date(2026, 10, 5))
    descr, standing = postseason_label(g, season=s, postseason=None)
    assert descr == "ALDS"
    assert standing is None


def test_postseason_label_outside_window_returns_none():
    s = _season()
    g = _psgame(20, "Yankees", "Red Sox", d=date(2026, 6, 1))
    descr, standing = postseason_label(g, season=s, postseason=None)
    assert descr is None and standing is None
