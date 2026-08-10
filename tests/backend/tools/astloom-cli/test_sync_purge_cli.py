"""CLI smoke for sync / purge parsers."""

from __future__ import annotations

from astloom_cli.parser import build_parser


def test_parser_has_sync_and_purge():
    parser = build_parser()
    sync = parser.parse_args(["sync"])
    assert sync.command == "sync"
    assert sync.path is None  # pinned software paths from init
    assert sync.max_files == 0
    purge = parser.parse_args(["purge", "--yes"])
    assert purge.command == "purge"
    assert purge.yes is True
