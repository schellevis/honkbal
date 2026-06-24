from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape


def make_env() -> Environment:
    return Environment(
        loader=PackageLoader("honkbal", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
