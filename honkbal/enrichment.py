from __future__ import annotations

from bisect import bisect_left
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from honkbal.clock import AMSTERDAM, Clock
from honkbal.config.rivalries import rivalry_tier
from honkbal.config.teams import MLB_TEAMS, division_of, league_of, normalize_team
from honkbal.models import Enrichment, Game
from honkbal.season import ActiveSeason


class TeamStanding(BaseModel):
    model_config = ConfigDict(frozen=True)

    team: str
    wins: int | None = None
    losses: int | None = None
    winning_percentage: float | None = None
    division_rank: int | None = None
    games_back: float | None = None
    wild_card_games_back: float | None = None
    run_differential: int | None = None
    streak: str | None = None
    last_ten: str | None = None


class TeamPlayoffOdds(BaseModel):
    model_config = ConfigDict(frozen=True)

    team: str
    make_playoffs: float | None = None
    win_division: float | None = None
    win_world_series: float | None = None


StandingsByTeam = dict[str, TeamStanding]
PlayoffOddsByTeam = dict[str, TeamPlayoffOdds]


def enrich_games(
    games: list[Game],
    *,
    season: ActiveSeason,
    clock: Clock,
    standings: StandingsByTeam | None = None,
    playoff_odds: PlayoffOddsByTeam | None = None,
) -> list[Game]:
    """Return games with rule-based interest scores.

    Postseason games are intentionally not enriched: from that point on the site already has
    explicit postseason labels and every game is inherently important.
    """
    if clock.now() >= season.windows.ps:
        return games

    st = standings or {}
    odds = playoff_odds or {}
    enriched: list[Game] = []
    for game in games:
        enrichment = score_game(game, standings=st, playoff_odds=odds)
        enriched.append(game.model_copy(update={"enrichment": enrichment}))
    return _assign_percentiles(enriched)


def _assign_percentiles(games: list[Game]) -> list[Game]:
    """Percentiel (0..100) van elke score binnen de gescoorde games van deze build.

    Het interessefilter (SPEC §6.9) werkt op percentielen in plaats van ruwe scores: de ruwe
    verdeling is samengeperst (~20..60) en verschuift per seizoensfase/signaalbeschikbaarheid,
    waardoor een vaste drempel op de ruwe score dode sliderzones geeft. "Drempel 75" betekent
    op percentielen altijd "toon de top 25%".
    """
    scores = sorted(g.enrichment.score for g in games if g.enrichment is not None)
    n = len(scores)
    if n == 0:
        return games

    def pct(score: float) -> int:
        if n == 1:
            return 50
        below = bisect_left(scores, score)
        return round(100 * below / (n - 1))

    out: list[Game] = []
    for g in games:
        if g.enrichment is None:
            out.append(g)
        else:
            e = g.enrichment.model_copy(update={"percentile": pct(g.enrichment.score)})
            out.append(g.model_copy(update={"enrichment": e}))
    return out


