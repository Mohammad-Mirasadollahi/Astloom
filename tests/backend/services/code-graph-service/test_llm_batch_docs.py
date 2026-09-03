"""Batch docs: one complete() per file chunk, not per symbol."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from code_graph_service.domain.enums import DocStatus, SymbolKind
from code_graph_service.domain.models import GraphSymbol, Scope
from code_graph_service.llm_wiring import LlmBackedDocGenerator, _parse_docs_batch_json


def _symbol(name: str, *, qn: str | None = None) -> GraphSymbol:
    qualified = qn or f"mod.{name}"
    return GraphSymbol(
        id=f"sym:p:{qualified}",
        scope=Scope("t", "w", "p"),
        kind=SymbolKind.FUNCTION,
        file_path="mod.py",
        name=name,
        qualified_name=qualified,
        signature=f"def {name}()",
        body=f"def {name}():\n    return 1\n",
        hash_value="h",
        ai_documentation="",
        doc_status=DocStatus.MISSING,
        embedding=[],
    )


class _FakeGateway:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.complete_calls = 0
        self.last_request: Any = None
        self.settings = SimpleNamespace(enabled=True, default_model="test-model")

    def complete(self, request: Any) -> SimpleNamespace:
        self.complete_calls += 1
        self.last_request = request
        return SimpleNamespace(content=json.dumps(self.payload))


def test_generate_many_one_complete_for_multiple_symbols(monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    a = _symbol("alpha")
    b = _symbol("beta")
    gw = _FakeGateway(
        {
            "docs": {
                a.qualified_name: "doc-alpha",
                b.qualified_name: "doc-beta",
            }
        }
    )
    gen = LlmBackedDocGenerator(gw, settings=gw.settings)
    out = gen.generate_many([(a, []), (b, ["alpha"])])
    assert out == ["doc-alpha", "doc-beta"]
    assert gw.complete_calls == 1
    assert gw.last_request.response_format_json is True


def test_generate_delegates_to_batch(monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    a = _symbol("solo")
    gw = _FakeGateway({"docs": {a.qualified_name: "solo-doc"}})
    gen = LlmBackedDocGenerator(gw, settings=gw.settings)
    assert gen.generate(a, []) == "solo-doc"
    assert gw.complete_calls == 1


def test_parse_docs_batch_json_accepts_docs_wrapper():
    a = _symbol("a")
    b = _symbol("b")
    raw = json.dumps({"docs": {a.qualified_name: "A", b.qualified_name: "B"}})
    assert _parse_docs_batch_json(raw, [(a, []), (b, [])]) == ["A", "B"]


def test_parse_docs_batch_json_partial_fills_empty():
    a = _symbol("a")
    b = _symbol("b")
    raw = json.dumps({"docs": {a.qualified_name: "only-a"}})
    assert _parse_docs_batch_json(raw, [(a, []), (b, [])]) == ["only-a", ""]


def test_generate_many_falls_back_on_provider_timeout(monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    a = _symbol("alpha")

    class _BoomGateway:
        settings = SimpleNamespace(enabled=True, default_model="test-model")

        def complete(self, request: Any) -> SimpleNamespace:
            raise TimeoutError("LiteLLM call exceeded deadline of 0.3s")

    class _Heuristic:
        def generate(self, symbol: GraphSymbol, neighbors: list[str]) -> str:
            return f"heuristic:{symbol.name}"

        def generate_many(self, items: list[tuple[GraphSymbol, list[str]]]) -> list[str]:
            return [self.generate(s, n) for s, n in items]

    gen = LlmBackedDocGenerator(_BoomGateway(), fallback=_Heuristic(), settings=_BoomGateway.settings)
    out = gen.generate_many([(a, [])])
    assert out == ["heuristic:alpha"]
