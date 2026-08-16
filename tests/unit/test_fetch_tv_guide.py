import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.config.toggles import TV_GUIDE_DAYS
from honkbal.fetch.http import Throttle
from honkbal.fetch.tv_guide import (
    _detect_nl_commentary,
    _looks_like_game,
    _parse_bases_covered_schedule,
    _parse_teams,
    _tz_param,
    fetch_tv_guide,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tv_guide"

CLOCK = FrozenClock(datetime(2026, 8, 5, 21, 0, tzinfo=AMSTERDAM))
EMPTY_ESPN = {"data": {"airings": []}}
NO_THROTTLE = Throttle(0, CLOCK)


def _fetch(tmp_path, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return fetch_tv_guide(CLOCK, data_dir=tmp_path, client=client, throttle=NO_THROTTLE)


@pytest.mark.parametrize(
    ("title", "feed", "expected"),
    [
        ("MLB: Yankees vs Red Sox (NL)", "", True),
        ("MLB: Yankees vs Red Sox ( nl )", "", True),
        ("MLB: Yankees vs Red Sox - Nederlands commentaar", "", True),
        ("MLB: Yankees vs Red Sox, nederlandstalig commentaar", "", True),
        ("MLB: Yankees vs Red Sox NL-commentaar", "", True),
        ("MLB: Yankees vs Red Sox", "NL", True),
        ("MLB: Yankees vs Red Sox", "nl", True),
        ("MLB: Yankees vs Red Sox", "", False),
        ("MLB: NL All-Stars vs AL All-Stars", "", False),
        ("MLB: NL East showdown", "English", False),
    ],
)
def test_detect_nl_commentary_variants(title, feed, expected):
    assert _detect_nl_commentary(title, feed) is expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("MLB: Cubs vs Dodgers", ["cubs", "dodgers"]),
        ("MLB: New York Yankees - Atlanta Braves", ["braves", "yankees"]),
        ("MLB: Guardians vs Tigers Game 2", ["guardians", "tigers"]),
        ("MLB: D-backs vs Giants", ["d-backs", "giants"]),
        ("MLB: Yankees vs Red Sox (NL)", ["red sox", "yankees"]),
        ("MLB: Yankees vs Red Sox - Nederlands commentaar", ["red sox", "yankees"]),
        ("MLB Quick Pitch", []),
        ("Major League Baseball", []),
        ("MLB: Wild Card Game 1", []),
        ("MLB: TBD vs Yankees", []),
    ],
)
def test_parse_teams(title, expected):
    assert _parse_teams(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("MLB: Cubs vs Dodgers", True),
        ("MLB: New York Yankees - Atlanta Braves", True),
        ("MLB: Wild Card", True),
        ("MLB: NLCS Game 1", True),
        ("MLB Postseason", True),
        ("MLB All-Star Game", True),
        ("Major League Baseball", True),
        ("Major League Baseball 2026", True),
        ("MLB Quick Pitch", False),
        ("MLB Plays of the Week", False),
        ("MLB Bases Covered Live", True),
        ("MLB bases covered live", True),
    ],
)
def test_looks_like_game(title, expected):
    assert _looks_like_game(title) is expected


BASES_COVERED_AIRING = {
    "data": {
        "airings": [
            {
                "id": "bc1",
                "name": "MLB Bases Covered Live",
                "type": "UPCOMING",
                "startDateTime": "2026-08-09T17:30:00Z",
                "endDateTime": "2026-08-09T20:35:00Z",
                "feedName": None,
                "network": {"abbreviation": "nl_espn4", "name": "ESPN4"},
                "subcategory": {"name": "MLB"},
                "league": {"name": "MLB"},
            }
        ]
    }
}


def test_parse_bases_covered_schedule():
    html = (FIXTURES / "bases_covered.html").read_text()

    schedule = _parse_bases_covered_schedule(html, 2026)

    # "Final Day - TBC" en "Plus two Postseason doubleheaders" zijn geen teamparen.
    assert schedule == {
        "2026-08-02": ["cubs", "yankees"],
        "2026-08-09": ["blue jays", "phillies"],
        "2026-08-16": ["blue jays", "yankees"],
    }


def test_fetch_tv_guide_fills_bases_covered_teams_from_mlb_com(tmp_path):
    mlb_calls = []

    def handler(req):
        if req.url.host == "www.mlb.com":
            mlb_calls.append(req.url.path)
            return httpx.Response(200, text=(FIXTURES / "bases_covered.html").read_text())
        variables = json.loads(req.url.params["variables"])
        if variables["day"] == "2026-08-09":
            return httpx.Response(200, json=BASES_COVERED_AIRING)
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)
    cache = json.loads((tmp_path / "tv_guide.json").read_text())

    assert result.ok is True
    assert mlb_calls == ["/international/europe/bases-covered-live"]
    (airing,) = cache["airings"]
    assert airing["title"] == "MLB Bases Covered Live"
    assert airing["channel"] == "espn4"
    # Hoofdwedstrijd van zondag 9 augustus volgens de MLB.com-pagina.
    assert airing["teams"] == ["blue jays", "phillies"]


