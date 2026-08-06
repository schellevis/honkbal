import json
from datetime import date, datetime, time

from honkbal.clock import AMSTERDAM
from honkbal.models import Game
from honkbal.tv_guide import TvAiring, TvMatch, build_tv_lookup, load_tv_guide

DAY = date(2026, 8, 6)


def _game(away, home, *, hh=None, mm=0, day=DAY, seq=0):
    tbd = hh is None
    return Game(
        date_ams=day,
        time_ams=None if tbd else time(hh, mm),
        hour_ams=None if tbd else hh,
        date_et=day,
        away=away,
        home=home,
        is_tbd=tbd,
        source_seq=seq,
    )


def _airing(*, channel="espn2", hh=21, mm=0, day=DAY, teams=(), live=True, nl=False):
    return TvAiring(
        channel=channel,
        start=datetime.combine(day, time(hh, mm), tzinfo=AMSTERDAM),
        teams=frozenset(teams),
        nl_commentary=nl,
        live=live,
    )


def _epoch(hh, mm=0, day=DAY):
    return int(datetime.combine(day, time(hh, mm), tzinfo=AMSTERDAM).timestamp())


def test_team_match_is_unordered_and_carries_nl_flag():
    games = [_game("Dodgers", "Cubs", hh=21, mm=5)]
    airings = [_airing(teams=("cubs", "dodgers"), hh=21, mm=0, nl=True)]

    lookup = build_tv_lookup(games, airings)

    assert lookup == {(_epoch(21, 5), "dodgers", "cubs"): TvMatch("espn2", True)}


def test_team_match_respects_tolerance_boundary():
    games = [_game("Yankees", "Red Sox", hh=21, mm=0)]
    within = [_airing(teams=("red sox", "yankees"), hh=22, mm=15)]  # 75 min
    beyond = [_airing(teams=("red sox", "yankees"), hh=22, mm=16)]  # 76 min

    assert build_tv_lookup(games, within)
    assert not build_tv_lookup(games, beyond)


def test_doubleheader_closest_start_wins():
    early = _game("Guardians", "Tigers", hh=18, mm=0, seq=0)
    late = _game("Guardians", "Tigers", hh=21, mm=30, seq=1)
    airings = [_airing(teams=("guardians", "tigers"), hh=21, mm=20)]

    lookup = build_tv_lookup([early, late], airings)

    assert list(lookup) == [(_epoch(21, 30), "guardians", "tigers")]


def test_simulcast_keeps_first_channel():
    games = [_game("Cubs", "Dodgers", hh=21, mm=0)]
    airings = [
        _airing(channel="espn", teams=("cubs", "dodgers"), hh=21, mm=0),
        _airing(channel="espn4", teams=("cubs", "dodgers"), hh=21, mm=5),
    ]

    lookup = build_tv_lookup(games, airings)

    assert lookup[(_epoch(21), "cubs", "dodgers")].channel == "espn"


def test_teamless_airing_matches_only_when_unambiguous():
    lone = [_game("Mets", "Phillies", hh=1, mm=10)]
    crowded = lone + [_game("Braves", "Marlins", hh=1, mm=15)]
    airings = [_airing(teams=(), hh=1, mm=0)]

    assert build_tv_lookup(lone, airings) == {
        (_epoch(1, 10), "mets", "phillies"): TvMatch("espn2", False)
    }
    assert build_tv_lookup(crowded, airings) == {}


def test_teamless_airing_skips_games_already_matched_by_team_pass():
    matched = _game("Cubs", "Dodgers", hh=21, mm=0)
    other = _game("Mets", "Phillies", hh=21, mm=10)
    airings = [
        _airing(channel="espn", teams=("cubs", "dodgers"), hh=21, mm=0),
        _airing(channel="espn3", teams=(), hh=21, mm=5),
    ]

    lookup = build_tv_lookup([matched, other], airings)

    # De teamloze airing ziet alleen de nog vrije game en mag die dus wél claimen.
    assert lookup[(_epoch(21), "cubs", "dodgers")].channel == "espn"
    assert lookup[(_epoch(21, 10), "mets", "phillies")].channel == "espn3"


def test_tbd_games_and_replays_never_match():
    games = [_game("Cubs", "Dodgers", hh=None)]
    airings = [_airing(teams=("cubs", "dodgers"), hh=21)]
    assert build_tv_lookup(games, airings) == {}

    timed = [_game("Cubs", "Dodgers", hh=21)]
    replay = [_airing(teams=("cubs", "dodgers"), hh=21, live=False)]
    assert build_tv_lookup(timed, replay) == {}


def test_load_tv_guide_reads_cache_and_skips_junk(tmp_path):
    (tmp_path / "tv_guide.json").write_text(json.dumps({
        "airings": [
            {
                "channel": "espn2",
                "start": "2026-08-06T21:00:00+02:00",
                "teams": ["cubs", "dodgers"],
                "nl_commentary": True,
                "live": True,
                "title": "MLB: Cubs vs Dodgers",
            },
            {"channel": "espn9", "start": "2026-08-06T21:00:00+02:00"},
            {"channel": "espn", "start": "2026-08-06T21:00:00"},
            {"channel": "espn", "start": "niet-een-datum"},
            {"channel": "espn3", "start": "2026-08-06T23:00:00+02:00", "teams": ["cubs"]},
            "geen-dict",
        ]
    }))

    airings = load_tv_guide(tmp_path)

    assert len(airings) == 2
    assert airings[0].teams == frozenset({"cubs", "dodgers"})
    assert airings[0].nl_commentary is True
    # Eén team is geen paar: behandeld als teamloos.
    assert airings[1].teams == frozenset()


def test_load_tv_guide_soft_fails(tmp_path):
    assert load_tv_guide(tmp_path) == []

    (tmp_path / "tv_guide.json").write_text("{kapot")
    assert load_tv_guide(tmp_path) == []
