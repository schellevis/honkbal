from datetime import date, datetime, time
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Enrichment, Game, PostseasonData, PostseasonGame
from honkbal.render.context import build_page_context, default_tab
from honkbal.season import select_active_season

IMG = Path(__file__).parent.parent / "fixtures" / "img"


def _g(d, hour, away, home, tbd=False, seq=0, et=None, enrichment=None):
    return Game(date_ams=d, time_ams=None if tbd else time(hour, 5),
                hour_ams=None if tbd else hour, date_et=et or d, away=away, home=home,
                is_tbd=tbd, source_seq=seq, enrichment=enrichment)


def _season(c):
    return select_active_season(c)


def _ctx(games, page="alles", **kw):
    c = kw.pop("clock", FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM)))
    return build_page_context(
        games, page=page, team_slug_q=kw.pop("team_slug_q", None),
        season=_season(c), postseason=kw.pop("postseason", None), clock=c,
        img_dir=IMG, asset_version="v1",
    )


def test_default_tab_avond_before_ps():
    c = FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))
    assert default_tab(season=_season(c), clock=c) == "avond"


def test_default_tab_alles_in_postseason():
    c = FrozenClock(datetime(2026, 10, 10, 12, tzinfo=AMSTERDAM))
    assert default_tab(season=_season(c), clock=c) == "alles"


def test_groups_by_day_and_orders():
    games = [
        _g(date(2026, 6, 21), 20, "Red Sox", "Yankees"),
        _g(date(2026, 6, 21), 22, "Mets", "Cubs"),
        _g(date(2026, 6, 22), 19, "Dodgers", "Giants"),
    ]
    ctx = _ctx(games)
    assert len(ctx.days) == 2
    assert ctx.days[0].header_label == "vandaag, 21 juni"
    assert len(ctx.days[0].rows) == 2
    assert ctx.days[0].rows[0].away_slug == "red sox"
    assert ctx.total_rows == 3
    assert ctx.is_empty is False


def test_empty_state():
    ctx = _ctx([_g(date(2026, 6, 21), 20, "River Cats", "Chihuahuas")])
    assert ctx.is_empty is True
    assert ctx.total_rows == 0


def test_tbd_time_label():
    games = [_g(date(2026, 6, 21), 0, "Mets", "Cubs", tbd=True)]
    ctx = _ctx(games, page="alles")
    assert ctx.days[0].rows[0].time_label == "TBD"


def test_enrichment_does_not_break_render():
    enr = Enrichment(score=0.9, label="must-watch", reasons=["rivalry"])
    games = [_g(date(2026, 6, 21), 20, "Red Sox", "Yankees", enrichment=enr)]
    ctx = _ctx(games)
    assert ctx.total_rows == 1
    row = ctx.days[0].rows[0]
    assert row.enrichment_score == 0.9
    assert row.enrichment_label == "must-watch"
    assert row.enrichment_reasons == ("rivalry",)


# --- Postseason footnote tests (SPEC §5.6) ---

def _ps_clock():
    """Clock pinned to mid-postseason 2026."""
    return FrozenClock(datetime(2026, 10, 15, 12, tzinfo=AMSTERDAM))


def _ps_game(d=date(2026, 10, 14), hour=20):
    return Game(
        date_ams=d, time_ams=time(hour, 0), hour_ams=hour, date_et=d,
        away="Yankees", home="Red Sox", is_tbd=False, source_seq=0, enrichment=None,
    )


def _make_postseason(descr: str) -> PostseasonData:
    """Build a minimal PostseasonData with one game whose descr is given."""
    return PostseasonData(
        fetched_at=datetime(2026, 10, 14, 8, tzinfo=AMSTERDAM),
        teams={"NYY": "Yankees", "BOS": "Red Sox"},
        games={
            (date(2026, 10, 14), 20, "Red Sox"): PostseasonGame(
                event_id="1", record="2-1", descr=descr,
                home="Red Sox", away="Yankees",
            )
        },
    )


