from datetime import date, datetime, time

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.enrichment import TeamPlayoffOdds, TeamStanding, enrich_games, score_game
from honkbal.models import Game
from honkbal.season import select_active_season


def _game(away="yankees", home="red sox"):
    return Game(
        date_ams=date(2026, 6, 26),
        time_ams=time(20, 5),
        hour_ams=20,
        date_et=date(2026, 6, 26),
        away=away,
        home=home,
        is_tbd=False,
        source_seq=0,
    )


def _standing(team, pct, gb=2.0, wc=1.0, rank=2):
    return TeamStanding(
        team=team,
        wins=50,
        losses=40,
        winning_percentage=pct,
        division_rank=rank,
        games_back=gb,
        wild_card_games_back=wc,
        run_differential=35,
    )


def test_score_game_combines_rivalry_standings_and_playoff_odds():
    standings = {
        "yankees": _standing("yankees", 0.56),
        "red sox": _standing("red sox", 0.54),
    }
    odds = {
        "yankees": TeamPlayoffOdds(team="yankees", make_playoffs=0.55),
        "red sox": TeamPlayoffOdds(team="red sox", make_playoffs=0.48),
    }

    enrichment = score_game(_game(), standings=standings, playoff_odds=odds)

    assert enrichment is not None
    assert enrichment.score >= 55
    assert enrichment.label == "topwedstrijd"
    assert "rivalry" in enrichment.reasons
    assert "divisieduel" in enrichment.reasons
    assert "playoff odds" in enrichment.reasons


def test_division_pressure_only_applies_within_same_division():
    standings = {
        "yankees": _standing("yankees", 0.56),
        "guardians": _standing("guardians", 0.54),
    }

    enrichment = score_game(_game(home="guardians"), standings=standings)

    assert enrichment is not None
    assert "divisieduel" not in enrichment.reasons
    assert "divisiedruk" not in enrichment.reasons


def test_score_game_ignores_low_signal_game():
    enrichment = score_game(_game("rockies", "athletics"))
    assert enrichment is None


def test_enrich_games_skips_postseason():
    clock = FrozenClock(datetime(2026, 10, 5, 12, tzinfo=AMSTERDAM))
    season = select_active_season(clock)
    game = _game()

    enriched = enrich_games([game], season=season, clock=clock)

    assert enriched == [game]
    assert enriched[0].enrichment is None


def test_enrich_games_returns_copied_games_with_enrichment():
    clock = FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))
    season = select_active_season(clock)
    game = _game()

    enriched = enrich_games([game], season=season, clock=clock)

    assert enriched[0] is not game
    assert enriched[0].enrichment is not None
    assert game.enrichment is None
