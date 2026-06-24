from __future__ import annotations

import time as _time
from collections.abc import Callable

import httpx

from honkbal.clock import Clock
from honkbal.config.toggles import GRAB_NO_WAIT


def build_client(
    transport: httpx.BaseTransport | None = None, timeout: float = 30.0
) -> httpx.Client:
    return httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)


class Throttle:
    def __init__(self, seconds: float, clock: Clock, sleep: Callable[[float], None] = _time.sleep):
        # `clock` blijft in de signatuur voor injectie-consistentie met andere fetchers, maar de
        # throttle gebruikt alleen `sleep`; we bewaren de clock niet (was dead field).
        self._seconds = seconds
        self._sleep = sleep

    def wait(self) -> None:
        if GRAB_NO_WAIT or self._seconds <= 0:
            return
        self._sleep(self._seconds)
