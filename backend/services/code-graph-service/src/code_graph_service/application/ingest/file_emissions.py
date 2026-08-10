"""Secondary graph emissions after primary file edges (routes / DI / tests / rationale / dispatch)."""

from __future__ import annotations

from collections.abc import Sequence

from ...domain.confidence_policy import clamp_confidence
from ...domain.di_injections import extract_injections
from ...domain.dispatch_synth import synthesize_interface_dispatch
from ...domain.enums import CallConfidence, DocStatus, RelType, SymbolKind
from ...domain.framework_routes import extract_routes, route_symbol_id
from ...domain.freshness import extract_module_contract_docstring, extract_rationale_comments
from ...domain.hashing import digest
from ...domain.http_calls import extract_http_calls, normalize_http_path
from ...domain.models import GraphEdge, GraphSymbol, Scope
from ...domain.test_links import suggest_test_links
from ..support import unresolved_symbol_id


class FileEmissionsMixin:
    """Framework routes, HTTP client calls, DI injections, test links, rationale, dispatch."""

    def _emit_framework_routes(
        self,
        scope: Scope,
        *,
        file_path: str,
        source: str,
        language: str,
        stamp: str,
        short_names: dict[str, list[str]] | None = None,
    ) -> int:
        """Create ROUTE symbols and ROUTES_TO edges for framework handlers."""
        written = 0
        if short_names is None:
            by_name: dict[str, list[str]] = {}
            for sym in self.store.list_symbols(scope):
                if sym.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD}:
                    by_name.setdefault(sym.name, []).append(sym.id)
        else:
            by_name = short_names

        for route in extract_routes(source, language=language, file_path=file_path):
            rid = route_symbol_id(scope.project_id, route.method, route.path)
            label = f"{route.method} {route.path}"
            self.store.put_symbol(
                GraphSymbol(
                    id=rid,
                    scope=scope,
                    kind=SymbolKind.ROUTE,
                    file_path=file_path,
                    name=label,
                    qualified_name=f"route:{route.method}:{route.path}",
                    signature=label,
                    body="",
                    hash_value=digest(label),
                    ai_documentation=f"{route.framework} route",
                    doc_status=DocStatus.UNCHANGED,
                    embedding=self.embeddings.embed(label).vector,
                    created_at=stamp,
                    updated_at=stamp,
                    language=language,
                )
            )
            handlers = by_name.get(route.handler_name, [])
            confidence = (
                CallConfidence.EXACT
                if len(handlers) == 1
                else CallConfidence.AMBIGUOUS
                if handlers
                else CallConfidence.UNRESOLVED
            )
            if not handlers:
                target = unresolved_symbol_id(scope, route.handler_name)
                written += self._put_edge(
                    scope,
                    RelType.ROUTES_TO.value,
                    rid,
                    target,
                    file_path=file_path,
                    confidence=confidence,
                    metadata={
                        "framework": route.framework,
                        "method": route.method,
                        "path": route.path,
                        "handler": route.handler_name,
                        "line": route.line_hint,
                        "provenance": "framework_route",
                    },
                    link_key=f"route:{route.method}:{route.path}:{route.handler_name}",
                )
            else:
                for hid in handlers[:5]:
                    written += self._put_edge(
                        scope,
                        RelType.ROUTES_TO.value,
                        rid,
                        hid,
                        file_path=file_path,
                        confidence=confidence,
                        metadata={
                            "framework": route.framework,
                            "method": route.method,
                            "path": route.path,
                            "handler": route.handler_name,
                            "line": route.line_hint,
                            "provenance": "framework_route",
                        },
                        link_key=f"route:{route.method}:{route.path}:{hid}",
                    )
        return written

    def _emit_http_calls(
        self,
        scope: Scope,
        *,
        file_path: str,
        source: str,
        language: str,
    ) -> int:
        """Emit HTTP_CALLS from client call sites to ROUTE/handler or unresolved targets."""
        calls = extract_http_calls(source, language=language, file_path=file_path)
        if not calls:
            return 0

        # Prefer file-level caller: functions in this file that contain the call line (best-effort: all funcs in file)
        file_funcs = [
            s
            for s in self.store.list_symbols(scope)
            if s.file_path == file_path
            and s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD}
        ]
        routes_by_path: dict[str, list[str]] = {}
        for sym in self.store.list_symbols(scope):
            if sym.kind != SymbolKind.ROUTE:
                continue
            # qualified_name: route:METHOD:/path
            parts = sym.qualified_name.split(":", 2)
            path = parts[2] if len(parts) >= 3 else ""
            if path:
                routes_by_path.setdefault(normalize_http_path(path), []).append(sym.id)

        written = 0
        for call in calls:
            path = normalize_http_path(call.url_or_path)
            targets = list(routes_by_path.get(path, []))
            # Also match ROUTES_TO handlers via route metadata path
            if not targets:
                for edge in self.store.list_edges(scope):
                    if edge.rel_type != RelType.ROUTES_TO.value:
                        continue
                    meta_path = normalize_http_path(str(edge.metadata.get("path") or ""))
                    if meta_path == path:
                        targets.append(edge.source_id)  # route node
            targets = list(dict.fromkeys(targets))
            confidence = (
                CallConfidence.EXACT
                if len(targets) == 1
                else CallConfidence.AMBIGUOUS
                if targets
                else CallConfidence.UNRESOLVED
            )
            if not targets:
                targets = [unresolved_symbol_id(scope, f"http:{call.method}:{path}")]
            # Prefer functions whose body contains this URL/path (line-local attribution).
            body_hits = [
                s
                for s in file_funcs
                if call.url_or_path in (s.body or "") or path in (s.body or "")
            ]
            sources = body_hits[:3] if body_hits else file_funcs[:3]
            if not sources:
                file_id = f"file:{scope.project_id}:{file_path}"
                sources_ids = [file_id]
            else:
                sources_ids = [s.id for s in sources]
            rel = (
                RelType.ASYNC_CALLS.value
                if call.is_async or call.framework in {"httpx", "aiohttp"}
                else RelType.HTTP_CALLS.value
            )
            for sid in sources_ids:
                for tid in targets[:5]:
                    written += self._put_edge(
                        scope,
                        rel,
                        sid,
                        tid,
                        file_path=file_path,
                        confidence=confidence,
                        metadata={
                            "method": call.method,
                            "url_or_path": call.url_or_path,
                            "path": path,
                            "framework": call.framework,
                            "line": call.line_hint,
                            "is_async": bool(call.is_async),
                            "provenance": "http_client_call",
                        },
                        link_key=f"http:{sid}:{call.method}:{path}:{tid}",
                    )
        return written

    def _emit_di_injections(
        self,
        scope: Scope,
        *,
        file_path: str,
        source: str,
        language: str,
    ) -> int:
        """Emit CALLS edges for Depends / constructor DI bindings."""
        by_name: dict[str, list[str]] = {}
        for sym in self.store.list_symbols(scope):
            if sym.kind in {
                SymbolKind.FUNCTION,
                SymbolKind.METHOD,
                SymbolKind.CLASS,
            }:
                by_name.setdefault(sym.name, []).append(sym.id)

        written = 0
        for inj in extract_injections(source, language=language, file_path=file_path):
            consumers = by_name.get(inj.consumer_name, [])
            providers = by_name.get(inj.provider_name, [])
            if not consumers:
                continue
            if not providers:
                target = unresolved_symbol_id(scope, inj.provider_name)
                conf = clamp_confidence(
                    CallConfidence.UNRESOLVED, via="di_injection"
                )
                for cid in consumers[:5]:
                    written += self._put_edge(
                        scope,
                        RelType.CALLS.value,
                        cid,
                        target,
                        file_path=file_path,
                        confidence=conf,
                        metadata={
                            "call": inj.provider_name,
                            "framework": inj.framework,
                            "pattern": inj.pattern,
                            "line": inj.line_hint,
                            "provenance": "di_injection",
                        },
                        link_key=f"di:{cid}:{inj.provider_name}:{inj.pattern}",
                    )
                continue
            conf = clamp_confidence(
                CallConfidence.EXACT if len(providers) == 1 else CallConfidence.AMBIGUOUS,
                via="di_injection",
            )
            for cid in consumers[:5]:
                for pid in providers[:5]:
                    written += self._put_edge(
                        scope,
                        RelType.CALLS.value,
                        cid,
                        pid,
                        file_path=file_path,
                        confidence=conf,
                        metadata={
                            "call": inj.provider_name,
                            "framework": inj.framework,
                            "pattern": inj.pattern,
                            "line": inj.line_hint,
                            "provenance": "di_injection",
                        },
                        link_key=f"di:{cid}:{pid}:{inj.pattern}",
                    )
        return written

    def _emit_test_links(
        self,
        scope: Scope,
        *,
        symbols: Sequence[GraphSymbol] | None = None,
    ) -> int:
        """Emit convention-based TESTED_BY edges (production → test)."""
        triples: list[tuple[str, str, str]] = []
        id_by_qn: dict[str, str] = {}
        symbol_snapshot = symbols if symbols is not None else self.store.list_symbols(scope)
        for sym in symbol_snapshot:
            if sym.kind not in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}:
                continue
            triples.append((sym.qualified_name, sym.name, sym.file_path))
            id_by_qn[sym.qualified_name] = sym.id

        written = 0
        for link in suggest_test_links(triples):
            src = id_by_qn.get(link.production_name)
            tgt = id_by_qn.get(link.test_name)
            if not src or not tgt:
                continue
            written += self._put_edge(
                scope,
                RelType.TESTED_BY.value,
                src,
                tgt,
                file_path="",
                confidence=CallConfidence.PROBABLE,
                metadata={"reason": link.reason, "provenance": "test_convention"},
                link_key=f"tested_by:{src}:{tgt}",
            )
        return written

    def _emit_rationale_nodes(
        self,
        scope: Scope,
        *,
        file_path: str,
        source: str,
        stamp: str,
        language: str = "",
    ) -> int:
        """Extract WHY/NOTE/HACK comments as RATIONALE symbols linked DOCUMENTED_BY from file."""
        written = 0
        file_id = f"file:{scope.project_id}:{file_path}"
        for hit in extract_rationale_comments(source):
            rid = f"rationale:{scope.project_id}:{file_path}:{hit.line}:{hit.tag}"
            body = f"{hit.tag}: {hit.body}"
            self.store.put_symbol(
                GraphSymbol(
                    id=rid,
                    scope=scope,
                    kind=SymbolKind.RATIONALE,
                    file_path=file_path,
                    name=f"{hit.tag}:{hit.line}",
                    qualified_name=f"{file_path}::{hit.tag}@{hit.line}",
                    signature=hit.tag,
                    body=body,
                    hash_value=digest(body),
                    ai_documentation=body,
                    doc_status=DocStatus.UNCHANGED,
                    embedding=self.embeddings.embed(body).vector,
                    created_at=stamp,
                    updated_at=stamp,
                    language=language,
                )
            )
            written += self._put_edge(
                scope,
                RelType.DOCUMENTED_BY.value,
                file_id,
                rid,
                file_path=file_path,
                confidence=CallConfidence.EXACT,
                metadata={"tag": hit.tag, "line": hit.line, "provenance": "rationale_comment"},
                link_key=f"rationale:{hit.line}:{hit.tag}",
            )
        return written

    def _emit_module_contract_node(
        self,
        scope: Scope,
        *,
        file_path: str,
        source: str,
        stamp: str,
        language: str = "",
    ) -> int:
        """Index selective module contract docstring as RATIONALE (tag MODULE_CONTRACT)."""
        contract = extract_module_contract_docstring(source, language)
        if not contract:
            return 0
        file_id = f"file:{scope.project_id}:{file_path}"
        rid = f"rationale:{scope.project_id}:{file_path}:1:MODULE_CONTRACT"
        body = f"MODULE_CONTRACT: {contract}"
        self.store.put_symbol(
            GraphSymbol(
                id=rid,
                scope=scope,
                kind=SymbolKind.RATIONALE,
                file_path=file_path,
                name="MODULE_CONTRACT:1",
                qualified_name=f"{file_path}::MODULE_CONTRACT@1",
                signature="MODULE_CONTRACT",
                body=body,
                hash_value=digest(body),
                ai_documentation=contract,
                doc_status=DocStatus.UNCHANGED,
                embedding=self.embeddings.embed(contract).vector,
                created_at=stamp,
                updated_at=stamp,
                language=language,
            )
        )
        return self._put_edge(
            scope,
            RelType.DOCUMENTED_BY.value,
            file_id,
            rid,
            file_path=file_path,
            confidence=CallConfidence.EXACT,
            metadata={"tag": "MODULE_CONTRACT", "line": 1, "provenance": "module_contract_docstring"},
            link_key="rationale:1:MODULE_CONTRACT",
        )

    def _emit_dynamic_dispatch(
        self,
        scope: Scope,
        *,
        symbols: Sequence[GraphSymbol] | None = None,
        edges: Sequence[GraphEdge] | None = None,
    ) -> int:
        symbol_snapshot = (
            list(symbols) if symbols is not None else self.store.list_symbols(scope)
        )
        edge_snapshot = (
            list(edges)
            if edges is not None
            else [
                *self.store.list_edges(scope, rel_type=RelType.CALLS.value),
                *self.store.list_edges(scope, rel_type=RelType.INHERITS_FROM.value),
            ]
        )
        sym_tuples = [
            (s.id, s.name, s.qualified_name, s.kind.value)
            for s in symbol_snapshot
        ]
        inherits = [
            (e.source_id, e.target_id)
            for e in edge_snapshot
            if e.rel_type in {RelType.INHERITS_FROM.value, "INHERITS_FROM"}
        ]
        calls = [
            (e.source_id, e.target_id, str(e.metadata.get("call") or ""))
            for e in edge_snapshot
            if e.rel_type in {RelType.CALLS.value, "CALLS"}
        ]
        written = 0
        for synth in synthesize_interface_dispatch(
            symbols=sym_tuples, inherits=inherits, calls=calls
        ):
            conf = clamp_confidence(CallConfidence.PROBABLE, via="dynamic_dispatch")
            written += self._put_edge(
                scope,
                RelType.CALLS.value,
                synth.source_id,
                synth.target_id,
                file_path="",
                confidence=conf,
                metadata={
                    "call": synth.method_name,
                    "provenance": synth.provenance,
                    "via": "dynamic_dispatch",
                    "via_type": synth.via_type,
                    "synthesizedBy": "dynamic_dispatch",
                },
                link_key=f"dispatch:{synth.source_id}:{synth.target_id}:{synth.method_name}",
            )
        return written
