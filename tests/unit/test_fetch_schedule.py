# tests/unit/test_fetch_schedule.py
from datetime import datetime
from pathlib import Path

import httpx

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.fetch.schedule import (
    MIN_SUCCESS,
    FetchResult,
    feed_params,
    fetch_all,
    fetch_schedule,
    write_atomic,
)


def _clock():
    return FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))


def test_feed_params_match_spec():
    p = feed_params(147, 2026, "20260621")
    assert p["team_id"] == 147
    assert p["leave_empty_games"] == "true"
    assert p["event_type"] == "T"
    assert p["begin_date"] == "20260621"
    assert p["year"] == 2026


def test_fetch_all_concatenates_and_counts_success():
    def handler(req):
        return httpx.Response(
            200,
            text=(
                "START DATE,START TIME,START TIME ET,SUBJECT\n"
                "06/01/26,07:05 PM,07:05 PM,Angels at Yankees\n"
            ),
            headers={"Last-Modified": "Sun, 08 Mar 2026 23:05:07 GMT"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    # 26 feeds slagen -> boven de drempel van 24 -> ok is True.
    result = fetch_all(client, _clock(), feed_ids=list(range(101, 127)))
    assert result.success_count == 26
    assert result.ok is True
    assert b"Yankees" in result.csv_bytes
    assert "101" in result.headers


def test_fetch_all_concatenation_preserves_feed_order():
    # source_seq-stabiliteit hangt af van concatenatie in feed_ids-volgorde.
    def handler(req):
        tid = int(req.url.params["team_id"])
        return httpx.Response(
            200,
            text=(
                "START DATE,START TIME,START TIME ET,SUBJECT\n"
                f"06/01/26,07:05 PM,07:05 PM,Angels at Yankees {tid}\n"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_all(client, _clock(), feed_ids=[147, 119, 159])
    assert b"Yankees 147" in result.csv_bytes
    assert result.csv_bytes.index(b"Yankees 147") < result.csv_bytes.index(b"Yankees 119")
    assert result.csv_bytes.index(b"Yankees 119") < result.csv_bytes.index(b"Yankees 159")


def test_fetch_all_below_threshold_not_ok():
    def handler(req):
        return httpx.Response(503)  # alles faalt

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_all(client, _clock(), feed_ids=[147, 119, 159])
    assert result.success_count == 0
    assert result.ok is False


def test_fetch_all_invalid_csv_payload_not_ok_even_above_threshold():
    def handler(req):
        return httpx.Response(200, text="<html>temporary upstream error</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_all(client, _clock(), feed_ids=list(range(101, 127)))
    assert result.success_count == 26
    assert result.ok is False


def test_write_atomic_keeps_cache_when_not_ok(tmp_path: Path):
    csv_path = tmp_path / "all.csv"
    headers_path = tmp_path / "headers.json"
    csv_path.write_bytes(b"GOOD-CACHE")
    headers_path.write_text("{}")

    bad = FetchResult(csv_bytes=b"PARTIAL", headers={}, success_count=1, ok=False)
    wrote = write_atomic(bad, csv_path, headers_path)
    assert wrote is False
    assert csv_path.read_bytes() == b"GOOD-CACHE"  # last-known-good intact (§12.12)


def test_write_atomic_replaces_when_ok(tmp_path: Path):
    csv_path = tmp_path / "all.csv"
    headers_path = tmp_path / "headers.json"
    good = FetchResult(
        csv_bytes=(
            b"START DATE,START TIME,START TIME ET,SUBJECT\n"
            b"06/01/26,07:05 PM,07:05 PM,Angels at Yankees\n"
        ),
        headers={"147": {}},
        success_count=MIN_SUCCESS,
        ok=True,
    )
    assert write_atomic(good, csv_path, headers_path) is True
    assert b"Angels at Yankees" in csv_path.read_bytes()


def test_write_atomic_refuses_invalid_csv_even_when_ok(tmp_path: Path):
    csv_path = tmp_path / "all.csv"
    headers_path = tmp_path / "headers.json"
    csv_path.write_bytes(b"GOOD-CACHE")
    headers_path.write_text("{}")

    bad = FetchResult(
        csv_bytes=b"<html>temporary upstream error</html>",
        headers={"147": {}},
        success_count=MIN_SUCCESS,
        ok=True,
    )
    assert write_atomic(bad, csv_path, headers_path) is False
    assert csv_path.read_bytes() == b"GOOD-CACHE"


def test_fetch_schedule_uses_configured_throttle(tmp_path: Path, monkeypatch):
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

        def get(self, url, params):
            return httpx.Response(
                200,
                text=(
                    "START DATE,START TIME,START TIME ET,SUBJECT\n"
                    "06/01/26,07:05 PM,07:05 PM,Angels at Yankees\n"
                ),
            )

    monkeypatch.setattr("honkbal.fetch.schedule.Throttle", FakeThrottle)
    monkeypatch.setattr("honkbal.fetch.schedule.httpx.Client", lambda **kwargs: FakeClient())

    result = fetch_schedule(_clock(), data_dir=tmp_path)
    assert result.ok is True
    assert calls[0][0] == "init"
    assert any(call == ("wait",) for call in calls)
