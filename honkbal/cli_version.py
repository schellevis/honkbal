from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_VERSION = _REPO / "version.txt"
_DEFAULT_CSS = _REPO / "frontend" / "css" / "style.css"


def resolve_asset_version(
    *, version_file: Path | None = None, style_css: Path | None = None
) -> str:
    version_file = version_file or _DEFAULT_VERSION
    style_css = style_css or _DEFAULT_CSS
    if version_file.is_file():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return str(int(style_css.stat().st_mtime))


def write_version_file(value: str, *, version_file: Path | None = None) -> None:
    (version_file or _DEFAULT_VERSION).write_text(value.strip() + "\n", encoding="utf-8")
