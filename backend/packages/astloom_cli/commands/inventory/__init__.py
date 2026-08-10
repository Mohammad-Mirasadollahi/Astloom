"""`astloom inventory` — code vs docs done/remaining for client software roots."""

from __future__ import annotations

from astloom_cli.commands.inventory.cmd import cmd_inventory
from astloom_cli.commands.inventory.collect import build_inventory_report, inventory_one_root
from astloom_cli.commands.inventory.render import format_detail_text
from astloom_cli.commands.inventory.util import TOP_N, bucket, pct, rel_under, top
from astloom_cli.commands.inventory.words import parse_inventory_words
from astloom_cli.sync_config import resolve_sync_filters

# Back-compat aliases for tests / callers that used private names.
_pct = pct
_bucket = bucket
_rel_under = rel_under
_top = top
_inventory_one_root = inventory_one_root

__all__ = [
    "TOP_N",
    "build_inventory_report",
    "cmd_inventory",
    "format_detail_text",
    "inventory_one_root",
    "parse_inventory_words",
    "resolve_sync_filters",
    "_bucket",
    "_inventory_one_root",
    "_pct",
    "_rel_under",
    "_top",
]
