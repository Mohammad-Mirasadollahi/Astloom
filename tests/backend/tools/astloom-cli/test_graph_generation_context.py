"""CLI generation-context includes hybrid_documentation pack."""

from __future__ import annotations

import json

from astloom_cli.commands import graph as graph_cmd
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


def test_cmd_graph_generation_context_prints_hybrid(monkeypatch, capsys):
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "gen-ctx")
    svc.ingest_file(
        scope,
        "agent",
        "c",
        "idem",
        {
            "file_path": "src/x.py",
            "source": "def hello():\n    return 1\n",
            "language": "python",
        },
    )
    sid = f"sym:{scope.project_id}:src.x.hello"

    class _Args:
        symbol_id = sid
        qualified_name = ""
        max_symbols = 8

    monkeypatch.setattr(graph_cmd, "_graph_service", lambda: svc)
    monkeypatch.setattr(graph_cmd, "_graph_scope", lambda args: scope)
    code = graph_cmd.cmd_graph_generation_context(_Args())
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "hybrid_documentation" in payload
    assert payload["hybrid_documentation"]["mode"] == "hybrid"
    assert payload["hybrid_documentation"]["coverage"]["ast"] is True


def test_cmd_graph_generation_context_resolves_unique_short_name(monkeypatch, capsys):
    svc = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "gen-short")
    svc.ingest_file(
        scope,
        "agent",
        "c",
        "idem",
        {
            "file_path": "src/x.py",
            "source": "def hello():\n    return 1\n",
            "language": "python",
        },
    )

    class _Args:
        symbol_id = ""
        qualified_name = "hello"
        max_symbols = 8

    monkeypatch.setattr(graph_cmd, "_graph_service", lambda: svc)
    monkeypatch.setattr(graph_cmd, "_graph_scope", lambda args: scope)
    assert graph_cmd.cmd_graph_generation_context(_Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["seed_symbol_id"].endswith("src.x.hello")


def test_cmd_graph_ingest_returns_failure_for_failed_files(monkeypatch, tmp_path, capsys):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    svc = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "ingest-failure")

    class _Args:
        path = str(tmp_path)
        max_files = 10
        allow_cloud_llm = False

    monkeypatch.setattr(graph_cmd, "_graph_service", lambda: svc)
    monkeypatch.setattr(graph_cmd, "_graph_scope", lambda args: scope)
    assert graph_cmd.cmd_graph_ingest(_Args()) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["result"]["files_failed"] == 1
