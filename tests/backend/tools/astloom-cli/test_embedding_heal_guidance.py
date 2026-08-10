"""Unit tests for shared embedding-heal operator guidance."""

from __future__ import annotations

from astloom_cli.embedding_heal_guidance import (
    format_embedding_heal_lines,
    missing_embedding_counts,
    print_embedding_heal_guidance,
)


def test_missing_embedding_counts_empty():
    assert missing_embedding_counts({}) == (0, 0, 0)
    assert missing_embedding_counts(None) == (0, 0, 0)


def test_format_embedding_heal_lines_guides_plain_sync():
    summary = {
        "embeddings": {
            "missing_symbols": 12,
            "indexed_symbols": 3,
            "eligible_symbols": 15,
        }
    }
    lines = format_embedding_heal_lines(summary)
    assert any("12 searchable symbols missing" in line for line in lines)
    assert any("Do this: astloom sync heal" in line for line in lines)
    assert format_embedding_heal_lines(summary, sync_mode="heal")
    assert any("This run:" in line for line in format_embedding_heal_lines(summary, sync_mode="heal"))


def test_print_embedding_heal_guidance_silent_when_complete(capsys):
    print_embedding_heal_guidance(
        {"embeddings": {"missing_symbols": 0, "indexed_symbols": 5, "eligible_symbols": 5}}
    )
    assert capsys.readouterr().out == ""


def test_print_remote_sync_heal_note_guides_plain_and_heal(capsys):
    from astloom_cli.embedding_heal_guidance import print_remote_sync_heal_note

    print_remote_sync_heal_note(sync_mode="")
    plain = capsys.readouterr().out
    assert "Embeddings (server)" in plain
    assert "astloom sync heal" in plain

    print_remote_sync_heal_note(sync_mode="heal")
    healed = capsys.readouterr().out
    assert "full-project embedding heal" in healed
