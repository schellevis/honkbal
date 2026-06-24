# tests/unit/test_models.py
from datetime import date, datetime, time

import pytest

from honkbal.clock import AMSTERDAM
from honkbal.models import (
    Enrichment,
    Game,
    PostseasonData,
    PostseasonGame,
    ScheduleMeta,
    sort_games,
)


def _game(d, t, away, home, seq, tbd=False, et=None):
    return Game(
        date_ams=d,
        time_ams=t,
        hour_ams=(t.hour if t else None),
        date_et=et or d,
        away=away,
        home=home,
        is_tbd=tbd,
        source_seq=seq,
    )


def test_game_defaults_enrichment_none():
    g = _game(date(2026, 4, 8), time(19, 5), "yankees", "red sox", 0)
    assert g.enrichment is None
    assert g.hour_ams == 19


def test_game_accepts_enrichment_without_changing_core():
    e = Enrichment(score=0.9, label="must-watch", reasons=("rivalry",))
    g = _game(date(2026, 4, 8), time(19, 5), "yankees", "red sox", 0).model_copy(
        update={"enrichment": e}
    )
    assert g.enrichment.score == 0.9
    assert g.away == "yankees"  # rest van het model ongewijzigd (SPEC §11)


def test_sort_within_day_by_time_then_tbd_last_then_source_seq():
    d = date(2026, 4, 8)
    games = [
        _game(d, None, "a", "b", 5, tbd=True),       # TBD, later seq
        _game(d, None, "c", "d", 3, tbd=True),       # TBD, eerdere seq
        _game(d, time(22, 0), "e", "f", 1),
        _game(d, time(13, 0), "g", "h", 2),
        _game(date(2026, 4, 9), time(1, 0), "i", "j", 0),  # andere (latere) dag
    ]
    out = sort_games(games)
    assert [g.source_seq for g in out] == [2, 1, 3, 5, 0]
    # binnen 8 apr: 13:00, 22:00, dan TBD (seq 3 voor seq 5); 9 apr daarna


def test_schedule_meta_fields():
    m = ScheduleMeta(
        modified=datetime(2026, 3, 8, 23, 5, tzinfo=AMSTERDAM),
        refreshed=datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM),
    )
    assert m.refreshed > m.modified


def test_postseason_data_keyed_lookup():
    pg = PostseasonGame(
        event_id="401809252", record="0-0", descr="ALDS Game 1*",
        home="Guardians", away="Tigers", standing="(0-0)",
    )
    pd = PostseasonData(
        fetched_at=datetime(2026, 10, 1, 19, 0, tzinfo=AMSTERDAM),
        teams={"CLE": "Guardians", "DET": "Tigers"},
        games={(date(2026, 10, 1), 19, "Guardians"): pg},
    )
    got = pd.games[(date(2026, 10, 1), 19, "Guardians")]
    assert got.descr == "ALDS Game 1*"


def test_game_is_frozen():
    from pydantic import ValidationError

    g = _game(date(2026, 4, 8), time(19, 5), "yankees", "red sox", 0)
    with pytest.raises((ValidationError, TypeError)):
        g.away = "mets"  # frozen model
