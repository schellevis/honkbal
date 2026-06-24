# tests/unit/test_fetch_http.py
from datetime import datetime

import httpx

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.fetch.http import Throttle, build_client


def test_throttle_sleeps_configured_seconds():
    calls = []
    t = Throttle(2.0, FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM)),
                 sleep=calls.append)
    t.wait()
    assert calls == [2.0]


def test_throttle_noop_when_zero():
    calls = []
    t = Throttle(0, FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM)),
                 sleep=calls.append)
    t.wait()
    assert calls == []


def test_build_client_uses_transport():
    def handler(req):
        return httpx.Response(200, text="ok")

    client = build_client(transport=httpx.MockTransport(handler))
    assert client.get("https://example.test/").text == "ok"
