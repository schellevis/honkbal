from honkbal.config.seasons import RAW_SEASONS


def test_seasons_have_required_keys():
    required = {"reg", "showfrom", "einde", "ps", "wc", "ds", "cs", "ws", "new", "hide"}
    for year in (2024, 2025, 2026):
        assert required <= set(RAW_SEASONS[year]), f"jaar {year} mist velden"


def test_2026_block_values():
    s = RAW_SEASONS[2026]
    assert s["reg"] == "25-03-2026"
    assert s["ps"] == "01-10-2026"
    # newreg (2027 reguliere start) bewust weggelaten: nog onbekend → unknown-state.
    assert "newreg" not in s
