from honkbal.config.seasons import RAW_SEASONS


def test_seasons_have_required_keys():
    required = {"reg", "showfrom", "einde", "ps", "wc", "ds", "cs", "ws", "new", "hide"}
    for year in (2024, 2025, 2026):
        assert required <= set(RAW_SEASONS[year]), f"jaar {year} mist velden"


def test_2026_block_values():
    s = RAW_SEASONS[2026]
    assert s["reg"] == "25-03-2026"
    # aangekondigde postseason 2026 (MLB, 10-08-2026)
    assert s["ps"] == "29-09-2026"
    assert s["wc"] == "29-09-2026"
    assert s["ds"] == "03-10-2026"
    assert s["cs"] == "11-10-2026"
    assert s["ws"] == "23-10-2026"
    # newreg (2027 reguliere start) bewust weggelaten: nog onbekend → unknown-state.
    assert "newreg" not in s
