"""Render-wiring regressieguard (C4).

Rendert de ECHTE templates via de CLI en assert op de daadwerkelijke output:
- elke schedule-pagina + team-pagina laadt favorites.js + loadmore.js
- elke pagina registreert de service worker via /js/register-sw.js (die /sw.js registreert)
- scores/standings/settings laden hun eigen module + favorites + register-sw
- de loadmore-knop heeft de attributen/elementen die loadmore.js nodig heeft
- de nav bevat de team-<select>

Deze test faalt tegen de ongewijzigde templates en slaagt na de wiring.
De service-worker-registratie staat in /js/register-sw.js (SPEC §6.1 — geen inline blob);
de gerenderde pagina verwijst ernaar, en register-sw.js zelf registreert /sw.js.
"""

from datetime import datetime
from pathlib import Path

import pytest

from honkbal.cli import main
from honkbal.clock import FrozenClock

FIXTURE_DATA = Path(__file__).parent.parent / "fixtures" / "cli" / "data"
NOW = "2026-06-21T12:00:00+02:00"

SCHEDULE_PAGES = ["index.html", "avond.html", "ochtend.html", "nacht.html", "alles.html"]


@pytest.fixture(scope="module")
def built_site(tmp_path_factory):
    out = tmp_path_factory.mktemp("docs")
    rc = main(
        ["--now", NOW, "render", "--out", str(out), "--data-dir", str(FIXTURE_DATA)],
        clock=FrozenClock(datetime.fromisoformat(NOW)),
    )
    assert rc == 0
    return out


def _read(out: Path, name: str) -> str:
    return (out / name).read_text(encoding="utf-8")


def _assert_sw_registered(out: Path, html: str) -> None:
    """De pagina verwijst naar register-sw.js, en die module registreert /sw.js."""
    assert "/js/v/" in html and "register-sw.js" in html, (
        "pagina verwijst niet naar versioned register-sw.js"
    )
    sw_mod = (out / "js" / "register-sw.js").read_text(encoding="utf-8")
    assert "serviceWorker" in sw_mod
    assert '"/sw.js"' in sw_mod or "'/sw.js'" in sw_mod
    assert (out / "sw.js").is_file(), "/sw.js ontbreekt in de build"


@pytest.mark.parametrize("page", SCHEDULE_PAGES)
def test_schedule_pages_load_favorites_and_loadmore_and_sw(built_site, page):
    html = _read(built_site, page)
    assert "favorites-init.js" in html, f"{page} laadt favorites-init.js niet"
    assert "loadmore.js" in html, f"{page} laadt loadmore.js niet"
    _assert_sw_registered(built_site, html)


def test_team_page_loads_favorites_loadmore_sw(built_site):
    html = _read(built_site, "dodgers.html")
    assert "favorites-init.js" in html
    assert "loadmore.js" in html
    _assert_sw_registered(built_site, html)


def _assert_shared_nav(html: str) -> None:
    """Gedeelde topnav + standaard H1 (SPEC §2, I3).

    Productie-markup: Bootstrap-topnav (ul.nav.nav-tabs.nav-top) en een H1 met
    een link terug naar de homepage. De team-<select> hoort bij de schedule-subnav
    (alleen schema-pagina's), niet bij scores/standings/settings.
    """
    assert '<a href="/"><span>⚾</span> honkbal.net</a>' in html, "standaard H1 ontbreekt"
    assert 'class="nav nav-tabs nav-top"' in html, "topnav ontbreekt"
    assert "/scores.html" in html and "/standings.html" in html and "/settings.html" in html, (
        "topnav mist links naar scores/standen/instellingen"
    )


def test_scores_page_loads_scores_js_and_sw(built_site):
    html = _read(built_site, "scores.html")
    # Versioned module-root: hele ES-modulegraph hangt onder /js/v/<asset_version>/.
    assert "/js/v/" in html and "/scores-entry.js" in html
    assert "import { init }" not in html, "scores.html bevat nog een inline module-bootstrap"
    assert "favorites-init.js" in html
    _assert_sw_registered(built_site, html)
    _assert_shared_nav(html)
    # JS-hooks die scores.js leest (productie-shell: per-dag-tabellen in #scores-container):
    assert 'id="scores-container"' in html, "scores container-hook ontbreekt"
    assert 'id="scores-status"' in html, "scores status-indicator ontbreekt"
    assert 'id="scores-time"' in html, "scores laatste-update tijd-hook ontbreekt"
    # scores is het actieve nav-item
    assert '/scores.html?' in html and 'class="nav-link active" href="/scores.html' in html


def test_standings_page_loads_standings_js_and_sw(built_site):
    html = _read(built_site, "standings.html")
    assert "/js/v/" in html and "/standings-entry.js" in html
    assert "import { init }" not in html, "standings.html bevat nog een inline module-bootstrap"
    assert "favorites-init.js" in html
    _assert_sw_registered(built_site, html)
    _assert_shared_nav(html)
    # JS-hooks die standings.js leest (productie-shell: tabs + meta + container):
    assert 'id="standings-tabs"' in html, "standings tabs-hook ontbreekt"
    assert 'id="standings-container"' in html, "standings container-hook ontbreekt"
    assert "data-tab=" in html, "standings tab-knoppen ontbreken"
    assert "data-season=" in html, "standings data-season ontbreekt (server-injected season)"
    assert 'class="nav-link active" href="/standings.html' in html


def test_settings_page_loads_settings_js_and_sw(built_site):
    html = _read(built_site, "settings.html")
    assert "/js/v/" in html and "/settings-entry.js" in html
    assert "import { init }" not in html, "settings.html bevat nog een inline module-bootstrap"
    assert "favorites-init.js" in html
    _assert_sw_registered(built_site, html)
    _assert_shared_nav(html)
    # JS-hooks die settings.js leest:
    assert 'id="favorites-save"' in html and 'id="favorites-clear"' in html
    assert 'id="favorites-status"' in html
    assert 'name="team"' in html, "settings checkbox-grid ontbreekt"
    # Het instellingen-nav-item is een tandwiel-icoon (geen tekst); actief via .nav-link-icon.
    assert 'class="nav-link nav-link-icon active" href="/settings.html' in html


def test_loadmore_button_has_required_attributes(built_site):
    # alles.html heeft genoeg fixture-games voor een tail
    html = _read(built_site, "alles.html")
    assert 'class="loadmore"' in html
    assert "data-page=" in html
    assert "data-tail-version=" in html
    assert "loadmore-msg" in html, "loadmore-msg element ontbreekt"
    assert "loadmore-container" in html, "loadmore-container ontbreekt"


def test_loadmore_tail_version_equals_asset_version(built_site):
    import json

    html = _read(built_site, "alles.html")
    tail = json.loads((built_site / "alles.tail.json").read_text(encoding="utf-8"))
    version = tail["version"]
    assert f'data-tail-version="{version}"' in html


def test_nav_contains_team_select(built_site):
    html = _read(built_site, "index.html")
    assert "<select" in html, "nav bevat geen team-<select>"
    assert "data-team-select" in html
    # alfabetisch: een paar bekende teams als <option value="slug">
    assert 'value="dodgers"' in html
    assert 'value="yankees"' in html
