from datetime import datetime

import pytest

from honkbal.clock import AMSTERDAM, UTC, FrozenClock, SystemClock


def test_frozen_clock_returns_fixed_moment():
    moment = datetime(2026, 4, 8, 19, 30, tzinfo=AMSTERDAM)
    clock = FrozenClock(moment)
    assert clock.now() == moment
    assert clock.now().tzinfo is AMSTERDAM


def test_frozen_clock_normalizes_utc_to_amsterdam():
    # 17:30 UTC op 8 april = 19:30 CEST (UTC+2)
    clock = FrozenClock(datetime(2026, 4, 8, 17, 30, tzinfo=UTC))
    assert clock.now().tzinfo is AMSTERDAM
    assert clock.now().hour == 19
    assert clock.now() == datetime(2026, 4, 8, 17, 30, tzinfo=UTC)  # zelfde instant


def test_frozen_clock_dst_boundary():
    # Winter: 12:00 UTC op 1 jan = 13:00 CET (UTC+1)
    clock = FrozenClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    assert clock.now().hour == 13


def test_frozen_clock_rejects_naive():
    with pytest.raises(ValueError):
        FrozenClock(datetime(2026, 4, 8, 19, 30))


def test_system_clock_is_amsterdam_aware():
    assert SystemClock().now().tzinfo is AMSTERDAM
