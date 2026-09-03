"""Batch docs: one complete() per file chunk, not per symbol."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from code_graph_service.domain.enums import DocStatus, SymbolKind
from code_graph_service.domain.models import GraphSymbol, Scope
from code_graph_service.llm_wiring import (
    LlmBackedDocGenerator,
    _parse_docs_batch_json,
    build_docs_batch_prompt,
    pack_docs_batches,
)


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


def test_pack_docs_batches_splits_large_file_under_budget():
    symbols = []
    for i in range(40):
        sym = _symbol(f"fn{i}")
        sym.body = ("x" * 900) + f"\ndef fn{i}():\n    return {i}\n"
        symbols.append((sym, []))
    batches = pack_docs_batches(symbols, prompt_budget=8_000, max_chunk=8)
    assert len(batches) >= 5
    assert sum(len(chunk) for chunk, _cap in batches) == 40
    for chunk, body_cap in batches:
        assert 1 <= len(chunk) <= 8
        assert body_cap <= 800
        prompt = build_docs_batch_prompt(chunk, body_cap=body_cap)
        assert len(prompt) <= 8_000 + 500  # small slack for packing estimate vs render


def test_generate_many_splits_after_timeout_before_heuristic(monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    items = [(_symbol(f"s{i}"), []) for i in range(4)]
    calls: list[int] = []

    class _FlakyGateway:
        settings = SimpleNamespace(enabled=True, default_model="test-model")

        def complete(self, request: Any) -> SimpleNamespace:
            # Count symbols in prompt by [n] markers roughly via docs keys expected
            user = request.messages[-1].content
            n = user.count("qualified_name=")
            calls.append(n)
            if n > 1:
                raise TimeoutError("deadline")
            # succeed only for single-symbol chunks
            qn = None
            for sym, _ in items:
                if sym.qualified_name in user:
                    qn = sym.qualified_name
                    break
            assert qn
            return SimpleNamespace(content=json.dumps({"docs": {qn: f"doc-{qn}"}}))

    gen = LlmBackedDocGenerator(_FlakyGateway(), settings=_FlakyGateway.settings)
    out = gen.generate_many(items)
    assert len(out) == 4
    assert all(o.startswith("doc-") for o in out)
    assert any(n > 1 for n in calls)  # first attempts were multi-symbol
    assert calls.count(1) >= 4  # eventually singles
