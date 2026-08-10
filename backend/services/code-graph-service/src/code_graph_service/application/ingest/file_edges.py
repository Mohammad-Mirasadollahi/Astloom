"""Structural edges for one ingested file (contains / docs / imports / inherits / calls)."""

from __future__ import annotations

from ...domain.confidence_policy import clamp_confidence
from ...domain.cross_language import (
    SymbolIndexes,
    build_symbol_indexes,
    resolve_call_target_polyglot,
    resolve_import_target,
)
from ...domain.enums import CallConfidence, DocStatus, SymbolKind
from ...domain.external_calls import classify_external_call, external_call_symbol_id
from ...domain.hashing import digest
from ...domain.models import GraphSymbol, ParseResult, Scope
from ..support import unresolved_symbol_id


class FileEdgesMixin:
    """Emit CONTAINS / DOCUMENTED_BY / IMPORTS / INHERITS_FROM / CALLS for a file."""

    def _emit_containment_and_doc_edges(
        self,
        scope: Scope,
        *,
        file_id: str,
        file_path: str,
        symbol_ids: list[str],
        documented_pairs: list[tuple[str, str]],
    ) -> int:
        written = 0
        for symbol_id in symbol_ids:
            written += self._put_edge(
                scope, "CONTAINS", file_id, symbol_id, file_path=file_path
            )
        for symbol_id, doc_id in documented_pairs:
            written += self._put_edge(
                scope, "DOCUMENTED_BY", symbol_id, doc_id, file_path=file_path
            )
        return written

    def _emit_import_edges(
        self,
        scope: Scope,
        *,
        parsed: ParseResult,
        file_id: str,
        file_path: str,
        language: str,
        stamp: str,
        indexes: SymbolIndexes,
        package_aliases: dict[str, str],
    ) -> int:
        written = 0
        for item in parsed.symbols:
            if item.kind != SymbolKind.IMPORT:
                continue
            for imp in item.imports:
                target, confidence, cross_meta = resolve_import_target(
                    imp,
                    indexes,
                    source_language=language,
                    package_aliases=package_aliases,
                )
                target_id = target or f"ext:{imp}"
                if target is None and self._maybe_get(target_id, scope) is None:
                    self.store.put_symbol(
                        GraphSymbol(
                            id=target_id,
                            scope=scope,
                            kind=SymbolKind.IMPORT,
                            file_path=file_path,
                            name=imp,
                            qualified_name=imp,
                            signature=imp,
                            body=imp,
                            hash_value=digest(imp),
                            ai_documentation="external import",
                            doc_status=DocStatus.UNCHANGED,
                            embedding=self.embeddings.embed(imp).vector,
                            created_at=stamp,
                            updated_at=stamp,
                            language=language,
                        )
                    )
                import_meta = {
                    "import_text": imp,
                    "is_external": target is None,
                    **cross_meta,
                }
                written += self._put_edge(
                    scope,
                    "IMPORTS",
                    file_id,
                    target_id,
                    file_path=file_path,
                    confidence=confidence,
                    metadata=import_meta,
                    link_key=f"import:{imp}",
                )
                source_id = f"sym:{scope.project_id}:{item.qualified_name}"
                written += self._put_edge(
                    scope,
                    "IMPORTS",
                    source_id,
                    target_id,
                    file_path=file_path,
                    confidence=confidence,
                    metadata=import_meta,
                    link_key=f"import:{imp}",
                )
        return written

    def _emit_inherit_and_call_edges(
        self,
        scope: Scope,
        *,
        parsed: ParseResult,
        file_path: str,
        language: str,
        indexes: SymbolIndexes,
        by_qualified: dict[str, str],
        short_names: dict[str, list[str]],
    ) -> int:
        written = 0
        for item in parsed.symbols:
            source_id = f"sym:{scope.project_id}:{item.qualified_name}"
            for base in item.bases:
                target = by_qualified.get(base) or (short_names.get(base, [None])[0])
                if target:
                    written += self._put_edge(
                        scope,
                        "INHERITS_FROM",
                        source_id,
                        target,
                        file_path=file_path,
                        confidence=CallConfidence.EXACT,
                        link_key=f"base:{base}",
                    )
                else:
                    written += self._put_edge(
                        scope,
                        "INHERITS_FROM",
                        source_id,
                        unresolved_symbol_id(scope, base),
                        file_path=file_path,
                        confidence=CallConfidence.UNRESOLVED,
                        metadata={"base": base},
                        link_key=f"base:{base}",
                    )
            reflection_names = set(getattr(item, "reflection_calls", None) or ())
            for call in item.calls:
                targets, confidence, cross_meta = resolve_call_target_polyglot(
                    call,
                    indexes=indexes,
                    import_aliases=parsed.import_aliases,
                    module_prefix=parsed.module_prefix,
                    source_language=language,
                )
                via = (
                    "reflection"
                    if call in reflection_names
                    else str(cross_meta.get("via") or "")
                )
                if via:
                    confidence = clamp_confidence(
                        confidence,
                        source_language=language,
                        target_language=str(cross_meta.get("target_language") or language),
                        via=via,
                    )
                meta = {**cross_meta, "call": call}
                if via:
                    meta["via"] = via
                    meta["provenance"] = via
                if confidence == CallConfidence.AMBIGUOUS and targets:
                    for match in targets:
                        written += self._put_edge(
                            scope,
                            "CALLS",
                            source_id,
                            match,
                            file_path=file_path,
                            confidence=CallConfidence.AMBIGUOUS,
                            metadata=meta,
                            link_key=f"call:{call}:{match}",
                        )
                elif targets:
                    written += self._put_edge(
                        scope,
                        "CALLS",
                        source_id,
                        targets[0],
                        file_path=file_path,
                        confidence=confidence,
                        metadata=meta,
                        link_key=f"call:{call}",
                    )
                else:
                    external_kind = classify_external_call(
                        call, import_aliases=parsed.import_aliases
                    )
                    if external_kind:
                        written += self._put_edge(
                            scope,
                            "CALLS",
                            source_id,
                            external_call_symbol_id(scope.project_id, call),
                            file_path=file_path,
                            confidence=clamp_confidence(
                                CallConfidence.EXTERNAL, via=via or ""
                            ),
                            metadata={
                                "call": call,
                                "is_external": True,
                                "external_kind": external_kind,
                                "cross_language": False,
                                **({"via": via, "provenance": via} if via else {}),
                            },
                            link_key=f"call:{call}",
                        )
                    else:
                        written += self._put_edge(
                            scope,
                            "CALLS",
                            source_id,
                            unresolved_symbol_id(scope, call),
                            file_path=file_path,
                            confidence=clamp_confidence(
                                CallConfidence.UNRESOLVED, via=via or ""
                            ),
                            metadata={
                                "call": call,
                                "cross_language": False,
                                **({"via": via, "provenance": via} if via else {}),
                            },
                            link_key=f"call:{call}",
                        )
        return written

    def _resolution_indexes(
        self, scope: Scope
    ) -> tuple[SymbolIndexes, dict[str, str], dict[str, list[str]]]:
        symbols = self.store.list_symbols(scope)
        indexes = build_symbol_indexes(symbols)
        by_qualified = {
            s.qualified_name: s.id
            for s in symbols
            if s.kind not in {SymbolKind.FILE, SymbolKind.DOCUMENTATION}
        }
        short_names: dict[str, list[str]] = {}
        for s in symbols:
            if s.kind in {SymbolKind.FILE, SymbolKind.DOCUMENTATION, SymbolKind.IMPORT}:
                continue
            short_names.setdefault(s.name, []).append(s.id)
        return indexes, by_qualified, short_names
