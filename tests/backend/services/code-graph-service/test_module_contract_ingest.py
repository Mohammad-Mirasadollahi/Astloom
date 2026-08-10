"""Tests for module-contract docstring extraction and ingest."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.freshness import extract_module_contract_docstring
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p")

CONTRACT_SRC = '''\
"""
Persistent analysis queue — one sample at a time.

Durability: PostgreSQL ticket status is the source of truth.
Redis LIST wakes the worker; rebuilt from DB on startup.
Redis timeouts fail-open to DB poll — never unexpected crashes.
"""

def enqueue(item):
    return item
'''


def test_extract_module_contract_python():
    doc = extract_module_contract_docstring(CONTRACT_SRC, "python")
    assert doc is not None
    assert "source of truth" in doc.lower()
    assert extract_module_contract_docstring('"""tiny"""\n\nx=1\n', "python") is None


def test_ingest_emits_module_contract_rationale():
    service = CodeGraphService(InMemoryStore())
    result = service.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idemp-contract-1",
        {"file_path": "pkg/queue.py", "source": CONTRACT_SRC, "language": "python"},
    )
    assert result.file_id.startswith("file:")
    file_sym = service.store.get_symbol(result.file_id, SCOPE)
    assert "PostgreSQL" in (file_sym.ai_documentation or "")
    rationale = [
        s
        for s in service.store.list_symbols(SCOPE)
        if s.kind.value == "rationale" and "MODULE_CONTRACT" in (s.name or "")
    ]
    assert rationale
    assert "fail-open" in rationale[0].body.lower() or "fail-open" in rationale[0].ai_documentation.lower()
