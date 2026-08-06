from datetime import date, datetime, time
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Game, PostseasonData, PostseasonGame
from honkbal.render.context import build_page_context
from honkbal.render.pages import render_schedule_page
from honkbal.render.tail import split_context
from honkbal.season import select_active_season

IMG = Path(__file__).parent.parent / "fixtures" / "img"


def _g(d, hour, away, home, seq=0):
    return Game(date_ams=d, time_ams=time(hour, 5), hour_ams=hour, date_et=d,
                away=away, home=home, is_tbd=False, source_seq=seq, enrichment=None)


def _clock():
    return FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))


def _render(games, page="alles", tv_lookup=None):
    c = _clock()
    s = select_active_season(c)
    ctx = build_page_context(games, page=page, team_slug_q=None, season=s,
                             postseason=None, clock=c, img_dir=IMG, asset_version="v1",
                             tv_lookup=tv_lookup)
    inline, tail = split_context(ctx)
    return render_schedule_page(inline, asset_version="v1", clock=c, season=s,
                                inline_days=inline.days,
                                tail_count=sum(len(d.rows) for d in tail))


def test_valid_html5_skeleton_and_lang_nl():
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert '<html lang="nl"' in html
    assert "/css/style.css?v1" in html
    assert "</form></form>" not in html
    assert html.count("</body>") == 1


def test_row_data_attributes_for_favorites():
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert 'data-away-team="red sox"' in html
    assert 'data-home-team="yankees"' in html
    assert "20:05" in html


def test_logo_and_name_rendered_and_escaped():
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert "/img/yankees-fs8.png?v1" in html
    assert "Yankees" in html
    assert "/img/red+sox-fs8.png?v1" in html


def test_row_data_interest_from_enrichment_percentile():
    """SPEC §6.9: rijen met enrichment dragen het percentiel als data-interest; zonder niet."""
    from honkbal.models import Enrichment

    scored = Game(date_ams=date(2026, 6, 21), time_ams=time(20, 5), hour_ams=20,
                  date_et=date(2026, 6, 21), away="Red Sox", home="Yankees",
                  is_tbd=False, source_seq=0,
                  enrichment=Enrichment(score=41.6, label="topper", reasons=("rivalry",),
                                        percentile=88))
    plain = _g(date(2026, 6, 21), 20, "Mets", "Phillies", seq=1)
    html = _render([scored, plain])
    assert 'data-interest="88"' in html
    assert html.count("data-interest") == 1  # rij zonder enrichment krijgt geen attribuut


def test_row_data_start_epoch_for_timed_games():
    """SPEC §6.8: getimede rijen dragen data-start (dedup live-sectie bij doubleheaders)."""
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    from datetime import datetime

    from honkbal.clock import AMSTERDAM
    ts = int(datetime(2026, 6, 21, 20, 5, tzinfo=AMSTERDAM).timestamp())
    assert f'data-start="{ts}"' in html


def test_tbody_carries_day_date_for_stale_pruning():
    """SPEC §6.10: elk dagblok draagt zijn ISO-datum, zodat TBD-rijen client-side kunnen
    verouderen (datum-granulair, net als het build-time filter)."""
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert '<tbody data-date="2026-06-21">' in html


def test_tv_guide_channel_logo_and_nl_badge():
    """SPEC §3.3: gematchte rij draagt de tv-gids-div met zenderlogo en evt. NL-badge."""
    from honkbal.tv_guide import TvMatch

    game = _g(date(2026, 6, 21), 20, "Red Sox", "Yankees")
    ts = int(datetime(2026, 6, 21, 20, 5, tzinfo=AMSTERDAM).timestamp())
    lookup = {(ts, "red sox", "yankees"): TvMatch("espn2", True)}
    html = _render([game], tv_lookup=lookup)

    assert '<div class="espn" data-channel="espn2" data-nlcom="1">' in html
    assert '<span class="comm">NL</span>' in html
    assert '<img class="espn2" src="/img/espn/espn2.png?v1" alt="ESPN2" />' in html
    assert 'srcset="/img/espn/espn2-dark.png?v1" media="(prefers-color-scheme: dark)"' in html


def test_tv_guide_absent_without_match():
    """SPEC §3.3: zonder match geen tv-gids-div; zonder NL-commentaar geen badge/attribuut."""
    plain = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert 'class="espn"' not in plain

    from honkbal.tv_guide import TvMatch

    ts = int(datetime(2026, 6, 21, 20, 5, tzinfo=AMSTERDAM).timestamp())
    lookup = {(ts, "red sox", "yankees"): TvMatch("espn", False)}
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")], tv_lookup=lookup)
    assert '<div class="espn" data-channel="espn">' in html
    assert "data-nlcom" not in html
    assert '<span class="comm">' not in html
    # espn heeft in de fixtures geen dark-variant: kale <img>, geen <picture>.
    assert "<picture>" not in html


def test_empty_state_message():
    html = _render([_g(date(2026, 6, 21), 20, "River Cats", "Chihuahuas")])
    assert "Geen wedstrijden beschikbaar 😢" in html


def test_loadmore_button_absent_when_small():
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert 'class="loadmore"' not in html


def test_footnote_exact_wording_when_star_descr():
    """Footnote uses the exact SPEC §5.6 text when a game's descr contains '*'."""
    c = FrozenClock(datetime(2026, 10, 15, 12, tzinfo=AMSTERDAM))
    s = select_active_season(c)
    game_date = date(2026, 10, 14)
    g = Game(date_ams=game_date, time_ams=time(20, 0), hour_ams=20,
             date_et=game_date, away="Yankees", home="Red Sox",
             is_tbd=False, source_seq=0, enrichment=None)
    pd = PostseasonData(
        fetched_at=datetime(2026, 10, 14, 8, tzinfo=AMSTERDAM),
        teams={"NYY": "Yankees", "BOS": "Red Sox"},
        games={(game_date, 20, "Red Sox"): PostseasonGame(
            event_id="1", record="2-1", descr="ALCS Game 5*",
            home="Red Sox", away="Yankees",
        )},
    )
    ctx = build_page_context([g], page="alles", team_slug_q=None, season=s,
                             postseason=pd, clock=c, img_dir=IMG, asset_version="v1")
    inline, tail = split_context(ctx)
    html = render_schedule_page(inline, asset_version="v1", clock=c, season=s,
                                inline_days=inline.days,
                                tail_count=sum(len(d.rows) for d in tail))
    assert "* Wordt alleen gespeeld als nodig." in html
    # Old wording must not appear.
    assert "wedstrijd speelt alleen indien nodig" not in html


def test_footnote_absent_when_no_star():
    """No footnote rendered when no game has a '*' in its descr."""
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert "Wordt alleen gespeeld" not in html


def test_nav_contains_standen_link():
    """Nav includes a 'standen' link to /standings.html."""
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    assert "/standings.html" in html
    assert "standen" in html


def test_nav_standen_not_active_on_schedule_page():
    """'standen' nav item has no active class on a non-standings page."""
    html = _render([_g(date(2026, 6, 21), 20, "Red Sox", "Yankees")])
    # The standen link must not have class="active" on a schedule page.
    assert 'href="/standings.html' in html
    # Find the standen anchor tag and confirm it has no " active" class.
    import re
    match = re.search(r'<a [^>]*href="/standings\.html[^"]*"[^>]*>standen</a>', html)
    assert match is not None, "standen nav link not found"
    assert "active" not in match.group(0)
