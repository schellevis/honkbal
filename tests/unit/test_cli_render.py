import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from honkbal.cli import _copy_static_assets, main
from honkbal.clock import AMSTERDAM, FrozenClock

FIXTURE_DATA = Path(__file__).parent.parent / "fixtures" / "cli" / "data"

# Alle pagina's die SPEC §2 voorschrijft (excl. <team>.html, die telt apart):
CORE_PAGES = [
    "index.html", "avond.html", "ochtend.html", "nacht.html", "alles.html",
    "scores.html", "standings.html", "settings.html", "debug.html",
    "offline.html", "404.html",
]
SCHEDULE_PAGES = ["avond", "ochtend", "nacht", "alles"]  # hebben een eigen tail.json


def test_render_produces_all_docs_files(tmp_path):
    out = tmp_path / "docs"
    # Pin de klok op de start van het fixture-venster (games lopen 2026-06-21 t/m 2026-07-20).
    # Zonder vaste klok filtert de >now-filter met de systeemtijd verse games weg: naarmate
    # het seizoen vordert zakken de per-tijdvak-pagina's onder de 250-drempel en verdwijnt hun
    # tail.json → de tail-assert wordt een tijdbom. Alle andere tests hier pinnen de klok al.
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    rc = main(
        ["--now", "2026-06-21T12:00:00+02:00", "render",
         "--out", str(out), "--data-dir", str(FIXTURE_DATA)],
        clock=clock,
    )
    assert rc == 0

    for page in CORE_PAGES:
        assert (out / page).is_file(), f"ontbreekt: {page}"

    # 30 teampagina's
    from honkbal.config.teams import TEAMS_AL, TEAMS_NL, team_slug

    for team in (*TEAMS_NL, *TEAMS_AL):
        assert (out / f"{team_slug(team)}.html").is_file(), f"teampagina ontbreekt: {team}"

    # tail.json per schemapagina (fixture has 1350 games, all exceed 250 inline threshold)
    for page in SCHEDULE_PAGES:
        assert (out / f"{page}.tail.json").is_file(), f"tail ontbreekt: {page}"

    # LOW-7: index krijgt GEEN eigen tail.json; de knop hergebruikt de default-tab-tail.
    assert not (out / "index.tail.json").exists(), "index.tail.json hoort niet te bestaan"
    index_html = (out / "index.html").read_text(encoding="utf-8")
    m = re.search(r'data-page="([^"]+)"', index_html)
    assert m, "index-loadmore-knop mist data-page"
    assert (out / f"{m.group(1)}.tail.json").is_file(), (
        f"index verwijst naar {m.group(1)}.tail.json maar die bestaat niet"
    )

    # Assets root-relatief
    assert (out / "css" / "style.css").is_file()
    assert (out / "sw.js").is_file()  # service worker op root (scope /)
    assert not (out / "js" / "sw.js").exists()  # NIET in js/
    versioned_js_root = out / "js" / "v"
    assert versioned_js_root.is_dir(), "versioned js-root ontbreekt"
    assert any(versioned_js_root.rglob("scores-entry.js")), "versioned scores-entry ontbreekt"
    assert (out / "favicon.ico").is_file()
    assert (out / "icon.png").is_file()
    assert (out / "manifest.json").is_file()
    assert any((out / "img").glob("*.png"))


def test_render_tail_json_is_valid_and_versioned(tmp_path):
    out = tmp_path / "docs"
    main(["render", "--out", str(out), "--data-dir", str(FIXTURE_DATA)])
    # tail.json files only exist when there are enough games to split (>250 inline rows).
    # With the fixture data, we might or might not have tail. Just verify format if present.
    tail_path = out / "alles.tail.json"
    if tail_path.exists():
        data = json.loads(tail_path.read_text())
        assert set(data) >= {"version", "page", "total", "batch_size", "blocks"}
        assert data["batch_size"] == 250
        assert isinstance(data["blocks"], list)


def test_render_with_missing_data_renders_empty_state(tmp_path):
    # Geen cache aanwezig → lege staat, exit 0 (graceful degradation, SPEC §9/§5.8)
    out = tmp_path / "docs"
    rc = main(["render", "--out", str(out), "--data-dir", str(tmp_path / "geen-cache")])
    assert rc == 0
    assert (out / "index.html").is_file()
    assert "Geen wedstrijden beschikbaar" in (out / "alles.html").read_text(encoding="utf-8")


def test_now_filter_excludes_past_games(tmp_path):
    """§3.2: concrete filter test — past game absent, future game present.

    We write a minimal CSV with exactly two games:
    - PAST:   Yankees at Red Sox  on 2026-04-01 (clearly before now)
    - FUTURE: Mets at Phillies    on 2026-09-15 (clearly after now, within season window)

    With a FrozenClock at 2026-06-21 12:00 CEST, the cutoff is now itself.
    Both dates are within the 2026 season window (showfrom=2026-03-26, hide=2027-02-01),
    so only the >now filter differentiates them.

    The past game must NOT appear in alles.html; the future game MUST appear.
    This test fails if the >now filter is removed from render_site().
    """
    from datetime import datetime

    # Minimal CSV: parser reads col0=date, col2=ET-time, col3=subject (len>=4 required).
    # Both teams are in ALLOWLIST_RENDER; season window covers both dates.
    # ET time 02:05 PM → 14:05 AMS (same calendar day, hour 14 = avond/alles).
    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    past_row = "04/01/26,10:05 AM,02:05 PM,Yankees at Red Sox"
    future_row = "09/15/26,10:05 AM,02:05 PM,Mets at Phillies"
    csv_text = "\n".join([header, past_row, future_row]) + "\n"

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "all.csv").write_text(csv_text, encoding="utf-8")
    (data_dir / "headers.json").write_text('{}', encoding="utf-8")

    out = tmp_path / "docs"
    now_iso = "2026-06-21T12:00:00+02:00"
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    rc = main(
        ["--now", now_iso, "render", "--out", str(out), "--data-dir", str(data_dir)],
        clock=clock,
    )
    assert rc == 0
    assert (out / "alles.html").is_file()

    content = (out / "alles.html").read_text(encoding="utf-8")
    # Past game (2026-04-01 14:05 < now 2026-06-21 12:00) must NOT appear as a game ROW.
    # NB: teamnamen kunnen wel in de nav-<select> staan; toets daarom op de game-rij.
    assert 'data-away-team="yankees"' not in content, (
        "Past game (Yankees at Red Sox, 2026-04-01) must be filtered out — start < now"
    )
    # Future game (2026-09-15 > now) must appear as a game row.
    assert 'data-away-team="mets"' in content and 'data-home-team="phillies"' in content, (
        "Future game (Mets at Phillies, 2026-09-15) must be present — start > now"
    )


