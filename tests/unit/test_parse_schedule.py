# tests/unit/test_parse_schedule.py
import json
from datetime import date, datetime, time
from pathlib import Path

from honkbal.clock import AMSTERDAM, FrozenClock
from honkbal.parse.schedule import load_games, parse_schedule, parse_subject

FIX = Path(__file__).parent.parent / "fixtures" / "schedule"


def _clock():
    return FrozenClock(datetime(2026, 6, 21, 12, 0, tzinfo=AMSTERDAM))


def _load():
    csv_bytes = (FIX / "golden.csv").read_bytes()
    headers = json.loads((FIX / "golden_headers.json").read_text())
    return parse_schedule(csv_bytes, headers, _clock())


def test_parse_subject_splits_away_home():
    assert parse_subject("Angels at Yankees") == ("Angels", "Yankees")
    assert parse_subject("AL All-Stars at NL All-Stars") == ("AL All-Stars", "NL All-Stars")
    assert parse_subject("not a game") is None


def test_affiliate_filtered_by_allowlist():
    games, _ = _load()
    pairs = {(g.away, g.home) for g in games}
    assert ("Chihuahuas", "River Cats") not in pairs


def test_dst_and_date_shift_conversions():
    games, _ = _load()
    by = {(g.away, g.home, g.source_seq): g for g in games}
    # date_et != date_ams (zomertijd, +6u): Angels at Yankees 04/13 19:05 ET -> 04/14 01:05 AMS
    ay = by[("Angels", "Yankees", 1)]
    assert ay.date_et == date(2026, 4, 13)
    assert ay.date_ams == date(2026, 4, 14)
    assert ay.time_ams == time(1, 5)
    assert ay.hour_ams == 1
    # NY-DST actief, EU wintertijd (+5u): Dodgers at Angels 03/22 21:07 ET -> 03/23 02:07 AMS
    da = by[("Dodgers", "Angels", 2)]
    assert da.date_et == date(2026, 3, 22)
    assert da.date_ams == date(2026, 3, 23)
    assert da.time_ams == time(2, 7)
    # beide wintertijd na najaars-DST (+6u): Phillies at Dodgers 11/01 23:00 ET -> 11/02 05:00 AMS
    pd = by[("Phillies", "Dodgers", 3)]
    assert pd.date_ams == date(2026, 11, 2)
    assert pd.hour_ams == 5
    # beide wintertijd vóór voorjaars-DST (+6u): Mets at Marlins 03/03 20:00 ET -> 03/04 02:00 AMS
    mm = by[("Mets", "Marlins", 4)]
    assert mm.date_ams == date(2026, 3, 4)
    assert mm.hour_ams == 2


def test_allstar_feed_kept():
    games, _ = _load()
    assert any(g.away == "AL All-Stars" and g.home == "NL All-Stars" for g in games)


def test_tbd_doubleheader_both_kept_and_stripped():
    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    rows = [
        header,
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
    ]
    games, _ = parse_schedule(("\n".join(rows) + "\n").encode("utf-8"), {}, _clock())
    tbd = [g for g in games if g.is_tbd and g.away == "Reds" and g.home == "Cubs"]
    assert len(tbd) == 2  # twee echte TBD-games uit twee teamfeeds -> 4 bronregels -> 2 games
    for g in tbd:
        assert g.time_ams is None and g.hour_ams is None
        assert g.date_et == date(2026, 6, 1) and g.date_ams == date(2026, 6, 1)
        assert "Time TBD" not in g.away and "Time TBD" not in g.home


def test_exact_duplicate_timed_game_is_collapsed_to_one():
    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    rows = [
        header,
        "04/13/26,04:05 PM,07:05 PM,Angels at Yankees",
        "04/13/26,04:05 PM,07:05 PM,Angels at Yankees",
    ]
    games, _ = parse_schedule(("\n".join(rows) + "\n").encode("utf-8"), {}, _clock())
    dup = [g for g in games if g.away == "Angels" and g.home == "Yankees"]
    assert len(dup) == 1
    assert dup[0].source_seq == 0


def test_sorted_tbd_last_within_day():
    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    rows = [
        header,
        "06/01/26,10:05 AM,01:05 PM,Mets at Phillies",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
    ]
    games, _ = parse_schedule(("\n".join(rows) + "\n").encode("utf-8"), {}, _clock())
    june1 = [g for g in games if g.date_ams == date(2026, 6, 1)]
    assert [g.source_seq for g in june1] == [0, 1, 2]


def test_tbd_strip_tolerant_of_double_space_and_whitespace():
    # SPEC quote toont een dubbele spatie: "Reds at Cubs  - Time TBD". De strip moet
    # zowel single- als double-space (en omringende whitespace) aankunnen, identiek gedrag.
    header = "START DATE,START TIME,START TIME ET,SUBJECT"
    rows = [
        header,
        "06/01/26,,,Reds at Cubs  - Time TBD",   # dubbele spatie vóór streepje
        "06/01/26,,,Mets at Phillies - Time TBD",  # enkele spatie
    ]
    csv_text = "\n".join(rows) + "\n"
    games, _ = parse_schedule(csv_text.encode("utf-8"), {}, _clock())
    tbd = [g for g in games if g.is_tbd]
    assert len(tbd) == 2
    names = {(g.away, g.home) for g in tbd}
    assert ("Reds", "Cubs") in names, "double-space TBD suffix not stripped cleanly"
    assert ("Mets", "Phillies") in names
    for g in tbd:
        assert "Time TBD" not in g.away and "Time TBD" not in g.home
        assert "-" not in g.home  # geen achtergebleven streepje


