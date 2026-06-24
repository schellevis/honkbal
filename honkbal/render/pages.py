from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from honkbal.clock import AMSTERDAM, Clock
from honkbal.config.teams import TEAMS_AL, TEAMS_NL, team_slug
from honkbal.models import Game, PostseasonData, ScheduleMeta
from honkbal.render.context import PageContext, build_page_context, default_tab
from honkbal.render.env import make_env
from honkbal.render.tail import InlineContext
from honkbal.season import ActiveSeason


@dataclass
class RenderReport:
    written: list[str] = field(default_factory=list)
    game_count: int = 0


def asset_version(*, version_file: Path, style_css: Path) -> str:
    if version_file.exists():
        content = version_file.read_text().strip()
        if content:
            return content
    return str(int(style_css.stat().st_mtime))


def nav_team_list() -> list[tuple[str, str]]:
    """Alfabetische (slug, weergavenaam)-lijst van alle teams voor de nav-<select>."""
    return sorted(
        ((team_slug(t), _team_display(t)) for t in (*TEAMS_NL, *TEAMS_AL)),
        key=lambda item: item[1].lower(),
    )


def versioned_js_root(asset_version: str) -> str:
    return f"/js/v/{asset_version}"


def render_schedule_page(
    ctx: PageContext | InlineContext,
    *,
    asset_version: str,
    clock: Clock,
    season: ActiveSeason,
    inline_days=None,
    tail_count: int = 0,
) -> str:
    env = make_env()
    tmpl = env.get_template("schedule.html")
    days = inline_days if inline_days is not None else ctx.days
    return tmpl.render(
        page=ctx.page,
        asset_version=asset_version,
        js_root=versioned_js_root(asset_version),
        countdown=ctx.countdown,
        is_empty=ctx.is_empty,
        inline_days=days,
        tail_count=tail_count,
        has_postseason_footnote=ctx.has_postseason_footnote,
        teams=nav_team_list(),
    )


def render_debug_page(
    *,
    schedule_meta,
    season: ActiveSeason,
    postseason,
    build_version: str,
    build_time,
    docs_files: dict,
    asset_version: str,
) -> str:
    env = make_env()
    tmpl = env.get_template("debug.html")
    return tmpl.render(
        schedule_meta=schedule_meta,
        season=season,
        postseason=postseason,
        build_version=build_version,
        build_time=build_time,
        docs_files=docs_files,
        asset_version=asset_version,
        js_root=versioned_js_root(asset_version),
    )


def render_all_schedule_pages(
    games: list[Game],
    *,
    season: ActiveSeason,
    postseason: PostseasonData | None,
    clock: Clock,
    img_dir: Path,
    asset_version: str,
    out_dir: Path,
) -> dict[str, str]:
    from honkbal.render.tail import build_tail_json, split_context, write_tail

    results: dict[str, str] = {}
    pages = ["avond", "ochtend", "nacht", "alles"]

    for page in pages:
        ctx = build_page_context(
            games, page=page, team_slug_q=None, season=season,
            postseason=postseason, clock=clock, img_dir=img_dir, asset_version=asset_version,
        )
        inline_ctx, remaining = split_context(ctx)
        tail_count = sum(len(d.rows) for d in remaining)
        html = render_schedule_page(
            ctx, asset_version=asset_version, clock=clock, season=season,
            inline_days=inline_ctx.days, tail_count=tail_count,
        )
        (out_dir / f"{page}.html").write_text(html, encoding="utf-8")
        results[page] = html

        if remaining:
            tj = build_tail_json(
                remaining, page=page, asset_version=asset_version, total=ctx.total_rows,
                last_inline_date=inline_ctx.last_inline_date,
            )
            write_tail(out_dir, page, tj)

    dtab = default_tab(season=season, clock=clock)
    dtab_page = dtab if dtab in pages else "avond"
    ctx_idx = build_page_context(
        games, page=dtab_page, team_slug_q=None, season=season,
        postseason=postseason, clock=clock, img_dir=img_dir, asset_version=asset_version,
    )
    inline_idx, remaining_idx = split_context(ctx_idx)
    tail_count_idx = sum(len(d.rows) for d in remaining_idx)
    html_idx = render_schedule_page(
        ctx_idx, asset_version=asset_version, clock=clock, season=season,
        inline_days=inline_idx.days, tail_count=tail_count_idx,
    )
    (out_dir / "index.html").write_text(html_idx, encoding="utf-8")
    results["index"] = html_idx

    # index.html is de default-tab-inhoud; de "meer laden"-knop draagt
    # data-page=<default-tab> en hergebruikt dus /<default-tab>.tail.json (al gegenereerd in de
    # pages-loop hierboven). Geen losse index.tail.json — dat zou een verwarrend duplicaat zijn.

    # Genereer alle 30 teampagina's direct met filtered_games en page="team".
    # De tweetraps-ontdekking via alles_ctx is vervallen (L1): teampagina's negeren de
    # hide/showfrom-filter (filters.py:50), dus een team met alleen post-hide games zou anders
    # een lege pagina krijgen. Directe iteratie over TEAMS_NL+TEAMS_AL borgt dat alle 30
    # pagina's altijd correct worden gegenereerd (SW PRECACHE vereist alle 30).
    for team_name in (*TEAMS_NL, *TEAMS_AL):
        tslug = team_slug(team_name)
        ctx_t = build_page_context(
            games, page="team", team_slug_q=tslug, season=season,
            postseason=postseason, clock=clock, img_dir=img_dir, asset_version=asset_version,
        )
        inline_t, remaining_t = split_context(ctx_t)
        tail_count_t = sum(len(d.rows) for d in remaining_t)
        html_t = render_schedule_page(
            ctx_t, asset_version=asset_version, clock=clock, season=season,
            inline_days=inline_t.days, tail_count=tail_count_t,
        )
        (out_dir / f"{tslug}.html").write_text(html_t, encoding="utf-8")
        results[tslug] = html_t

        if remaining_t:
            tj = build_tail_json(
                remaining_t, page=tslug, asset_version=asset_version, total=ctx_t.total_rows,
                last_inline_date=inline_t.last_inline_date,
            )
            write_tail(out_dir, tslug, tj)

    return results


