from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


class Enrichment(BaseModel):
    """Interessantheidsscore voor uitgelichte reguliere-seizoenwedstrijden."""

    model_config = ConfigDict(frozen=True)

    score: float
    label: str
    reasons: tuple[str, ...] = ()


class Game(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_ams: date
    time_ams: time | None
    hour_ams: int | None
    date_et: date
    away: str
    home: str
    is_tbd: bool
    source_seq: int
    enrichment: Enrichment | None = None

    @property
    def sort_key(self) -> tuple[date, int, time, int]:
        # TBD achteraan binnen de dag; daarna oplopend op tijd; source_seq als tiebreaker.
        return (
            self.date_ams,
            1 if self.is_tbd else 0,
            self.time_ams or time.min,
            self.source_seq,
        )


class ScheduleMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    modified: datetime
    refreshed: datetime


class PostseasonGame(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    record: str | None = None
    descr: str
    home: str
    away: str
    standing: str | None = None


class PostseasonData(BaseModel):
    model_config = ConfigDict(frozen=True)

    fetched_at: datetime
    teams: dict[str, str]
    games: dict[tuple[date, int, str], PostseasonGame]


def sort_games(games: Iterable[Game]) -> list[Game]:
    return sorted(games, key=lambda g: g.sort_key)
