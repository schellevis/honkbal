from datetime import date, datetime, time
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Game, ScheduleMeta
from honkbal.render.pages import render_all_schedule_pages, render_debug_page
from honkbal.season import select_active_season

IMG = Path(__file__).parent.parent / "fixtures" / "img"


def _clock():
    return FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))


def test_debug_page_has_build_and_season_info_no_legacy_refs():
    c = _clock()
    s = select_active_season(c)
    meta = ScheduleMeta(modified=datetime(2026, 6, 21, 6, tzinfo=AMSTERDAM),
                        refreshed=datetime(2026, 6, 21, 11, 55, tzinfo=AMSTERDAM))
    html = render_debug_page(schedule_meta=meta, season=s, postseason=None,
                             build_version="abc123-7", build_time=c.now(),
                             docs_files={"index.html": c.now()}, asset_version="v1")
    assert "abc123-7" in html
    assert "2026" in html and "2027" in html
    assert "niet actief buiten postseason" in html
    for legacy in ("espn.json", "tvgidsnl.json", "scores.json"):
        assert legacy not in html


def test_integration_writes_all_pages_and_tail(tmp_path):
    c = _clock()
    s = select_active_season(c)
    games = [Game(date_ams=date(2026, 6, 21), time_ams=time(20, 5), hour_ams=20,
                  date_et=date(2026, 6, 21), away="Red Sox", home="Yankees",
                  is_tbd=False, source_seq=0, enrichment=None)]
    render_all_schedule_pages(games, season=s, postseason=None, clock=c,
                              img_dir=IMG, asset_version="v1", out_dir=tmp_path)
    for page in ("index", "avond", "ochtend", "nacht", "alles"):
        assert (tmp_path / f"{page}.html").exists()
    assert (tmp_path / "yankees.html").exists()
    assert not list(tmp_path.glob("*.tail.json"))
