from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from honkbal.config.toggles import LOAD_MORE_BATCH, SHOW_GAMES
from honkbal.render.context import DayBlock, PageContext, RowContext
from honkbal.render.env import make_env


@dataclass(frozen=True)
class InlineContext:
    page: str
    default_tab: str
    countdown: tuple[str, bool] | None
    days: list[DayBlock]
    total_rows: int
    has_postseason_footnote: bool
    is_empty: bool
    tail_count: int
    last_inline_date: date | None = None


def split_context(ctx: PageContext) -> tuple[InlineContext, list[DayBlock]]:
    inline_days: list[DayBlock] = []
    remaining_days: list[DayBlock] = []
    inline_count = 0
    split_done = False

    for day in ctx.days:
        if split_done:
            remaining_days.append(day)
            continue

        rows_needed = SHOW_GAMES - inline_count
        if len(day.rows) <= rows_needed:
            inline_days.append(day)
            inline_count += len(day.rows)
        else:
            inline_rows = list(day.rows[:rows_needed])
            rest_rows = list(day.rows[rows_needed:])
            if inline_rows:
                inline_days.append(DayBlock(
                    header_label=day.header_label,
                    special=day.special,
                    date_ams=day.date_ams,
                    rows=inline_rows,
                ))
                inline_count += len(inline_rows)
            if rest_rows:
                remaining_days.append(DayBlock(
                    header_label=day.header_label,
                    special=day.special,
                    date_ams=day.date_ams,
                    rows=rest_rows,
                ))
            split_done = True

        if inline_count >= SHOW_GAMES:
            split_done = True

    last_inline_date = inline_days[-1].date_ams if inline_days else None
    tail_count = sum(len(d.rows) for d in remaining_days)
    inline_ctx = InlineContext(
        page=ctx.page,
        default_tab=ctx.default_tab,
        countdown=ctx.countdown,
        days=inline_days,
        total_rows=ctx.total_rows,
        has_postseason_footnote=ctx.has_postseason_footnote,
        is_empty=ctx.is_empty,
        tail_count=tail_count,
        last_inline_date=last_inline_date,
    )
    return inline_ctx, remaining_days


def _build_blocks(
    remaining_days: list[DayBlock],
    *,
    last_inline_date: date | None = None,
) -> list[str]:
    env = make_env()
    flat_rows: list[tuple[DayBlock, RowContext]] = []
    for day in remaining_days:
        for row in day.rows:
            flat_rows.append((day, row))

    blocks: list[str] = []
    last_emitted_date: date | None = last_inline_date

    i = 0
    while i < len(flat_rows):
        batch = flat_rows[i:i + LOAD_MORE_BATCH]
        i += LOAD_MORE_BATCH

        day_sections: list[tuple[DayBlock, list[RowContext], bool]] = []
        for day_block, _row in batch:
            if not day_sections or day_sections[-1][0].date_ams != day_block.date_ams:
                show_hdr = day_block.date_ams != last_emitted_date
                day_sections.append((day_block, [], show_hdr))
            day_sections[-1][1].append(_row)

        parts: list[str] = []
        for day_block, rows, show_hdr in day_sections:
            mini_day = DayBlock(
                header_label=day_block.header_label,
                special=day_block.special,
                date_ams=day_block.date_ams,
                rows=rows,
            )
            tmpl = env.from_string(
                "{% from '_rows.html' import render_days %}"
                "{{ render_days(days, show_headers=show_hdr) }}"
            )
            parts.append(tmpl.render(days=[mini_day], show_hdr=show_hdr))
            last_emitted_date = day_block.date_ams

        blocks.append("".join(parts))

    return blocks


def build_tail_json(
    remaining_days: list[DayBlock],
    *,
    page: str,
    asset_version: str,
    total: int,
    last_inline_date: date | None = None,
) -> dict[str, Any]:
    blocks = _build_blocks(
        remaining_days, last_inline_date=last_inline_date
    )
    return {
        "version": asset_version,
        "page": page,
        "total": total,
        "batch_size": LOAD_MORE_BATCH,
        "blocks": blocks,
    }


def write_tail(out_dir: Path, page: str, tail_json: dict[str, Any]) -> None:
    if not tail_json.get("blocks"):
        return
    out_path = out_dir / f"{page}.tail.json"
    out_path.write_text(json.dumps(tail_json, ensure_ascii=False), encoding="utf-8")
