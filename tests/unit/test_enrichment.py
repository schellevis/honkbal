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


def test_low_signal_game_gets_low_score_without_label():
    """SPEC §6.9/§11: elke reguliere-seizoenwedstrijd krijgt een score (voor het
    percentielfilter); het uitlicht-label bestaat pas vanaf de drempel (18)."""
    enrichment = score_game(_game("rockies", "athletics"))
    assert enrichment is not None
    assert enrichment.score < 18
    assert enrichment.label is None


def test_runaway_division_leader_adds_no_playoff_pressure():
    """SPEC §11.2: een leider heeft games_back 0, maar zonder achtervolger binnen bereik
    is er geen race — dat mag geen playoffrace-punten opleveren."""
    standings = {
        "yankees": _standing("yankees", 0.65, gb=0.0, wc=0.0, rank=1),
        "red sox": _standing("red sox", 0.50, gb=12.0, wc=9.0, rank=2),
    }
    enrichment = score_game(_game(), standings=standings)
    assert enrichment is not None
    assert "playoffrace" not in enrichment.reasons


def test_tight_division_race_pressures_the_leader_too():
    standings = {
        "yankees": _standing("yankees", 0.60, gb=0.0, wc=0.0, rank=1),
        "red sox": _standing("red sox", 0.58, gb=1.0, wc=0.0, rank=2),
    }
    enrichment = score_game(_game(), standings=standings)
    assert enrichment is not None
    assert "playoffrace" in enrichment.reasons


def test_race_team_against_hopeless_team_scores_less_than_two_race_teams():
    """Gemiddelde i.p.v. maximum: één team in de race is half zo interessant als twee."""
    race = _standing("yankees", 0.55, gb=1.0, wc=0.5, rank=2)
    hopeless = _standing("guardians", 0.40, gb=15.0, wc=12.0, rank=5)
    also_race = _standing("guardians", 0.55, gb=1.5, wc=1.0, rank=3)

    one_sided = score_game(_game(home="guardians"),
                           standings={"yankees": race, "guardians": hopeless})
    two_sided = score_game(_game(home="guardians"),
                           standings={"yankees": race, "guardians": also_race})
    assert one_sided is not None and two_sided is not None
    assert two_sided.score > one_sided.score


def test_enrich_games_assigns_percentiles():
    clock = FrozenClock(datetime(2026, 6, 21, 12, tzinfo=AMSTERDAM))
    season = select_active_season(clock)
    top = _game()  # rivalry tier 3 + divisieduel
    low = _game("rockies", "athletics")

    enriched = enrich_games([top, low], season=season, clock=clock)

    assert enriched[0].enrichment.percentile == 100
    assert enriched[1].enrichment.percentile == 0


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
