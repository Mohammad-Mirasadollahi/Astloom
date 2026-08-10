from __future__ import annotations

from code_metadata import (
    load_profile,
    should_escalate_to_source,
    validate_file_metadata,
    validate_profile,
    validate_symbol_metadata,
)


def test_code_metadata_profile_loads_and_validates():
    profile = load_profile()
    assert profile["profile_id"] == "default"
    assert validate_profile(profile) == []


def test_file_and_symbol_validators():
    file_record = {
        "file_id": "file_1",
        "project_id": "proj_1",
        "repository_id": "repo_1",
        "path": "src/main.py",
        "language": "python",
        "content_hash": "abc",
        "ast_hash": "def",
        "freshness_status": "CURRENT",
        "confidence_score": 0.9,
    }
    symbol_record = {
        "symbol_id": "sym_1",
        "file_id": "file_1",
        "qualified_name": "main.run",
        "symbol_type": "function",
        "confidence_score": 0.8,
        "metadata_version": "1",
    }
    assert validate_file_metadata(file_record) == []
    assert validate_symbol_metadata(symbol_record) == []


def test_source_escalation_rules():
    profile = load_profile()
    assert should_escalate_to_source(
        freshness_status="STALE",
        confidence_score=0.9,
        risk_tags=[],
        profile=profile,
    )
    assert should_escalate_to_source(
        freshness_status="CURRENT",
        confidence_score=0.9,
        risk_tags=["secrets"],
        profile=profile,
    )
    assert not should_escalate_to_source(
        freshness_status="CURRENT",
        confidence_score=0.9,
        risk_tags=[],
        profile=profile,
    )
