from honkbal.config.teams import (
    ALLOWLIST_RENDER,
    MLB_TEAMS,
    TEAM_ABBR,
    league_of,
    normalize_team,
    team_slug,
)


def test_mlb_teams_count_and_allowlist():
    assert len(MLB_TEAMS) == 30
    assert "national league" in ALLOWLIST_RENDER
    assert "national league" not in MLB_TEAMS
    assert len(TEAM_ABBR) == 30
    # all-star pseudo-teams: typo "all all-stars" is gefixt naar "al all-stars"
    assert "al all-stars" in ALLOWLIST_RENDER
    assert "nl all-stars" in ALLOWLIST_RENDER
    assert "all all-stars" not in ALLOWLIST_RENDER


def test_slug_and_normalize_dbacks():
    assert team_slug("D-backs") == "d-backs"
    assert team_slug("Red Sox") == "red+sox"
    assert team_slug("Diamondbacks") == "d-backs"
    assert normalize_team("D-Backs") == "d-backs"
    assert normalize_team("red+sox") == "red sox"
    assert normalize_team("AL All-Stars") == "al all-stars"


def test_league_of():
    assert league_of("yankees") == "AL"
    assert league_of("mets") == "NL"
    assert league_of("national league") is None
