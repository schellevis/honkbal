# tests/unit/test_fetch_espn.py
import json
from datetime import datetime
from pathlib import Path

import httpx

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.fetch.espn_postseason import (
    cache_is_fresh,
    fetch_postseason,
    fetch_summaries,
    refresh_postseason,
)
from honkbal.parse.espn_postseason import parse_postseason

FIX = Path(__file__).parent.parent / "fixtures" / "espn"


def _clock():
    return FrozenClock(datetime(2026, 10, 1, 12, 0, tzinfo=AMSTERDAM))


def test_cache_fresh_within_espncap_seconds():
    now_epoch = _clock().now().timestamp()
    assert cache_is_fresh(now_epoch - 100, _clock(), espncap=3000) is True   # 100s < 3000s
    assert cache_is_fresh(now_epoch - 4000, _clock(), espncap=3000) is False  # 4000s > 3000s
    assert cache_is_fresh(None, _clock()) is False  # geen cache -> verversen


def test_refresh_returns_none_when_cache_fresh():
    def handler(req):  # mag nooit geraakt worden
        raise AssertionError("geen netwerk verwacht bij verse cache")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fresh = _clock().now().timestamp() - 10
    assert refresh_postseason(client, _clock(), Path("/unused"), parsed_at_epoch=fresh) is None


def test_fetch_summaries_uses_disk_cache(tmp_path: Path):
    schedule = json.loads((FIX / "schedule_two_teams.json").read_text())
    # leg de summary alvast op schijf -> geen netwerk nodig
    (tmp_path / "401809252.json").write_text((FIX / "summary_tied.json").read_text())

    def handler(req):
        raise AssertionError("summary stond al in cache; geen fetch verwacht")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = fetch_summaries(client, schedule, _clock(), tmp_path)
    assert out["401809252"]["seasonseries"][0]["summary"] == "Series tied 1-1"


# --- I1: malformed ESPN payload -> geen crash, build gaat door (SPEC §9/§3.5) ---


def test_parse_postseason_skips_malformed_events_no_crash():
    # Events zonder competition.date, zonder team-objecten, met verkeerde types:
    # mag NIET crashen; malformede events worden overgeslagen.
    malformed = [
        {"team": {"recordSummary": "1-0"}, "events": [
            {"id": 1, "competitions": [{"competitors": []}]},          # geen date
            {"id": 2, "competitions": [{"date": "kapot", "competitors": []}]},  # ongeldige date
            "niet-een-dict",                                            # rare entry
        ]},
        "ook-geen-dict",
    ]
    ps = parse_postseason(malformed, {}, _clock())
    assert ps.games == {}  # niets geparsed, maar geen exception


def test_fetch_postseason_sets_ok_false_on_fetch_error(tmp_path: Path, monkeypatch):
    # refresh_postseason gooit -> fetch_postseason vangt het en zet ok=False
    # (zodat cli_fetch de waarschuwing toont i.p.v. de build te laten crashen).
    def boom(*args, **kwargs):
        raise RuntimeError("ESPN onbereikbaar")

    monkeypatch.setattr("honkbal.fetch.espn_postseason.refresh_postseason", boom)
    res = fetch_postseason(_clock(), data_dir=tmp_path)
    assert res.ok is False
    assert res.count == 0


def test_fetch_postseason_graceful_with_malformed_schedule(tmp_path: Path, monkeypatch):
    # End-to-end: een schedule-respons met malformede events -> geen crash, ok=True,
    # 0 games geparsed (alles overgeslagen). Build-stap gaat door.
    malformed_schedule = json.dumps({"events": [{"id": 9, "competitions": [{}]}]})

    def handler(req):
        return httpx.Response(200, text=malformed_schedule)

    import honkbal.fetch.espn_postseason as mod

    orig_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs.pop("timeout", None)
        return orig_client(transport=httpx.MockTransport(handler))

    class NoopThrottle:
        def __init__(self, seconds, clock):
            pass

        def wait(self):
            pass

    monkeypatch.setattr("honkbal.fetch.espn_postseason.Throttle", NoopThrottle)

    # Patch the Client used inside fetch_postseason to use our MockTransport.
    import unittest.mock as m

    with m.patch.object(mod.httpx, "Client", fake_client):
        res = fetch_postseason(_clock(), data_dir=tmp_path)
    assert res.ok is True
    assert res.count == 0


def test_fetch_postseason_uses_configured_throttle(tmp_path: Path, monkeypatch):
    calls = []

    class FakeThrottle:
        def __init__(self, seconds, clock):
            calls.append(("init", seconds, clock.now()))

        def wait(self):
            calls.append(("wait",))

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, params=None):
            return httpx.Response(200, json={"events": []})

    monkeypatch.setattr("honkbal.fetch.espn_postseason.Throttle", FakeThrottle)
    monkeypatch.setattr("honkbal.fetch.espn_postseason.httpx.Client", lambda **kwargs: FakeClient())

    res = fetch_postseason(_clock(), data_dir=tmp_path)
    assert res.ok is True
    assert calls[0][0] == "init"
    assert any(call == ("wait",) for call in calls)
