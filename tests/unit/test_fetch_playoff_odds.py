import json

from honkbal.fetch.playoff_odds import load_playoff_odds, parse_playoff_odds


def test_parse_playoff_odds_accepts_percent_and_decimal_values():
    odds = parse_playoff_odds({
        "teams": {
            "yankees": {"make_playoffs": "55.5%", "win_division": 0.30},
            "red sox": {"team": "red sox", "make_playoffs": 48, "win_world_series": "3%"},
        }
    })

    assert odds["yankees"].make_playoffs == 0.555
    assert odds["yankees"].win_division == 0.30
    assert odds["red sox"].make_playoffs == 0.48
    assert odds["red sox"].win_world_series == 0.03


def test_load_playoff_odds_reads_optional_cache(tmp_path):
    (tmp_path / "playoff_odds.json").write_text(
        json.dumps({"teams": [{"team": "Dodgers", "make_playoffs": "90%"}]}),
        encoding="utf-8",
    )

    odds = load_playoff_odds(tmp_path)

    assert odds["dodgers"].make_playoffs == 0.9
