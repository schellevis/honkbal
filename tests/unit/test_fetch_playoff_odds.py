import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.fetch.playoff_odds import (
    fetch_playoff_odds,
    load_playoff_odds,
    parse_baseball_reference_playoff_odds,
    parse_fangraphs_playoff_odds,
    parse_playoff_odds,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_playoff_odds_accepts_percent_and_decimal_values():
    odds = parse_playoff_odds({
        "teams": {
            "yankees": {"make_playoffs": "55.5%", "win_division": 0.30},
            "red sox": {"team": "red sox", "make_playoffs": 48, "win_world_series": "3%"},
        }
    })

    assert odds["yankees"].make_playoffs == 0.555
    assert odds["yankees"].win_division == 0.30
    assert odds["red sox"].make_playoffs == 0.48
    assert odds["red sox"].win_world_series == 0.03


def test_load_playoff_odds_reads_optional_cache(tmp_path):
    (tmp_path / "playoff_odds.json").write_text(
        json.dumps({"teams": [{"team": "Dodgers", "make_playoffs": "90%"}]}),
        encoding="utf-8",
    )

    odds = load_playoff_odds(tmp_path)

    assert odds["dodgers"].make_playoffs == 0.9


def test_parse_fangraphs_playoff_odds_normalizes_live_fields():
    payload = json.loads((FIXTURES / "playoff_odds_fangraphs.json").read_text())

    odds = parse_fangraphs_playoff_odds(payload)

    assert odds["yankees"].make_playoffs == pytest.approx(0.994)
    assert odds["yankees"].win_division == 0.825
    assert odds["red sox"].win_world_series == 0.005


def test_parse_baseball_reference_playoff_odds_normalizes_table():
    html = (FIXTURES / "playoff_odds_baseball_reference.html").read_text()

    odds = parse_baseball_reference_playoff_odds(html)

    assert odds["dodgers"].make_playoffs == 1.0
    assert odds["dodgers"].win_division == 0.995
    assert odds["padres"].win_world_series == 0.005


def test_fetch_playoff_odds_writes_fangraphs_cache(tmp_path):
    payload = json.loads((FIXTURES / "playoff_odds_fangraphs.json").read_text())

    def handler(req):
        assert "fangraphs.com/api/playoff-odds/odds" in str(req.url)
        assert "season=2026" in str(req.url)
        assert req.headers["User-Agent"].startswith("Mozilla/5.0")
        return httpx.Response(200, json=payload)

    clock = FrozenClock(datetime(2026, 6, 24, 19, 0, tzinfo=AMSTERDAM))
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_playoff_odds(clock, data_dir=tmp_path, client=client)
    cache = json.loads((tmp_path / "playoff_odds.json").read_text())

    assert result.ok is True
    assert result.source == "fangraphs"
    assert result.count == 2
    assert cache["source"] == "fangraphs"
    assert cache["teams"][1]["team"] == "yankees"


def test_fetch_playoff_odds_falls_back_to_baseball_reference(tmp_path):
    html = (FIXTURES / "playoff_odds_baseball_reference.html").read_text()
    calls = []

    def handler(req):
        calls.append(str(req.url))
        if "fangraphs.com" in str(req.url):
            return httpx.Response(403, text="blocked")
        return httpx.Response(200, text=html)

    clock = FrozenClock(datetime(2026, 6, 24, 19, 0, tzinfo=AMSTERDAM))
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_playoff_odds(clock, data_dir=tmp_path, client=client)
    cache = json.loads((tmp_path / "playoff_odds.json").read_text())

    assert result.ok is True
    assert result.source == "baseball-reference"
    assert result.count == 2
    assert len(calls) == 2
    assert cache["source"] == "baseball-reference"
    assert cache["teams"][0]["team"] == "dodgers"


def test_fetch_playoff_odds_soft_fails_and_keeps_existing_cache(tmp_path):
    cache_path = tmp_path / "playoff_odds.json"
    cache_path.write_text('{"teams": [{"team": "Dodgers", "make_playoffs": "90%"}]}')

    def handler(req):
        if "fangraphs.com" in str(req.url):
            return httpx.Response(500)
        return httpx.Response(200, text="<html>changed schema</html>")

    clock = FrozenClock(datetime(2026, 6, 24, 19, 0, tzinfo=AMSTERDAM))
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_playoff_odds(clock, data_dir=tmp_path, client=client)

    assert result.ok is False
    assert json.loads(cache_path.read_text()) == {
        "teams": [{"team": "Dodgers", "make_playoffs": "90%"}]
    }
