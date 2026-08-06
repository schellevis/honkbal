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

# Tv-gids (SPEC §3.3): weergavenamen per kanaalslug; tevens allowlist voor de markup
# (class/src worden letterlijk geïnterpoleerd).
CHANNEL_LABELS: dict[str, str] = {
    "espn": "ESPN",
    "espn2": "ESPN2",
    "espn3": "ESPN3",
    "espn4": "ESPN4",
    "espn_extra": "ESPN Extra",
}


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


def channel_logo_html(
    channel: str, *, img_dir: Path, asset_version: str, nl_commentary: bool = False
) -> Markup:
    """Zenderlogo voor de tv-gids-kolom (SPEC §3.3).

    Geen height-attribuut zoals bij teamlogo's: de breedte per kanaal komt uit de CSS
    (`img.espn { width: 40px }` etc.), een vaste hoogte zou de aspect ratio vervormen.
    Ontbrekend asset of onbekend kanaal → lege Markup (rij zonder gids-div).
    """
    label = CHANNEL_LABELS.get(channel)
    if label is None:
        return Markup("")
    light = img_dir / "espn" / f"{channel}.png"
    if not light.exists():
        return Markup("")
    v = escape(asset_version)
    img = f'<img class="{channel}" src="/img/espn/{channel}.png?{v}" alt="{label}" />'
    if (img_dir / "espn" / f"{channel}-dark.png").exists():
        img = (
            "<picture>"
            f'<source srcset="/img/espn/{channel}-dark.png?{v}"'
            ' media="(prefers-color-scheme: dark)" />'
            f"{img}</picture>"
        )
    badge = '<span class="comm">NL</span>' if nl_commentary else ""
    nlcom = ' data-nlcom="1"' if nl_commentary else ""
    return Markup(f'<div class="espn" data-channel="{channel}"{nlcom}>{badge}{img}</div>')