def score_game(
    game: Game,
    *,
    standings: StandingsByTeam | None = None,
    playoff_odds: PlayoffOddsByTeam | None = None,
) -> Enrichment | None:
    away = normalize_team(game.away)
    home = normalize_team(game.home)
    if away not in MLB_TEAMS or home not in MLB_TEAMS:
        return None

    standings = standings or {}
    playoff_odds = playoff_odds or {}
    away_st = standings.get(away)
    home_st = standings.get(home)
    away_odds = playoff_odds.get(away)
    home_odds = playoff_odds.get(home)

    score = 0.0
    reasons: list[str] = []

    tier = rivalry_tier(away, home)
    if tier:
        score += tier * 8
        reasons.append("rivalry")

    same_league = league_of(away) is not None and league_of(away) == league_of(home)
    same_division = (
        division_of(away) is not None and division_of(away) == division_of(home)
    )
    if same_league:
        score += 4
    if same_division:
        score += 6
        reasons.append("divisieduel")

    if _both_known(away_st, home_st):
        score += _team_quality_score(away_st, home_st, reasons)
        score += _standings_pressure_score(
            away_st, home_st, same_division, reasons,
            standings=standings, away=away, home=home,
        )

    if away_odds is not None and home_odds is not None:
        score += _playoff_pressure_score(away_odds, home_odds, reasons)

    if game.time_ams is not None:
        start = datetime.combine(game.date_ams, game.time_ams, tzinfo=AMSTERDAM)
        if start.weekday() >= 4:
            score += 3
            reasons.append("weekend")
        if 19 <= game.time_ams.hour <= 22:
            score += 3
            reasons.append("gunstige tijd")
    if game.is_tbd:
        score -= 6

    # Geen cutoff: élke reguliere-seizoenwedstrijd krijgt een score (nodig voor het
    # percentiel-gebaseerde interessefilter, SPEC §6.9). Alleen het label kent de
    # uitlicht-drempel (18): daaronder is de wedstrijd niet vermeldenswaardig.
    score = round(max(0.0, min(100.0, score)), 1)
    return Enrichment(
        score=score,
        label=_label_for(score, reasons) if score >= 18 else None,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _both_known(a: TeamStanding | None, b: TeamStanding | None) -> bool:
    return a is not None and b is not None


def _team_quality_score(a: TeamStanding, b: TeamStanding, reasons: list[str]) -> float:
    pcts = [p for p in (a.winning_percentage, b.winning_percentage) if p is not None]
    if len(pcts) != 2:
        return 0.0
    avg = sum(pcts) / 2
    diff = abs(pcts[0] - pcts[1])
    score = max(0.0, (avg - 0.48) * 45)
    score += max(0.0, 1.0 - diff * 5) * 6
    if avg >= 0.54:
        reasons.append("sterke teams")
    if diff <= 0.04:
        reasons.append("gelijkwaardig")
    return min(score, 18.0)


def _standings_pressure_score(
    a: TeamStanding,
    b: TeamStanding,
    same_division: bool,
    reasons: list[str],
    *,
    standings: StandingsByTeam,
    away: str,
    home: str,
) -> float:
    # Gemiddelde van de druk per team (niet het maximum): een race-team tegen een kansloos
    # team is half zo interessant als twee race-teams tegen elkaar.
    pressure = (
        _team_race_pressure(away, a, standings) + _team_race_pressure(home, b, standings)
    ) / 2
    score = pressure * 18
    if pressure >= 0.5:
        reasons.append("playoffrace")

    if same_division and a.division_rank is not None and b.division_rank is not None:
        if a.division_rank <= 3 and b.division_rank <= 3:
            score += 6
            reasons.append("divisiedruk")

    return min(score, 24.0)


def _team_race_pressure(team: str, st: TeamStanding, standings: StandingsByTeam) -> float:
    """Playoffdruk 0..1 voor één team.

    Een divisieleider heeft per definitie games_back 0; zijn druk komt van de achterstand van
    de nummer 2 in dezelfde divisie (staat die 12 games achter, dan is er geen race). Voor de
    rest telt de kleinste van divisie- en wildcard-achterstand.
    """
    if st.division_rank == 1:
        division = division_of(team)
        if division is None:
            return 0.0
        chaser_gbs = [
            other.games_back
            for slug, other in standings.items()
            if slug != team
            and other.division_rank == 2
            and other.games_back is not None
            and division_of(slug) == division
        ]
        return _race_pressure(min(chaser_gbs)) if chaser_gbs else 0.0
    return max(_race_pressure(st.games_back), _race_pressure(st.wild_card_games_back))


def _playoff_pressure_score(
    a: TeamPlayoffOdds,
    b: TeamPlayoffOdds,
    reasons: list[str],
) -> float:
    probs = [p for p in (a.make_playoffs, b.make_playoffs) if p is not None]
    if len(probs) != 2:
        return 0.0
    tension = sum(max(0.0, 1.0 - abs(p - 0.5) * 2) for p in probs) / 2
    score = tension * 25
    if score >= 8:
        reasons.append("playoff odds")
    if abs(probs[0] - probs[1]) <= 0.15:
        score += 5
        reasons.append("gelijke kansen")
    return min(score, 30.0)


def _race_pressure(value: float | None) -> float:
    if value is None:
        return 0.0
    value = abs(value)
    if value > 8:
        return 0.0
    return 1.0 - (value / 8.0)


def _label_for(score: float, reasons: list[str]) -> str:
    if score >= 55:
        return "topwedstrijd"
    if "rivalry" in reasons:
        return "rivalry"
    if "playoff odds" in reasons or "playoffrace" in reasons:
        return "playoffrace"
    return "uitgelicht"
