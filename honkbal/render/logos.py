from __future__ import annotations

import re
from pathlib import Path

from markupsafe import Markup, escape

from honkbal.config.teams import normalize_team, team_slug

ALLSTAR_LEAGUE: dict[str, str] = {
    "al all-stars": "American League",
    "nl all-stars": "National League",
}
_SAFE_CLASS = re.compile(r"^[a-z0-9][a-z0-9+-]*$")


def display_name(name: str) -> str:
    return ALLSTAR_LEAGUE.get(normalize_team(name), name)


def logo_html(name: str, *, img_dir: Path, asset_version: str) -> Markup:
    disp = display_name(name)
    slug = team_slug(disp)
    alt = escape(disp)
    v = escape(asset_version)
    dark = img_dir / f"{slug}-dark.png"
    light = img_dir / f"{slug}-fs8.png"
    if dark.exists():
        return Markup(
            '<picture class="team">'
            f'<source srcset="/img/{slug}-dark.png?{v}" media="(prefers-color-scheme: dark)" />'
            f'<img src="/img/{slug}-fs8.png?{v}" alt="{alt}" height="20" />'
            "</picture>"
        )
    if light.exists():
        # Trailing space matches productie-markup (`<img …> Naam`): zorgt voor de
        # spatie tussen logo en teamnaam zonder extra CSS.
        return Markup(f'<img src="/img/{slug}-fs8.png?{v}" alt="{alt}" height="20" /> ')
    fallback_class = slug if _SAFE_CLASS.fullmatch(slug) else "unknown"
    return Markup(f'<span class="logofill {fallback_class}">&nbsp;</span>')