def _team_display(name: str) -> str:
    """Capitalize first letter of each word for display."""
    return " ".join(w.capitalize() for w in name.replace("+", " ").split())


def render_site(
    *,
    out_dir: Path,
    games: list[Game],
    meta: ScheduleMeta | None,
    postseason: PostseasonData | None,
    season: ActiveSeason,
    asset_version: str,
    clock: Clock,
    img_dir: Path | None = None,
) -> RenderReport:
    """Render full site to out_dir. Filters to games from now onward. Returns RenderReport."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report = RenderReport()

    # §3.2: toon strikt wedstrijden vanaf nu (parser is puur, filter leeft hier).
    # Voor GETIMEDE games is de grens moment-nauwkeurig: starttijd strikt > nu, zodat een
    # reeds begonnen wedstrijd verdwijnt en alleen nog-komende wedstrijden blijven.
    # Voor TBD games (geen tijd) is de grens datum-granulair: date_ams >= vandaag, want
    # zonder starttijd valt niet te bepalen of een wedstrijd op vandaag al voorbij is.
    now = clock.now()
    date_cutoff = now.date()

    def _keep(g) -> bool:
        if g.is_tbd or g.time_ams is None:
            return g.date_ams >= date_cutoff
        start = datetime.combine(g.date_ams, g.time_ams, tzinfo=AMSTERDAM)
        return start > now

    filtered_games = [g for g in games if _keep(g)]
    report.game_count = len(filtered_games)

    # Use frontend/static/img as default img_dir
    _repo = Path(__file__).resolve().parent.parent.parent
    _img_dir = img_dir if img_dir is not None else (_repo / "frontend" / "static" / "img")

    # Render alle schedule-pagina's (index, avond, ochtend, nacht, alles) + alle 30 teampagina's.
    # render_all_schedule_pages genereert alle teams direct (L1-vereenvoudiging).
    rendered = render_all_schedule_pages(
        filtered_games,
        season=season,
        postseason=postseason,
        clock=clock,
        img_dir=_img_dir,
        asset_version=asset_version,
        out_dir=out_dir,
    )
    report.written.extend(f"{k}.html" for k in rendered)

    # Render static pages with asset_version injected
    env = make_env()

    nav_teams = nav_team_list()

    scores_html = env.get_template("scores.html").render(
        asset_version=asset_version,
        js_root=versioned_js_root(asset_version),
        page="scores",
        teams=nav_teams,
    )
    (out_dir / "scores.html").write_text(scores_html, encoding="utf-8")
    report.written.append("scores.html")

    standings_html = env.get_template("standings.html").render(
        asset_version=asset_version,
        js_root=versioned_js_root(asset_version),
        season=season,
        page="standings",
        teams=nav_teams,
    )
    (out_dir / "standings.html").write_text(standings_html, encoding="utf-8")
    report.written.append("standings.html")

    from honkbal.render.logos import logo_html as _logo_html

    settings_teams = [
        (slug, label, _logo_html(slug, img_dir=_img_dir, asset_version=asset_version))
        for slug, label in nav_teams
    ]
    settings_html = env.get_template("settings.html").render(
        asset_version=asset_version,
        js_root=versioned_js_root(asset_version),
        teams=nav_teams,
        settings_teams=settings_teams,
        page="settings",
    )
    (out_dir / "settings.html").write_text(settings_html, encoding="utf-8")
    report.written.append("settings.html")

    offline_html = env.get_template("offline.html").render(
        asset_version=asset_version,
        js_root=versioned_js_root(asset_version),
    )
    (out_dir / "offline.html").write_text(offline_html, encoding="utf-8")
    report.written.append("offline.html")

    # Render debug page
    docs_files = {f: clock.now() for f in report.written}
    debug_html = render_debug_page(
        schedule_meta=meta,
        season=season,
        postseason=postseason,
        build_version=asset_version,
        build_time=clock.now(),
        docs_files=docs_files,
        asset_version=asset_version,
    )
    (out_dir / "debug.html").write_text(debug_html, encoding="utf-8")
    report.written.append("debug.html")

    return report
