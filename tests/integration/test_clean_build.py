from datetime import datetime
from pathlib import Path

from honkbal.cli import main
from honkbal.clock import FrozenClock

FIXTURE_DATA = Path(__file__).parent.parent / "fixtures" / "cli" / "data"

EXPECTED = [
    "index.html", "avond.html", "ochtend.html", "nacht.html", "alles.html",
    "scores.html", "standings.html", "settings.html", "debug.html",
    "offline.html", "404.html", "sw.js", "manifest.json", "favicon.ico",
    "icon.png", "css/style.css",
]


def _build(tmp_path, data_dir, *, now="2026-06-21T12:00:00+02:00", monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv("HONKBAL_NO_FETCH", "1")
    out = tmp_path / "docs"
    # --now is a global option before the subcommand
    rc = main(
        ["--now", now, "build", "--out", str(out), "--data-dir", str(data_dir)],
        clock=FrozenClock(datetime.fromisoformat(now)),
    )
    return rc, out


def test_clean_build_with_restored_cache(tmp_path, monkeypatch):
    rc, out = _build(tmp_path, FIXTURE_DATA, monkeypatch=monkeypatch)
    assert rc == 0
    for rel in EXPECTED:
        assert (out / rel).is_file(), f"ontbreekt na build: {rel}"
    # 30 teampagina's + 5 tail.json
    from honkbal.config.teams import TEAMS_AL, TEAMS_NL, team_slug

    for t in (*TEAMS_NL, *TEAMS_AL):
        assert (out / f"{team_slug(t)}.html").is_file(), f"teampagina ontbreekt: {t}"
    # tail.json bestaat alleen als er meer dan 250 wedstrijden zijn per filterpagina.
    # Alles en avond hebben voldoende fixture-games; ochtend/nacht/index variëren.
    assert (out / "alles.tail.json").is_file(), "alles.tail.json ontbreekt"
    assert any((out).glob("*.tail.json")), "geen enkel tail.json aangemaakt"


def test_clean_build_no_cache_at_all_still_succeeds(tmp_path, monkeypatch):
    rc, out = _build(tmp_path, tmp_path / "geen-cache", monkeypatch=monkeypatch)
    assert rc == 0
    assert (out / "index.html").is_file()
    assert "Geen wedstrijden beschikbaar" in (out / "alles.html").read_text(encoding="utf-8")