def test_meta_newest_last_modified_wins():
    _, meta = _load()
    # nieuwste Last-Modified = 15 Jun 2026 10:00 UTC
    assert meta.modified.astimezone(AMSTERDAM).date() == date(2026, 6, 15)
    assert meta.refreshed == _clock().now()


def test_meta_accepts_httpx_lowercase_last_modified_header():
    csv_bytes = (FIX / "golden.csv").read_bytes()
    headers = {"108": {"last-modified": "Sun, 08 Mar 2026 23:05:07 GMT"}}
    _, meta = parse_schedule(csv_bytes, headers, _clock())
    assert meta.modified.astimezone(AMSTERDAM).date() == date(2026, 3, 9)
    assert meta.modified != meta.refreshed


def test_meta_falls_back_to_refreshed_when_no_last_modified():
    csv_bytes = (FIX / "golden.csv").read_bytes()
    headers = {"108": {"Content-Type": "text/csv"}}  # geen Last-Modified
    games, meta = parse_schedule(csv_bytes, headers, _clock())
    assert meta.modified == meta.refreshed == _clock().now()


# --- M1: pariteitsaanname _dedupe_team_feed_rows ---
# _dedupe_team_feed_rows leunt op "elke echte wedstrijd verschijnt een even aantal keer".
# De onderstaande tests borgen de drie maatgevende gevallen (normaal, TBD-DH, eenzijdig).

_HDR = "START DATE,START TIME,START TIME ET,SUBJECT"


def _parse(rows: list[str]) -> list:
    csv_text = "\n".join([_HDR] + rows) + "\n"
    games, _ = parse_schedule(csv_text.encode("utf-8"), {}, _clock())
    return games


def test_dedupe_pariteit_normale_wedstrijd_2x_wordt_1():
    """(a) Normale wedstrijd die 2× binnenkomt → 1 rij (SPEC §12.1)."""
    games = _parse([
        "04/13/26,04:05 PM,07:05 PM,Angels at Yankees",
        "04/13/26,04:05 PM,07:05 PM,Angels at Yankees",
    ])
    resultaat = [g for g in games if g.away == "Angels" and g.home == "Yankees"]
    assert len(resultaat) == 1, (
        "Verwacht 1 wedstrijd na dedup van 2 identieke rijen, maar kreeg "
        f"{len(resultaat)}. ceil(2/2)=1 is de pariteitsgarantie."
    )


def test_dedupe_pariteit_tbd_doubleheader_4x_wordt_2():
    """(b) TBD-doubleheader die 4× binnenkomt → 2 rijen (SPEC §12.13).

    Beide teamfeeds bevatten elk twee identieke TBD-rijen voor een DH → 4 total.
    ceil(4/2)=2 → twee wedstrijden behouden (de twee echte DH-games).
    """
    games = _parse([
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
        "06/01/26,,,Reds at Cubs - Time TBD",
    ])
    resultaat = [g for g in games if g.away == "Reds" and g.home == "Cubs"]
    assert len(resultaat) == 2, (
        "Verwacht 2 TBD-games na dedup van 4 identieke rijen (TBD-DH), maar kreeg "
        f"{len(resultaat)}. ceil(4/2)=2 is de pariteitsgarantie voor doubleheaders."
    )
    for g in resultaat:
        assert g.is_tbd


def test_dedupe_pariteit_eenzijdige_game_1x_blijft_1():
    """(c) All-star/eenzijdige game die maar 1× binnenkomt → 1 rij (ceil(1/2)=1)."""
    games = _parse([
        "07/15/26,05:30 PM,08:30 PM,AL All-Stars at NL All-Stars",
    ])
    resultaat = [g for g in games if g.away == "AL All-Stars"]
    assert len(resultaat) == 1, (
        "Verwacht 1 all-star-game na dedup van 1 bronrij, maar kreeg "
        f"{len(resultaat)}. ceil(1/2)=1 — eenzijdige feed levert geen duplicaat."
    )


# Fixture directory for load_games (has no Last-Modified in its headers)
SCHEDULE_FIX = Path(__file__).parent.parent / "fixtures" / "schedule"


def test_load_games_uses_injected_clock_for_refreshed(tmp_path):
    """§0: injected clock must be used, not SystemClock() (fix #1).

    We write a headers.json without Last-Modified so parse_meta falls back to
    clock.now() for *both* modified and refreshed. The injected FrozenClock is
    then verifiable without relying on real system time.
    """
    # Copy fixture files to tmp_path so load_games can find them.
    import shutil
    shutil.copy(SCHEDULE_FIX / "golden.csv", tmp_path / "all.csv")
    # Use headers without Last-Modified so refreshed == modified == frozen time.
    (tmp_path / "headers.json").write_text(
        '{"x": {"Content-Type": "text/csv"}}', encoding="utf-8"
    )
    frozen = FrozenClock(datetime(2026, 1, 15, 8, 30, tzinfo=AMSTERDAM))
    result = load_games(tmp_path, clock=frozen)
    assert result is not None
    _, meta = result
    # With no Last-Modified, both fields must equal the injected clock's time,
    # NOT the real system clock (which would differ by seconds/minutes).
    assert meta.refreshed == frozen.now()
    assert meta.modified == frozen.now()
