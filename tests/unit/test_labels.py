from datetime import date, datetime

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.render.labels import countdown, date_header_label, special_label
from honkbal.season import select_active_season


def _clock(y, m, d, h=12):
    return FrozenClock(datetime(y, m, d, h, 0, tzinfo=AMSTERDAM))


def _season(c=None):
    return select_active_season(c or _clock(2026, 6, 21))


def test_date_header_vandaag_morgen_weekday():
    c = _clock(2026, 6, 21)
    assert date_header_label(date(2026, 6, 21), clock=c) == "vandaag, 21 juni"
    assert date_header_label(date(2026, 6, 22), clock=c) == "morgen, 22 juni"
    assert date_header_label(date(2026, 6, 24), clock=c) == "woensdag, 24 juni"


def test_special_label_spring_training():
    s = _season()
    assert special_label(date(2026, 3, 20), date(2026, 3, 20),
                         season=s, is_uitzondering=False) == ("spring training", "badge")


def test_special_label_opening_day():
    s = _season()
    assert special_label(date(2026, 3, 25), date(2026, 3, 25),
                         season=s, is_uitzondering=False) == ("opening day", "badge")


def test_special_label_all_star():
    s = _season()
    assert special_label(date(2026, 7, 14), date(2026, 7, 14),
                         season=s, is_uitzondering=False) == ("all-star game", "badge")


def test_special_label_next_year_plain():
    s = _season()
    assert special_label(date(2027, 1, 3), date(2027, 1, 3),
                         season=s, is_uitzondering=False) == ("2027", "plain")


def test_special_label_none_for_regular_day():
    s = _season()
    assert special_label(date(2026, 6, 21), date(2026, 6, 21),
                         season=s, is_uitzondering=False) is None


def test_countdown_days_before_opening():
    c = _clock(2026, 3, 20)
    s = _season(_clock(2026, 3, 20))
    assert countdown(season=s, clock=c) == ("Nog 5 dagen tot opening day!", False)


def test_countdown_one_day_singular():
    c = _clock(2026, 3, 24)
    s = _season(_clock(2026, 3, 24))
    assert countdown(season=s, clock=c) == ("Nog 1 dag tot opening day!", False)


def test_countdown_opening_day():
    c = _clock(2026, 3, 25)
    s = _season(_clock(2026, 3, 25))
    assert countdown(season=s, clock=c) == ("Opening day!", True)


def test_countdown_none_after_opening():
    c = _clock(2026, 4, 1)
    s = _season(_clock(2026, 4, 1))
    assert countdown(season=s, clock=c) is None
