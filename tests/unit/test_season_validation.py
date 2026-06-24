import pytest

from honkbal.season import ConfigError, load_windows, parse_date_nl


def test_parse_valid_date():
    d = parse_date_nl("25-03-2026")
    assert (d.year, d.month, d.day) == (2026, 3, 25)


def test_parse_invalid_date_raises():
    with pytest.raises(ValueError):
        parse_date_nl("30-02-2027")  # 30 feb bestaat niet


def test_load_2025_windows_ok():
    w = load_windows(2025)
    assert w.reg < w.ps < w.ws < w.einde
    assert "1803DodgersCubs" in w.uitzondering


def test_load_2026_ok_without_newreg():
    # productiedata is geldig; newreg ontbreekt (unknown) → geen fout, newreg is None
    w = load_windows(2026)
    assert w.newreg is None
    assert w.reg < w.ps < w.ws < w.einde


def test_invalid_date_in_block_raises():
    # 30-02 leeft alléén als lokale fixture, niet in de productieconfig
    bad = {2032: {
        "reg": "30-02-2032", "showfrom": "01-04-2032", "einde": "01-11-2032",
        "ps": "01-10-2032", "wc": "01-10-2032", "ds": "05-10-2032",
        "cs": "12-10-2032", "ws": "24-10-2032",
        "new": "01-01-2033", "hide": "01-02-2033",
    }}
    with pytest.raises(ConfigError):
        load_windows(2032, bad)


def test_invariant_violation_raises():
    # einde vóór reg/ps → invariant geschonden
    bad = {2031: {
        "reg": "01-04-2031", "showfrom": "01-04-2031", "einde": "01-03-2031",
        "ps": "01-10-2031", "wc": "01-10-2031", "ds": "05-10-2031",
        "cs": "12-10-2031", "ws": "24-10-2031",
        "new": "01-01-2032", "hide": "01-02-2032",
    }}
    with pytest.raises(ConfigError):
        load_windows(2031, bad)


def test_missing_required_field_raises():
    raw = {2030: {"reg": "01-04-2030"}}  # mist bijna alles
    with pytest.raises(ConfigError):
        load_windows(2030, raw)


def _valid_block(year: int) -> dict:
    return {
        "reg": f"01-04-{year}", "showfrom": f"01-04-{year}", "einde": f"01-11-{year}",
        "ps": f"01-10-{year}", "wc": f"01-10-{year}", "ds": f"05-10-{year}",
        "cs": f"12-10-{year}", "ws": f"24-10-{year}",
        "new": f"01-01-{year + 1}", "hide": f"01-02-{year + 1}",
    }


def test_in_season_date_year_mismatch_raises():
    # I4 (SPEC §4.3): in-season key met verkeerd jaar → ConfigError.
    bad = {2026: _valid_block(2026)}
    bad[2026]["reg"] = "01-04-2099"  # in-season datum in fout jaar
    with pytest.raises(ConfigError):
        load_windows(2026, bad)


def test_next_season_date_year_mismatch_raises():
    # next-season key (new/hide/newreg) moet blokjaar + 1 zijn.
    bad = {2026: _valid_block(2026)}
    bad[2026]["new"] = "01-01-2026"  # next-season datum in het blokjaar zelf
    with pytest.raises(ConfigError):
        load_windows(2026, bad)


def test_correct_year_block_loads_ok():
    ok = {2026: _valid_block(2026)}
    w = load_windows(2026, ok)
    assert w.reg.year == 2026
    assert w.new.year == 2027