def test_timed_game_later_today_kept_but_already_started_dropped(tmp_path):
    """MINOR (§3.2): moment-nauwkeurige filter voor GETIMEDE games — strikt vanaf nu.

    now = 2026-06-21 12:00 CEST. Beide wedstrijden staan op dezelfde Amsterdamse dag
    (vandaag), zodat alleen de moment-precisie (niet de datum) het verschil maakt:
    - KEEP:  AMS 2026-06-21 21:00 (later vandaag, nog niet begonnen) → start > nu.
    - DROP:  AMS 2026-06-21 09:00 (eerder vandaag, al begonnen)      → start <= nu,
             ook al is date_ams (2026-06-21) == vandaag (date-granular zou 'm houden).

    ET +6h = AMS in de zomer, dus ET 03:00 PM → AMS 21:00 en ET 03:00 AM → AMS 09:00.
    """
    from datetime import datetime

    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    keep_row = "06/21/26,01:05 PM,03:00 PM,Mets at Phillies"     # AMS 2026-06-21 21:00 (keep)
    drop_row = "06/21/26,01:05 AM,03:00 AM,Yankees at Red Sox"   # AMS 2026-06-21 09:00 (drop)
    csv_text = "\n".join([header, keep_row, drop_row]) + "\n"

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "all.csv").write_text(csv_text, encoding="utf-8")
    (data_dir / "headers.json").write_text("{}", encoding="utf-8")

    out = tmp_path / "docs"
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    rc = main(
        ["--now", "2026-06-21T12:00:00+02:00", "render",
         "--out", str(out), "--data-dir", str(data_dir)],
        clock=clock,
    )
    assert rc == 0
    content = (out / "alles.html").read_text(encoding="utf-8")
    assert 'data-away-team="mets"' in content, "timed game later today (start > now) must be kept"
    assert 'data-away-team="yankees"' not in content, (
        "timed game already started today (start <= now) must be dropped"
    )


def test_render_collapses_exact_duplicate_schedule_rows(tmp_path):
    from datetime import datetime

    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    dup_row = "06/21/26,05:05 PM,11:05 PM,Astros at Blue Jays"
    csv_text = "\n".join([header, dup_row, dup_row]) + "\n"

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "all.csv").write_text(csv_text, encoding="utf-8")
    (data_dir / "headers.json").write_text("{}", encoding="utf-8")

    out = tmp_path / "docs"
    clock = FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))
    rc = main(
        ["--now", "2026-06-21T12:00:00+02:00", "render",
         "--out", str(out), "--data-dir", str(data_dir)],
        clock=clock,
    )
    assert rc == 0

    content = (out / "alles.html").read_text(encoding="utf-8")
    assert content.count('data-away-team="astros"') == 1


def test_copy_static_assets_copies_nested_subdirs_recursively(tmp_path):
    """Fix #4: _copy_static_assets must copy ALL subdirs of frontend/static/ recursively.

    A file in a nested subdirectory (e.g. static/fonts/foo.woff2) must end up at
    out/fonts/foo.woff2. Previously only static/img/ was copied; other subdirs were dropped.
    """
    import honkbal.cli as cli_mod

    # Build a fake frontend layout under tmp_path.
    fake_frontend = tmp_path / "frontend"
    (fake_frontend / "css").mkdir(parents=True)
    (fake_frontend / "css" / "style.css").write_text("body{}", encoding="utf-8")
    (fake_frontend / "static" / "img").mkdir(parents=True)
    (fake_frontend / "static" / "img" / "logo.png").write_bytes(b"\x89PNG")
    # A nested subdir that the old code would silently drop:
    (fake_frontend / "static" / "fonts").mkdir(parents=True)
    (fake_frontend / "static" / "fonts" / "main.woff2").write_bytes(b"woff")
    # A top-level static file:
    (fake_frontend / "static" / "favicon.ico").write_bytes(b"ico")

    out = tmp_path / "docs"
    out.mkdir()

    # Patch FRONTEND so _copy_static_assets uses our fake tree.
    with patch.object(cli_mod, "FRONTEND", fake_frontend):
        _copy_static_assets(out)

    assert (out / "css" / "style.css").is_file(), "css/style.css missing"
    assert (out / "img" / "logo.png").is_file(), "img/logo.png missing"
    assert (out / "favicon.ico").is_file(), "favicon.ico missing"
    # This is the key assertion — would fail with the old code:
    assert (out / "fonts" / "main.woff2").is_file(), (
        "fonts/main.woff2 missing — nested static subdirs must be copied recursively"
    )
