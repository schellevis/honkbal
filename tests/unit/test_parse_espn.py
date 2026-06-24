# tests/unit/test_parse_espn.py
import json
from datetime import date, datetime
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.parse.espn_postseason import (
    normalize_espn_name,
    parse_postseason,
    parse_series_standing,
)

FIX = Path(__file__).parent.parent / "fixtures" / "espn"


def _clock():
    return FrozenClock(datetime(2026, 10, 1, 12, 0, tzinfo=AMSTERDAM))


def _load(name):
    return json.loads((FIX / name).read_text())


def test_normalize_dbacks():
    assert normalize_espn_name("Diamondbacks") == "D-backs"
    assert normalize_espn_name("Guardians") == "Guardians"


def test_series_tied():
    s = parse_series_standing(_load("summary_tied.json"), "Tigers", "Guardians", {})
    assert s == "(1-1)"


def test_series_leader_oriented_away_first():
    teams = {"DET": "Tigers", "CLE": "Guardians"}
    # DET (away) leads 1-0 -> away-wins eerst -> (1-0)
    s = parse_series_standing(_load("summary_det_leads.json"), "Tigers", "Guardians", teams)
    assert s == "(1-0)"


def test_series_leader_home_flips_score():
    teams = {"DET": "Tigers", "CLE": "Guardians"}
    summary = {"seasonseries": [{"type": "current", "summary": "CLE leads series 2-1"}]}
    # CLE = home leads 2-1 -> oriënteer naar away-first -> (1-2)
    s = parse_series_standing(summary, "Tigers", "Guardians", teams)
    assert s == "(1-2)"


def test_series_finished_wins_variant_away():
    # Afgeronde serie: ESPN gebruikt "win(s) series" i.p.v. "lead(s) series" (echte data).
    teams = {"DET": "Tigers", "CLE": "Guardians"}
    summary = {"seasonseries": [{"type": "current", "summary": "DET wins series 3-1"}]}
    s = parse_series_standing(summary, "Tigers", "Guardians", teams)
    assert s == "(3-1)"


def test_series_finished_win_variant_home_flips():
    teams = {"CHC": "Cubs", "MIL": "Brewers"}
    # CHC = home "win series 2-1" -> oriënteer naar away-first -> (1-2)
    summary = {"seasonseries": [{"type": "current", "summary": "CHC win series 2-1"}]}
    s = parse_series_standing(summary, "Brewers", "Cubs", teams)
    assert s == "(1-2)"


def test_series_unknown_returns_none_no_crash():
    s = parse_series_standing(_load("summary_unknown.json"), "Tigers", "Guardians", {})
    assert s is None
    assert parse_series_standing({}, "a", "b", {}) is None  # geen seasonseries


def test_parse_postseason_dedup_and_fields():
    schedule = _load("schedule_two_teams.json")
    summaries = {"401809252": _load("summary_det_leads.json")}
    pd = parse_postseason(schedule, summaries, _clock())
    assert len(pd.games) == 1  # event komt 2x binnen -> dedup op event_id (§12.6)
    g = pd.games[(date(2026, 10, 1), 19, "Guardians")]
    assert g.event_id == "401809252"
    assert g.descr == "AL Division Series*"
    assert g.away == "Tigers" and g.home == "Guardians"
    assert g.standing == "(1-0)"
    assert pd.teams["DET"] == "Tigers"
    assert pd.fetched_at == _clock().now()