def test_fetch_tv_guide_bases_covered_soft_fails_without_mlb_page(tmp_path):
    def handler(req):
        if req.url.host == "www.mlb.com":
            return httpx.Response(500)
        variables = json.loads(req.url.params["variables"])
        if variables["day"] == "2026-08-09":
            return httpx.Response(200, json=BASES_COVERED_AIRING)
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)
    cache = json.loads((tmp_path / "tv_guide.json").read_text())

    assert result.ok is True
    (airing,) = cache["airings"]
    assert airing["teams"] == []


def test_fetch_tv_guide_writes_espn_cache(tmp_path):
    payload = json.loads((FIXTURES / "espn_airings.json").read_text())
    days = []

    def handler(req):
        assert req.url.host == "watch.graph.api.espn.com"
        assert req.url.params["apiKey"] == "0dbf88e8-cc6d-41da-aa83-18b5c630bc5c"
        variables = json.loads(req.url.params["variables"])
        assert variables["countryCode"] == "NL"
        assert variables["tz"] == "UTC+0200"
        days.append(variables["day"])
        if variables["day"] == "2026-08-06":
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)
    cache = json.loads((tmp_path / "tv_guide.json").read_text())

    assert result.ok is True
    assert result.source == "espn"
    assert days == [
        (datetime(2026, 8, 5) + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(TV_GUIDE_DAYS)
    ]
    assert cache["source"] == "espn"

    airings = cache["airings"]
    # a4 ("MLB Quick Pitch") is een magazineprogramma, a5 zit op ESPN Extra (bewust weggelaten)
    # en a6 ("Eredivisie: Ajax vs PSV") is geen MLB: alle drie vallen weg.
    assert [a["title"] for a in airings] == [
        "MLB: Cubs vs Dodgers",
        "MLB: Cubs vs Dodgers",
        "MLB: Yankees vs Red Sox (NL)",
    ]

    game, replay, nl_game = airings
    assert game["channel"] == "espn4"
    assert game["start"] == "2026-08-06T02:40:00+02:00"  # UTC -> Amsterdam
    assert game["end"] == "2026-08-06T05:40:00+02:00"
    assert game["teams"] == ["cubs", "dodgers"]
    assert game["nl_commentary"] is False
    assert game["live"] is True

    assert replay["channel"] == "espn3"
    assert replay["live"] is False

    assert nl_game["channel"] == "espn2"
    assert nl_game["teams"] == ["red sox", "yankees"]
    assert nl_game["nl_commentary"] is True


def test_fetch_tv_guide_uses_each_days_dst_offset(tmp_path):
    clock = FrozenClock(datetime(2026, 3, 28, 12, 0, tzinfo=AMSTERDAM))
    offsets = []

    def handler(req):
        variables = json.loads(req.url.params["variables"])
        offsets.append((variables["day"], variables["tz"]))
        return httpx.Response(200, json=EMPTY_ESPN)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_tv_guide(
        clock,
        data_dir=tmp_path,
        client=client,
        throttle=Throttle(0, clock),
    )

    assert result.ok is True
    expected_days = [clock.now() + timedelta(days=i) for i in range(TV_GUIDE_DAYS)]
    assert offsets == [(day.date().isoformat(), _tz_param(day)) for day in expected_days]
    # Kruist de DST-overgang van 2026-03-29: offset springt van +0100 naar +0200.
    assert offsets[0][1] == "UTC+0100"
    assert offsets[1][1] == "UTC+0200"


def test_fetch_tv_guide_prefers_discovered_api_key(tmp_path):
    (tmp_path / "espn_watch_config.json").write_text(
        json.dumps({"apiKey": "sleutel-uit-config"})
    )
    keys = []

    def handler(req):
        keys.append(req.url.params["apiKey"])
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)

    assert result.ok is True
    assert set(keys) == {"sleutel-uit-config"}


def test_fetch_tv_guide_ignores_corrupt_api_key_config(tmp_path):
    (tmp_path / "espn_watch_config.json").write_text("{kapot")
    keys = []

    def handler(req):
        keys.append(req.url.params["apiKey"])
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)

    assert result.ok is True
    assert set(keys) == {"0dbf88e8-cc6d-41da-aa83-18b5c630bc5c"}


def test_fetch_tv_guide_falls_back_to_tvgids(tmp_path):
    payload = json.loads((FIXTURES / "tvgids_programs_dict.json").read_text())
    tvgids_days = []

    def handler(req):
        if req.url.host == "watch.graph.api.espn.com":
            return httpx.Response(500)
        assert req.url.host == "json.tvgids.nl"
        assert req.url.params["channels"] == "148,468,469,470"
        tvgids_days.append(req.url.params["day"])
        if req.url.params["day"] == "0":
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json={"data": {}})

    result = _fetch(tmp_path, handler)
    cache = json.loads((tmp_path / "tv_guide.json").read_text())

    assert result.ok is True
    assert result.source == "tvgids"
    assert tvgids_days == [str(i) for i in range(TV_GUIDE_DAYS)]

    airings = cache["airings"]
    # "MLB Quick pitch" is geen wedstrijd en valt weg.
    assert len(airings) == 2
    named, generic = airings
    assert named["channel"] == "espn"
    assert named["start"] == "2026-08-06T01:00:00+02:00"  # epoch -> Amsterdam
    assert named["teams"] == ["braves", "yankees"]
    assert named["live"] is True
    assert named["nl_commentary"] is False

    assert generic["channel"] == "espn3"
    assert generic["teams"] == []
    assert generic["title"] == "Major League Baseball"