def test_footnote_present_when_descr_contains_star():
    """has_postseason_footnote is True when an inline game's descr contains '*'."""
    c = _ps_clock()
    pd = _make_postseason("ALCS Game 1*")
    ctx = build_page_context(
        [_ps_game()], page="alles", team_slug_q=None,
        season=select_active_season(c), postseason=pd,
        clock=c, img_dir=IMG, asset_version="v1",
    )
    assert ctx.has_postseason_footnote is True


def test_footnote_absent_when_no_star_in_descr():
    """has_postseason_footnote is False when postseason data is present but no '*' in descr."""
    c = _ps_clock()
    pd = _make_postseason("ALDS Game 2")  # no star
    ctx = build_page_context(
        [_ps_game()], page="alles", team_slug_q=None,
        season=select_active_season(c), postseason=pd,
        clock=c, img_dir=IMG, asset_version="v1",
    )
    assert ctx.has_postseason_footnote is False


def test_footnote_absent_when_postseason_but_date_derived_label():
    """Footnote absent when postseason present but no ESPN match — date-derived label, no star."""
    c = _ps_clock()
    # PostseasonData with an entry for a different game so there's no ESPN match for our game.
    pd = PostseasonData(
        fetched_at=datetime(2026, 10, 14, 8, tzinfo=AMSTERDAM),
        teams={},
        games={},  # no ESPN matches at all
    )
    ctx = build_page_context(
        [_ps_game()], page="alles", team_slug_q=None,
        season=select_active_season(c), postseason=pd,
        clock=c, img_dir=IMG, asset_version="v1",
    )
    # date-derived label ("ALCS") has no "*", so no footnote
    assert ctx.has_postseason_footnote is False


def test_footnote_counts_tail_rows():
    """Footnote True even when the '*' game is only in the tail (beyond inline limit)."""
    from honkbal.config.toggles import SHOW_GAMES
    from honkbal.render.tail import split_context

    c = _ps_clock()
    # Create more than SHOW_GAMES non-star games, then one star game at the end (in the tail).
    non_star_pd_games = {}
    non_star_games: list[Game] = []
    for i in range(SHOW_GAMES):
        # Use different hours (cycle 0–23) and days to pack them in.
        day_offset = i // 20
        hour = 14 + (i % 6)
        game_date = date(2026, 10, 14 + day_offset)
        g = Game(
            date_ams=game_date, time_ams=time(hour, i % 60), hour_ams=hour,
            date_et=game_date, away="Yankees", home="Red Sox",
            is_tbd=False, source_seq=i, enrichment=None,
        )
        non_star_games.append(g)
        # Provide a non-star ESPN descr for each non-star game.
        non_star_pd_games[(game_date, hour, "Red Sox")] = PostseasonGame(
            event_id=str(i), record=None, descr="ALCS Game 1",
            home="Red Sox", away="Yankees",
        )

    # The tail game has a "*" descr.
    tail_date = date(2026, 10, 30)
    tail_game = Game(
        date_ams=tail_date, time_ams=time(20, 0), hour_ams=20,
        date_et=tail_date, away="Yankees", home="Red Sox",
        is_tbd=False, source_seq=SHOW_GAMES, enrichment=None,
    )
    non_star_pd_games[(tail_date, 20, "Red Sox")] = PostseasonGame(
        event_id="999", record="3-2", descr="ALCS Game 7*",
        home="Red Sox", away="Yankees",
    )

    pd = PostseasonData(
        fetched_at=datetime(2026, 10, 14, 8, tzinfo=AMSTERDAM),
        teams={"NYY": "Yankees", "BOS": "Red Sox"},
        games=non_star_pd_games,
    )

    all_games = non_star_games + [tail_game]
    ctx = build_page_context(
        all_games, page="alles", team_slug_q=None,
        season=select_active_season(c), postseason=pd,
        clock=c, img_dir=IMG, asset_version="v1",
    )
    inline_ctx, remaining = split_context(ctx)
    # The tail game with "*" is beyond the inline limit.
    assert sum(len(d.rows) for d in remaining) >= 1
    # But the footnote must still be True on the page context.
    assert ctx.has_postseason_footnote is True
