"""Generation use cases: context packs and generated-code validation."""

from __future__ import annotations

from typing import Any

from code_metadata import load_profile, should_escalate_to_source

from ..domain.enums import SymbolKind
from ..domain.errors import NotFoundError, ValidationError
from ..domain.hybrid_doc_coverage import build_symbol_doc_coverage
from ..domain.languages import detect_language_from_path
from ..domain.models import Scope
from ..domain.parsing import builtin_names, defined_names, extract_call_refs
from .support import GraphServiceSupport


class GenerationUseCases(GraphServiceSupport):
    def build_generation_context(
        self,
        scope: Scope,
        seed_symbol_id: str,
        max_symbols: int = 12,
    ) -> dict[str, Any]:
        seed = self.store.get_symbol(seed_symbol_id, scope)
        hybrid = build_symbol_doc_coverage(self.store, scope, seed, max_neighbors=max_symbols)
        related_ids = {seed.id}
        expansion = "one_hop"
        fetch = getattr(self.store, "neighborhood_edges", None)
        if callable(fetch):
            try:
                for edge in fetch(
                    scope,
                    seed_symbol_id,
                    max_depth=2,
                    direction="both",
                    rel_types=["CALLS", "HTTP_CALLS", "ASYNC_CALLS", "DOCUMENTED_BY"],
                ):
                    related_ids.add(edge.source_id)
                    related_ids.add(edge.target_id)
            except Exception:
                pass
            expansion = "cypher_neighborhood"
        else:
            expand = getattr(self.store, "expand_neighborhood", None)
            if callable(expand):
                try:
                    for edge in expand(
                        scope, seed_symbol_id, max_depth=2, limit=max(24, max_symbols * 2)
                    ):
                        related_ids.add(edge.source_id)
                        related_ids.add(edge.target_id)
                    expansion = "apoc_or_store_expand"
                except Exception:
                    expansion = "one_hop"
            if expansion == "one_hop":
                for edge in self.store.list_edges(scope):
                    if edge.source_id == seed.id:
                        related_ids.add(edge.target_id)
                    if edge.target_id == seed.id:
                        related_ids.add(edge.source_id)

        ordered_ids = sorted(related_ids)
        symbols = []
        for symbol_id in ordered_ids:
            try:
                symbol = self.store.get_symbol(symbol_id, scope)
            except NotFoundError:
                continue
            if symbol.kind in {SymbolKind.FILE, SymbolKind.UNRESOLVED, SymbolKind.EXTERNAL}:
                continue
            symbols.append(symbol)
            if len(symbols) >= max_symbols:
                break
        prompt_parts = [
            "Use only the following graph context. Do not assume repository-wide source.",
            f"Seed: {seed.qualified_name}",
            (
                "Hybrid documentation coverage "
                f"(preferred={hybrid['preferred_layer']}; "
                f"active={','.join(hybrid['active_layers'])}): "
                "prefer human docs, else living docs, else rationale, else AST neighbors."
            ),
        ]
        for snippet in hybrid.get("preferred_snippets") or []:
            prompt_parts.append(f"Preferred doc: {snippet}")
        polyglot = self.get_polyglot_profile(scope)  # type: ignore[attr-defined]
        if polyglot.is_polyglot:
            prompt_parts.append(f"Polyglot project profile: {polyglot.summary}")
            if polyglot.language_links:
                linked = ", ".join(
                    f"{link.source_language}↔{link.target_language}"
                    for link in polyglot.language_links[:8]
                )
                prompt_parts.append(f"Related languages (cross edges): {linked}")
        for symbol in symbols:
            language = detect_language_from_path(symbol.file_path) or "unknown"
            prompt_parts.append(
                f"- [{language}] {symbol.kind.value} {symbol.qualified_name}: {symbol.signature}\n"
                f"  doc: {symbol.ai_documentation.splitlines()[0] if symbol.ai_documentation else 'n/a'}"
            )
        metadata_profile = load_profile()
        freshness_fn = getattr(self, "freshness_status", None)
        freshness = freshness_fn(scope) if callable(freshness_fn) else {}
        pending = {str(p) for p in (freshness.get("pending_files") or []) if str(p).strip()}
        freshness_status = "STALE" if seed.file_path in pending else "CURRENT"
        meta = seed.metadata or {}
        confidence_score = float(
            meta.get("confidence_score")
            if meta.get("confidence_score") is not None
            else (0.9 if seed.ai_documentation else 0.5)
        )
        risk_tags = [str(tag) for tag in (meta.get("risk_tags") or [])]
        escalate = should_escalate_to_source(
            freshness_status=freshness_status,
            confidence_score=confidence_score,
            risk_tags=risk_tags,
            profile=metadata_profile,
        )
        return {
            "seed_symbol_id": seed.id,
            "symbol_count": len(symbols),
            "uses_full_repository": False,
            "expansion": expansion,
            "prompt_context": "\n".join(prompt_parts),
            "symbols": [self._symbol_view(symbol) for symbol in symbols],
            "polyglot": polyglot.to_dict(),
            "hybrid_documentation": hybrid,
            "source_read_escalation": {
                "escalate_to_source": escalate,
                "profile_id": metadata_profile.get("profile_id"),
                "freshness_status": freshness_status,
                "confidence_score": confidence_score,
            },
            "read_model_id": "code_graph.generation_context",
        }

    def validate_generated_code(self, scope: Scope, source: str) -> dict[str, Any]:
        if not source.strip():
            raise ValidationError("source is required")
        symbols = self.store.list_symbols(scope)
        known = {symbol.name for symbol in symbols}
        known.update(symbol.qualified_name for symbol in symbols)
        known.update(builtin_names())
        known.update(defined_names(source))
        call_refs = extract_call_refs(source)
        unknown = sorted(
            {
                ref
                for ref in call_refs
                if ref not in known and ref.split(".")[-1] not in known and not ref.startswith("__")
            }
        )
        return {
            "accepted": len(unknown) == 0,
            "unknown_symbols": unknown,
            "known_symbol_count": len(known),
            "checked_call_refs": sorted(call_refs),
        }
