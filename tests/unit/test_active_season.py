from datetime import datetime

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.season import select_active_season

# Mini-tabel met geldige datums (geen 30-02), zodat selectie los van de echte data test.
RAW = {
    2025: {
        "reg": "27-03-2025", "showfrom": "27-03-2025", "einde": "01-11-2025",
        "ps": "29-09-2025", "wc": "29-09-2025", "ds": "03-10-2025",
        "cs": "12-10-2025", "ws": "24-10-2025",
        "new": "01-01-2026", "newreg": "26-03-2026", "hide": "01-02-2026",
        "uitzondering": ["1803DodgersCubs"],
    },
    2026: {
        "reg": "25-03-2026", "showfrom": "26-03-2026", "einde": "15-11-2026",
        "ps": "01-10-2026", "wc": "01-10-2026", "ds": "05-10-2026",
        "cs": "13-10-2026", "ws": "25-10-2026",
        "new": "01-01-2027", "newreg": "27-03-2027", "hide": "01-02-2027",
    },
}


def _clock(y, m, d):
    return FrozenClock(datetime(y, m, d, 12, 0, tzinfo=AMSTERDAM))


def test_midseason_picks_current_year():
    a = select_active_season(_clock(2026, 6, 21), RAW)
    assert a.year == 2026
    assert a.next_year == 2027
    assert a.no_grab is False


def test_after_einde_rolls_forward_nextyear_is_legacy():
    # na einde 2025 (01-11-2025) maar in kalenderjaar 2025 → year rolt naar 2026.
    # next_year is LEGACY berekend (kal.jaar 2025 + 1 = 2026), vóór rollover → gelijk aan year.
    a = select_active_season(_clock(2025, 12, 15), RAW)
    assert a.year == 2026
    assert a.next_year == 2026  # legacy: vóór de rollover berekend, dus == year (niet 2027)
    assert a.no_grab is True    # voorbij einde 2025 én vóór 15-01-2026 → geen fetch


def test_offseason_sets_no_grab():
    a = select_active_season(_clock(2026, 1, 5), RAW)  # voor 15-01
    assert a.no_grab is True


def test_next_uitzondering_empty_when_year_missing():
    a = select_active_season(_clock(2026, 6, 21), RAW)  # next_year 2027 ontbreekt in RAW
    assert a.next_uitzondering == ()


def test_real_config_2026_selects_successfully():
    # integratietest tegen de ECHTE RAW_SEASONS: 2026 is geldig en selecteert zonder fout
    from honkbal.config.seasons import RAW_SEASONS

    a = select_active_season(_clock(2026, 6, 21), RAW_SEASONS)
    assert a.year == 2026
    assert a.next_year == 2027
    assert a.windows.newreg is None  # 2026-blok heeft geen newreg (unknown-state)
