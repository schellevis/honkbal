from datetime import datetime

import httpx

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.fetch.standings import fetch_standings, load_standings, parse_standings


def _payload():
    return {
        "records": [
            {
                "teamRecords": [
                    {
                        "team": {"name": "New York Yankees"},
                        "wins": 50,
                        "losses": 31,
                        "winningPercentage": ".617",
                        "divisionRank": "1",
                        "gamesBack": "-",
                        "wildCardGamesBack": "+2.0",
                        "runDifferential": 80,
                        "streak": {"streakCode": "W3"},
                        "records": {
                            "splitRecords": [
                                {"type": "lastTen", "wins": 7, "losses": 3}
                            ]
                        },
                    },
                    {
                        "team": {"name": "Boston Red Sox"},
                        "wins": 44,
                        "losses": 38,
                        "winningPercentage": ".537",
                        "divisionRank": "2",
                        "gamesBack": "6.5",
                        "wildCardGamesBack": "1.0",
                        "runDifferential": 20,
                    },
                ]
            }
        ]
    }


def test_parse_standings_normalizes_mlb_stats_payload():
    standings = parse_standings(_payload())

    assert standings["yankees"].winning_percentage == 0.617
    assert standings["yankees"].games_back == 0.0
    assert standings["yankees"].wild_card_games_back == 2.0
    assert standings["yankees"].last_ten == "7-3"
    assert standings["red sox"].division_rank == 2


def test_fetch_standings_writes_cache_and_loads_it(tmp_path):
    def handler(req):
        assert "season=2026" in str(req.url)
        return httpx.Response(200, json=_payload())

    clock = FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_standings(clock, data_dir=tmp_path, client=client)
    loaded = load_standings(tmp_path)

    assert result.ok is True
    assert result.count == 2
    assert loaded["yankees"].streak == "W3"
