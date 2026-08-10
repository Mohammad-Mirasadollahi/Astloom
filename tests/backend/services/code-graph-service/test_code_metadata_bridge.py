"""Unit tests for code_metadata_bridge helpers."""

from __future__ import annotations

from code_graph_service.domain.code_metadata_bridge import (
    build_file_metadata_record,
    build_symbol_metadata_record,
    merge_code_metadata,
)


def test_merge_file_metadata_passes_contract():
    record = build_file_metadata_record(
        file_id="file:p:a.py",
        project_id="p",
        path="a.py",
        language="python",
        content_hash="abc",
    )
    merged = merge_code_metadata({"hash_version": "4"}, record, kind="file")
    assert merged["code_metadata"]["path"] == "a.py"
    assert "code_metadata_errors" not in merged
    assert merged["confidence_score"] == record["confidence_score"]


def test_merge_symbol_metadata_flags_errors():
    bad = build_symbol_metadata_record(
        symbol_id="sym:p:x",
        file_id="file:p:a.py",
        qualified_name="",
        symbol_type="function",
    )
    merged = merge_code_metadata({}, bad, kind="symbol")
    assert merged["code_metadata_errors"]
