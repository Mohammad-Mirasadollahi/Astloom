"""Ingest attaches validated code_metadata contract records on FILE/symbol nodes."""

from __future__ import annotations

from code_graph_service.application import CodeGraphService
from code_graph_service.domain.models import Scope
from code_graph_service.testing import InMemoryStore
from code_metadata import validate_file_metadata, validate_symbol_metadata

SCOPE = Scope("t", "w", "p")
SOURCE = """
def login(user, password):
    return user == "admin"
"""


def test_ingest_attaches_valid_code_metadata_records():
    service = CodeGraphService(InMemoryStore())
    result = service.ingest_file(
        SCOPE,
        "agent",
        "corr",
        "meta-1",
        {
            "file_path": "src/auth.py",
            "source": SOURCE,
            "language": "python",
            "repository_id": "repo-main",
        },
    )
    file_symbol = service.store.get_symbol(result.file_id, SCOPE)
    file_meta = (file_symbol.metadata or {}).get("code_metadata") or {}
    assert validate_file_metadata(file_meta) == []
    assert file_meta["repository_id"] == "repo-main"
    assert file_meta["freshness_status"] == "CURRENT"
    assert "code_metadata_errors" not in (file_symbol.metadata or {})

    login_id = f"sym:{SCOPE.project_id}:src.auth.login"
    symbol = service.store.get_symbol(login_id, SCOPE)
    sym_meta = (symbol.metadata or {}).get("code_metadata") or {}
    assert validate_symbol_metadata(sym_meta) == []
    assert sym_meta["file_id"] == result.file_id
    assert symbol.metadata.get("confidence_score") == sym_meta["confidence_score"]
    assert "code_metadata_errors" not in (symbol.metadata or {})
