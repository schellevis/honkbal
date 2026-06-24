# tests/unit/test_discover_feeds.py
from pathlib import Path

from honkbal.fetch.discover_feeds import classify_feed, discover

FIX = Path(__file__).parent.parent / "fixtures" / "discover"

FEEDS = {
    147: FIX / "feed_147.csv",  # Yankees (mlb)
    119: FIX / "feed_119.csv",  # Dodgers (mlb)
    159: FIX / "feed_159.csv",  # all-star
    112: FIX / "feed_112.csv",  # affiliate
    160: FIX / "feed_160.csv",  # empty
}


def _fetch_one(team_id: int) -> bytes:
    return FEEDS[team_id].read_bytes()


def test_classify_mlb():
    name, kind = classify_feed(FEEDS[147].read_bytes())
    assert kind == "mlb" and name == "yankees"


def test_classify_allstar():
    _, kind = classify_feed(FEEDS[159].read_bytes())
    assert kind == "allstar"


def test_classify_affiliate():
    name, kind = classify_feed(FEEDS[112].read_bytes())
    assert kind == "affiliate" and name is None


def test_classify_empty():
    name, kind = classify_feed(FEEDS[160].read_bytes())
    assert kind == "empty" and name is None


def test_discover_builds_mapping():
    result = discover(_fetch_one, team_ids=FEEDS.keys())
    assert result["team_feeds"]["yankees"] == 147
    assert result["team_feeds"]["dodgers"] == 119
    assert result["allstar_feed_id"] == 159
    assert 112 in result["affiliate"]
    assert 160 in result["empty"]
    # de afgeleide mapping bevat geen affiliate/empty ids
    assert 112 not in result["team_feeds"].values()
