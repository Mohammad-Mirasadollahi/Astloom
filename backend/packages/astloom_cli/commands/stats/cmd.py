"""`astloom stats` CLI entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from astloom_cli import ui
from astloom_cli.commands.inventory.collect import build_inventory_report
from astloom_cli.commands.stats.render import format_detail_text, print_human
from astloom_cli.commands.stats.words import parse_stats_words


def cmd_stats(args: argparse.Namespace) -> int:
    detail, save_path = parse_stats_words(getattr(args, "words", None))
    report = build_inventory_report(args)
    out_path = Path(save_path).expanduser() if save_path else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(format_detail_text(report), encoding="utf-8")

    print_human(report, detail=detail)
    if out_path is not None:
        ui.kv("Saved", str(out_path.resolve()))
        ui.blank()
    return 0
