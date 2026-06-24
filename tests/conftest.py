from datetime import datetime

import pytest

from honkbal.clock import AMSTERDAM, FrozenClock


@pytest.fixture
def frozen_clock():
    def _make(year, month, day, hour=12, minute=0):
        return FrozenClock(datetime(year, month, day, hour, minute, tzinfo=AMSTERDAM))

    return _make
