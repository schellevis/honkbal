from __future__ import annotations

RAW_SEASONS: dict[int, dict[str, str | list[str]]] = {
    2024: {
        "reg": "29-03-2024", "showfrom": "01-01-2024", "einde": "04-11-2024",
        "ps": "01-10-2024", "wc": "01-10-2024", "ds": "05-10-2024",
        "cs": "13-10-2024", "ws": "25-10-2024",
        "new": "01-01-2025", "newreg": "27-03-2025", "hide": "01-02-2025",
    },
    2025: {
        "reg": "27-03-2025", "showfrom": "27-03-2025", "einde": "01-11-2025",
        "allstargame": "15-07-2025",
        "ps": "29-09-2025", "wc": "29-09-2025", "ds": "03-10-2025",
        "cs": "12-10-2025", "ws": "24-10-2025",
        "new": "01-01-2026", "newreg": "26-03-2026", "hide": "01-02-2026",
        "uitzondering": ["1803DodgersCubs", "1903DodgersCubs"],
    },
    2026: {
        "reg": "25-03-2026", "showfrom": "26-03-2026", "einde": "15-11-2026",
        "allstargame": "14-07-2026",
        "ps": "01-10-2026", "wc": "01-10-2026", "ds": "05-10-2026",
        "cs": "13-10-2026", "ws": "25-10-2026",
        "new": "01-01-2027", "hide": "01-02-2027",
        # newreg (2027 reguliere start) bewust weggelaten: nog onbekend → unknown-state.
        # Voeg toe zodra MLB de 2027 opening day bekendmaakt.
    },
}
