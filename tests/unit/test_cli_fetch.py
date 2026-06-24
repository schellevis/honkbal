from datetime import datetime

from honkbal import cli_fetch
from honkbal.clock import AMSTERDAM, FrozenClock


class _Args:
    def __init__(self, data_dir):
        self.data_dir = str(data_dir)
        self.out = "docs"
        self.now = None


def test_fetch_skipped_via_env_is_noop_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("HONKBAL_NO_FETCH", "1")
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    assert cli_fetch.cmd_fetch(_Args(tmp_path), clock=clock) == 0


def test_postseason_only_fetched_when_now_ge_ps(tmp_path, monkeypatch):
    calls = {"schedule": 0, "standings": 0, "postseason": 0}

    def fake_schedule(clock, *, data_dir):
        calls["schedule"] += 1

        class R:
            ok, success_count = True, 30

        return R()

    def fake_postseason(clock, *, data_dir):
        calls["postseason"] += 1

        class R:
            ok, count = True, 8

        return R()

    def fake_standings(clock, *, data_dir):
        calls["standings"] += 1

        class R:
            ok, count = True, 30

        return R()

    monkeypatch.setattr("honkbal.cli_fetch.fetch_schedule", fake_schedule)
    monkeypatch.setattr("honkbal.cli_fetch.fetch_postseason", fake_postseason)
    monkeypatch.setattr("honkbal.cli_fetch.fetch_standings", fake_standings)

    # midseason (juni 2026, vóór ps 01-10) → géén postseason
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    assert cli_fetch.cmd_fetch(_Args(tmp_path), clock=clock) == 0
    assert calls == {"schedule": 1, "standings": 1, "postseason": 0}

    # postseason (oktober 2026, na ps) → óók postseason
    clock = FrozenClock(datetime(2026, 10, 5, 12, 0, tzinfo=AMSTERDAM))
    assert cli_fetch.cmd_fetch(_Args(tmp_path), clock=clock) == 0
    assert calls == {"schedule": 2, "standings": 1, "postseason": 1}


def test_partial_fetch_keeps_last_known_good(tmp_path, monkeypatch):
    # Fetch faalt onder drempel → fetcher retourneert ok=False, cache blijft (Fase 2-gedrag).
    def failing_schedule(clock, *, data_dir):
        class R:
            ok, success_count = False, 0

        return R()

    def failing_standings(clock, *, data_dir):
        class R:
            ok, count = False, 0

        return R()

    monkeypatch.setattr("honkbal.cli_fetch.fetch_schedule", failing_schedule)
    monkeypatch.setattr("honkbal.cli_fetch.fetch_standings", failing_standings)
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    # cmd_fetch logt de degradatie maar faalt de build NIET (SPEC §9/§12.12)
    assert cli_fetch.cmd_fetch(_Args(tmp_path), clock=clock) == 0
