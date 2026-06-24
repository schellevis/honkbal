from datetime import datetime

from honkbal import cli
from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.season import ConfigError


def test_config_error_makes_render_exit_nonzero(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ConfigError("ps > einde")

    monkeypatch.setattr("honkbal.cli.select_active_season", boom)
    rc = cli.main(
        ["render", "--out", str(tmp_path / "docs"), "--data-dir", str(tmp_path / "none")],
        clock=FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM)),
    )
    assert rc != 0


def test_build_aborts_on_config_error_in_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("HONKBAL_NO_FETCH", "1")

    def boom(*a, **k):
        raise ConfigError("ontbrekend veld")

    # fetch-pad slaat over (HONKBAL_NO_FETCH=1), maar render-pad roept select_active_season ook
    monkeypatch.setattr("honkbal.cli.select_active_season", boom)
    rc = cli.main(
        ["build", "--out", str(tmp_path / "docs"), "--data-dir", str(tmp_path / "d")],
        clock=FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM)),
    )
    assert rc != 0
