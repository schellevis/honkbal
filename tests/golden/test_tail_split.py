from datetime import date, datetime, time, timedelta
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.models import Game
from honkbal.render.context import build_page_context
from honkbal.render.tail import build_tail_json, split_context
from honkbal.season import select_active_season

IMG = Path(__file__).parent.parent / "fixtures" / "img"


def _clock():
    return FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))


def _ctx(games, page="alles"):
    c = _clock()
    return build_page_context(games, page=page, team_slug_q=None,
                              season=select_active_season(c), postseason=None,
                              clock=c, img_dir=IMG, asset_version="v1")


def _many(n, *, per_day):
    games, made, day = [], 0, date(2026, 6, 21)
    while made < n:
        for h in range(per_day):
            if made >= n:
                break
            hour = 14 + (h % 9)
            games.append(Game(date_ams=day, time_ams=time(hour, made % 60), hour_ams=hour,
                              date_et=day, away="Red Sox", home="Yankees",
                              is_tbd=False, source_seq=made, enrichment=None))
            made += 1
        day = day + timedelta(days=1)
    return games


def test_inline_exactly_250_rest_to_tail():
    games = _many(251, per_day=10)
    ctx = _ctx(games)
    inline, remaining = split_context(ctx)
    inline_rows = sum(len(d.rows) for d in inline.days)
    tail_rows = sum(len(d.rows) for d in remaining)
    assert inline_rows == 250
    assert tail_rows == 1
    assert inline_rows + tail_rows == 251


def test_tail_json_shape_and_block_count():
    games = _many(750, per_day=10)
    ctx = _ctx(games)
    inline, remaining = split_context(ctx)
    tail = build_tail_json(remaining, page="alles", asset_version="v1", total=750,
                           last_inline_date=inline.last_inline_date)
    assert tail["version"] == "v1"
    assert tail["page"] == "alles"
    assert tail["total"] == 750
    assert tail["batch_size"] == 250
    assert len(tail["blocks"]) == 2
    assert all(isinstance(b, str) for b in tail["blocks"])


def test_block_starting_new_day_gets_header_continuation_does_not():
    games = _many(260, per_day=10)
    ctx = _ctx(games)
    inline, remaining = split_context(ctx)
    tail = build_tail_json(remaining, page="alles", asset_version="v1", total=260,
                           last_inline_date=inline.last_inline_date)
    block0 = tail["blocks"][0]
    assert "<thead" in block0
    assert "juni" in block0 or "juli" in block0


def test_continuation_block_no_duplicate_header():
    games = _many(400, per_day=400)
    ctx = _ctx(games)
    inline, remaining = split_context(ctx)
    tail = build_tail_json(remaining, page="alles", asset_version="v1", total=400,
                           last_inline_date=inline.last_inline_date)
    assert sum(len(d.rows) for d in inline.days) == 250
    block0 = tail["blocks"][0]
    assert "<thead" not in block0
