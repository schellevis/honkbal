from __future__ import annotations

from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=AMSTERDAM)


class FrozenClock:
    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("FrozenClock vereist een tz-aware datetime")
        # Normaliseer naar Amsterdam zodat now() altijd Amsterdam-aware is (contract).
        self._moment = moment.astimezone(AMSTERDAM)

    def now(self) -> datetime:
        return self._moment