def test_fetch_tv_guide_handles_tvgids_list_shape(tmp_path):
    payload = json.loads((FIXTURES / "tvgids_programs_list.json").read_text())

    def handler(req):
        if req.url.host == "watch.graph.api.espn.com":
            return httpx.Response(500)
        if req.url.params["day"] == "0":
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json={"data": {}})

    result = _fetch(tmp_path, handler)
    cache = json.loads((tmp_path / "tv_guide.json").read_text())

    assert result.ok is True
    # ch_id 999 is geen ESPN-kanaal en valt weg.
    assert len(cache["airings"]) == 1
    assert cache["airings"][0]["channel"] == "espn2"
    assert cache["airings"][0]["teams"] == ["cardinals", "cubs"]


def test_fetch_tv_guide_soft_fails_and_keeps_existing_cache(tmp_path):
    cache_path = tmp_path / "tv_guide.json"
    cache_path.write_text('{"airings": [{"channel": "espn2"}]}')

    def handler(req):
        return httpx.Response(500)

    result = _fetch(tmp_path, handler)

    assert result.ok is False
    assert json.loads(cache_path.read_text()) == {"airings": [{"channel": "espn2"}]}


def test_fetch_tv_guide_skips_malformed_network_object(tmp_path):
    malformed = {
        "data": {
            "airings": [
                {
                    "name": "MLB: Cubs vs Dodgers",
                    "type": "UPCOMING",
                    "startDateTime": "2026-08-06T00:40:00Z",
                    "network": "nl_espn2",
                }
            ]
        }
    }

    def handler(req):
        return httpx.Response(200, json=malformed)

    result = _fetch(tmp_path, handler)

    assert result.ok is True
    assert json.loads((tmp_path / "tv_guide.json").read_text())["airings"] == []


def test_fetch_tv_guide_malformed_previous_cache_does_not_break_fetch(tmp_path):
    (tmp_path / "tv_guide.json").write_text("[]")

    def handler(req):
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)

    assert result.ok is True
    assert json.loads((tmp_path / "tv_guide.json").read_text())["airings"] == []


def test_fetch_tv_guide_atomic_write_failure_keeps_existing_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "tv_guide.json"
    original = '{"airings": [{"channel": "espn2"}]}'
    cache_path.write_text(original)

    def handler(req):
        return httpx.Response(200, json=EMPTY_ESPN)

    def fail_replace(src, dst):
        raise OSError("schijf niet beschikbaar")

    monkeypatch.setattr(os, "replace", fail_replace)
    result = _fetch(tmp_path, handler)

    assert result.ok is False
    assert cache_path.read_text() == original
    assert not (tmp_path / "tv_guide.json.tmp").exists()


def test_fetch_tv_guide_carries_over_running_airings(tmp_path):
    running = {
        "channel": "espn2",
        "start": "2026-08-05T20:00:00+02:00",
        "end": None,
        "teams": ["cubs", "dodgers"],
        "nl_commentary": False,
        "live": True,
        "title": "MLB: Cubs vs Dodgers",
    }
    stale = dict(running, channel="espn", start="2026-08-05T14:00:00+02:00")
    duplicate = dict(running, channel="espn3", start="2026-08-05T20:58:00+02:00")
    (tmp_path / "tv_guide.json").write_text(
        json.dumps({"airings": [running, stale, duplicate]})
    )

    fresh = {
        "data": {
            "airings": [
                {
                    "id": "n1",
                    "name": "MLB: Mets vs Phillies",
                    "type": "UPCOMING",
                    "startDateTime": "2026-08-05T19:00:00Z",
                    "endDateTime": None,
                    "feedName": None,
                    "network": {"abbreviation": "nl_espn3", "name": "ESPN3"},
                    "subcategory": {"name": "MLB"},
                }
            ]
        }
    }

    def handler(req):
        variables = json.loads(req.url.params["variables"])
        if variables["day"] == "2026-08-05":
            return httpx.Response(200, json=fresh)
        return httpx.Response(200, json=EMPTY_ESPN)

    result = _fetch(tmp_path, handler)
    cache = json.loads((tmp_path / "tv_guide.json").read_text())

    assert result.ok is True
    starts = [(a["channel"], a["start"]) for a in cache["airings"]]
    # Nieuwe airing + lopende carry-over; de verouderde (14:00) en de dubbele (espn3 20:58,
    # binnen 5 min van de nieuwe espn3 21:00) blijven weg.
    assert starts == [
        ("espn2", "2026-08-05T20:00:00+02:00"),
        ("espn3", "2026-08-05T21:00:00+02:00"),
    ]
