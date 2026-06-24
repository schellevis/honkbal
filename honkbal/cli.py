from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from honkbal.clock import Clock, FrozenClock, SystemClock
from honkbal.season import ConfigError, select_active_season

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"


def _clock_from_now(now: str | None) -> Clock:
    if now is None:
        return SystemClock()
    return FrozenClock(datetime.fromisoformat(now))


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_tree(item, target)
        else:
            shutil.copy2(item, target)


def _copy_static_assets(out: Path, *, asset_version: str | None = None) -> None:
    # css/ → out/css/
    _copy_tree(FRONTEND / "css", out / "css")
    # static/ → out/ : top-level files go to docs root; subdirs (img/, fonts/, …) go to
    # out/<subdir>/ so the root-relative layout is preserved. All subdirs are copied
    # recursively via _copy_tree so future asset directories are never silently dropped.
    static = FRONTEND / "static"
    if static.exists():
        for item in static.iterdir():
            if item.is_file():
                shutil.copy2(item, out / item.name)
            elif item.is_dir():
                _copy_tree(item, out / item.name)
    # js/ → out/js/, but sw.js → out/sw.js (root, scope /)
    js = FRONTEND / "js"
    if js.exists():
        (out / "js").mkdir(parents=True, exist_ok=True)
        versioned_js_root = out / "js" / "v" / asset_version if asset_version else None
        if versioned_js_root is not None:
            versioned_js_root.mkdir(parents=True, exist_ok=True)
        for item in js.iterdir():
            if item.name == "sw.js":
                shutil.copy2(item, out / "sw.js")
            elif item.is_file():
                shutil.copy2(item, out / "js" / item.name)
                if versioned_js_root is not None:
                    shutil.copy2(item, versioned_js_root / item.name)
            elif item.is_dir():
                _copy_tree(item, out / "js" / item.name)
                if versioned_js_root is not None:
                    _copy_tree(item, versioned_js_root / item.name)
    # Fallback: sw.js directly under frontend/
    if (FRONTEND / "sw.js").is_file():
        shutil.copy2(FRONTEND / "sw.js", out / "sw.js")


def cmd_render(args, *, clock: Clock | None = None) -> int:
    clock = clock or _clock_from_now(getattr(args, "now", None))
    out = Path(args.out)
    data_dir = Path(args.data_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        season = select_active_season(clock)
    except ConfigError as exc:
        print(f"[FOUT] config-validatie mislukt: {exc}", file=sys.stderr)
        return 2

    from honkbal.cli_version import resolve_asset_version  # noqa: PLC0415
    from honkbal.fetch.espn_postseason import load_postseason  # noqa: PLC0415
    from honkbal.parse.schedule import load_games  # noqa: PLC0415
    from honkbal.render.pages import render_site  # noqa: PLC0415

    loaded = load_games(data_dir, clock=clock)
    games, meta = loaded if loaded else ([], None)
    postseason = load_postseason(data_dir)

    asset_ver = resolve_asset_version()

    render_site(
        out_dir=out,
        games=games,
        meta=meta,
        postseason=postseason,
        season=season,
        asset_version=asset_ver,
        clock=clock,
    )
    _copy_static_assets(out, asset_version=asset_ver)
    print(f"[ok] render → {out} (asset_version={asset_ver}, games={len(games)})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="honkbal", description="honkbal.net v2 static-site generator"
    )
    p.add_argument("--now", help="ISO8601-klok voor reproduceerbare build (default: nu)")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--out", default="docs")
        sp.add_argument("--data-dir", default=".data")

    add_common(sub.add_parser("fetch"))
    add_common(sub.add_parser("render"))
    add_common(sub.add_parser("build"))
    return p


def main(argv: list[str] | None = None, *, clock: Clock | None = None) -> int:
    args = build_parser().parse_args(argv)
    clock = clock or _clock_from_now(args.now)
    if args.command == "render":
        return cmd_render(args, clock=clock)
    if args.command == "fetch":
        from honkbal.cli_fetch import cmd_fetch
        return cmd_fetch(args, clock=clock)
    if args.command == "build":
        from honkbal.cli_fetch import cmd_fetch
        rc = cmd_fetch(args, clock=clock)
        if rc not in (0,):
            return rc
        return cmd_render(args, clock=clock)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
