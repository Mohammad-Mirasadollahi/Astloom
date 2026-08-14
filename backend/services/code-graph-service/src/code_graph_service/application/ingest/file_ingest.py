"""Single-file ingest orchestration (symbols / edges / emissions / relink).

Role: parse one source file into FILE/symbol nodes and structural edges.
SoT: content hash + language on FILE; CONTAINS required for code children.
Invariants: hash-stable skip only when language set and CONTAINS intact;
edgeless FILE rows re-ingest (repair). Idempotency key short-circuits.
Allowed failure: ValidationError on missing path/source; per-call store errors.
Forbidden: treating edgeless hash-stable FILE rows as up-to-date.
"""

from __future__ import annotations

from typing import Any

from ...domain.enums import SymbolKind
from ...domain.errors import ValidationError
from ...domain.freshness import extract_module_contract_docstring
from ...domain.hashing import content_hash, now_iso
from ...domain.languages import assert_language_supported, detect_language_from_path
from ...domain.models import IngestResult, Scope
from ...domain.parsers import parse_source
from ...domain.structural_integrity import file_needs_contains_repair
from .file_edges import FileEdgesMixin
from .file_emissions import FileEmissionsMixin
from .file_relink import FileRelinkMixin
from .file_symbols import FileSymbolsMixin


class FileIngestMixin(
    FileSymbolsMixin,
    FileEdgesMixin,
    FileEmissionsMixin,
    FileRelinkMixin,
):
    """Parse one source file into symbols/edges via focused mixins."""

    def ingest_file(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> IngestResult:
        file_path = str(payload.get("file_path") or "").strip()
        try:
            return self._ingest_file_apply(
                scope, actor_id, correlation_id, idempotency_key, payload
            )
        except Exception:
            if file_path:
                self._rollback_incomplete_file(
                    scope,
                    file_id=f"file:{scope.project_id}:{file_path}",
                    file_path=file_path,
                )
            raise

    def _mark_file_ingest_complete(self, scope: Scope, file_id: str) -> None:
        current = self._maybe_get(file_id, scope)
        if current is None:
            return
        meta = dict(current.metadata or {})
        if meta.get("ingest_complete"):
            return
        meta["ingest_complete"] = True
        current.metadata = meta
        self.store.put_symbol(current)

    def _rollback_incomplete_file(
        self, scope: Scope, *, file_id: str, file_path: str
    ) -> None:
        """Drop a FILE stub written before a failed ingest so hash-skip cannot hide it."""
        current = self._maybe_get(file_id, scope)
        if current is None:
            return
        if (current.metadata or {}).get("ingest_complete"):
            return
        lister = getattr(self.store, "list_symbols_for_file", None)
        existing = (
            lister(scope, file_path)
            if callable(lister)
            else []
        )
        if any(
            s.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}
            and s.id != file_id
            for s in existing
        ):
            return
        deleter = getattr(self.store, "delete_symbol", None)
        if callable(deleter):
            deleter(file_id, scope)

    def _ingest_file_apply(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> IngestResult:
        existing = self.store.begin_idempotency(scope, idempotency_key, "ingest_file")
        if existing is not None:
            file_symbol = self.store.get_symbol(existing, scope)
            return IngestResult(file_symbol.id, 0, 0, 0, 0, [])

        file_path = str(payload.get("file_path") or "").strip()
        source = str(payload.get("source") or "")
        raw_language = str(payload.get("language") or "").strip()
        if raw_language:
            language = assert_language_supported(raw_language)
        else:
            language = assert_language_supported(
                detect_language_from_path(file_path) or "python"
            )
        if not file_path or not source:
            raise ValidationError("file_path and source are required")

        stamp = now_iso()
        hashed = content_hash(source, language)
        file_hash = hashed["hash"]
        hash_version = hashed["hash_version"]
        parser_ver = hashed["parser_version"]
        file_id = f"file:{scope.project_id}:{file_path}"
        previous_file = self._maybe_get(file_id, scope)
        reuse_unchanged_embeddings = bool(payload.get("reuse_unchanged_embeddings"))
        module_contract = extract_module_contract_docstring(source, language) or ""
        if (
            bool(payload.get("language_backfill_only"))
            and previous_file is not None
            and previous_file.hash_value == file_hash
            and previous_file.hash_version == hash_version
            and previous_file.parser_version == parser_ver
        ):
            updated = self._backfill_file_language(
                scope,
                file_path=file_path,
                language=language,
                stamp=stamp,
            )
            clearer = getattr(self, "clear_pending_sync", None)
            if callable(clearer):
                clearer(file_path)
            self._mark_file_ingest_complete(scope, file_id)
            self.store.complete_idempotency(
                scope,
                idempotency_key,
                "ingest_file",
                file_id,
            )
            return IngestResult(file_id, updated, 0, 0, 0, [])
        # Skip only when content is unchanged, language is persisted, and CONTAINS
        # edges still exist (edgeless FILE rows need repair after graph wipe/drift).
        if (
            previous_file is not None
            and previous_file.hash_value == file_hash
            and previous_file.hash_version == hash_version
            and previous_file.parser_version == parser_ver
            and str(previous_file.language or "").strip()
            and not file_needs_contains_repair(
                self.store, scope, file_id=file_id, file_path=file_path
            )
        ):
            clearer = getattr(self, "clear_pending_sync", None)
            if callable(clearer):
                clearer(file_path)
            self._mark_file_ingest_complete(scope, file_id)
            self.store.complete_idempotency(scope, idempotency_key, "ingest_file", file_id)
            return IngestResult(file_id, 0, 0, 0, 0, [])

        self._upsert_file_symbol(
            scope,
            file_id=file_id,
            file_path=file_path,
            source=source,
            file_hash=file_hash,
            language=language,
            stamp=stamp,
            previous_file=previous_file,
            ai_documentation=module_contract,
            hash_version=hash_version,
            parser_version=parser_ver,
            reuse_unchanged_embedding=reuse_unchanged_embeddings,
            repository_id=str(payload.get("repository_id") or "").strip() or None,
        )

        parsed = parse_source(language, file_path, source)
        defer_cross_file = bool(payload.get("defer_cross_file_pass"))
        # Parallel ingest used to force heuristic docs whenever defer_cross_file
        # was set ("refresh LLM later") — but no later pass existed, so
        # ASTLOOM_LITELLM_DOCS_ENABLED=true was a no-op on `astloom sync`.
        # Keep heuristic only when living LLM docs are disabled.
        from llm_gateway.routing import docs_generation_enabled

        prefer_heuristic_docs = defer_cross_file and not docs_generation_enabled()
        force_heuristic = payload.get("prefer_heuristic_docs")
        if force_heuristic is not None:
            prefer_heuristic_docs = bool(force_heuristic)
        symbol_ids, changed_ids, documented, documented_pairs = self._upsert_parsed_symbols(
            scope,
            parsed=parsed,
            file_path=file_path,
            language=language,
            stamp=stamp,
            prefer_heuristic_docs=prefer_heuristic_docs,
            reuse_unchanged_embeddings=reuse_unchanged_embeddings,
            on_progress=payload.get("on_symbol_progress"),
        )
        self._prune_stale_file_embeddings(
            scope,
            file_path=file_path,
            file_id=file_id,
            symbol_ids=symbol_ids,
            documented_pairs=documented_pairs,
        )

        batch_edges = defer_cross_file and callable(
            getattr(self.store, "put_edges", None)
        )
        if batch_edges:
            self._begin_edge_batch()
        self.store.delete_file_edges(scope, file_path)
        edges_written = 0
        edges_written += self._emit_containment_and_doc_edges(
            scope,
            file_id=file_id,
            file_path=file_path,
            symbol_ids=symbol_ids,
            documented_pairs=documented_pairs,
        )

        shared = payload.get("shared_resolution")
        if isinstance(shared, dict) and shared.get("indexes") is not None:
            indexes = shared["indexes"]
            by_qualified = shared.get("by_qualified") or {}
            short_names = shared.get("short_names") or {}
        else:
            indexes, by_qualified, short_names = self._resolution_indexes(scope)
        package_aliases = payload.get("package_aliases")
        if not isinstance(package_aliases, dict):
            package_aliases = {}

        edges_written += self._emit_import_edges(
            scope,
            parsed=parsed,
            file_id=file_id,
            file_path=file_path,
            language=language,
            stamp=stamp,
            indexes=indexes,
            package_aliases=package_aliases,
        )
        edges_written += self._emit_inherit_and_call_edges(
            scope,
            parsed=parsed,
            file_path=file_path,
            language=language,
            indexes=indexes,
            by_qualified=by_qualified,
            short_names=short_names,
        )

        if not defer_cross_file:
            edges_written += self._relink_unresolved_calls(scope, source_language=language)
            edges_written += self._relink_unresolved_references(
                scope,
                source_language=language,
                package_aliases=package_aliases,
            )
        edges_written += self._emit_framework_routes(
            scope,
            file_path=file_path,
            source=source,
            language=language,
            stamp=stamp,
            short_names=short_names if defer_cross_file else None,
        )
        edges_written += self._emit_http_calls(
            scope, file_path=file_path, source=source, language=language
        )
        edges_written += self._emit_di_injections(
            scope, file_path=file_path, source=source, language=language
        )
        if not defer_cross_file:
            edges_written += self._emit_test_links(scope)
        edges_written += self._emit_rationale_nodes(
            scope, file_path=file_path, source=source, stamp=stamp, language=language
        )
        edges_written += self._emit_module_contract_node(
            scope, file_path=file_path, source=source, stamp=stamp, language=language
        )
        if not defer_cross_file:
            edges_written += self._emit_dynamic_dispatch(scope)
        if batch_edges:
            self._flush_edge_batch()

        clearer = getattr(self, "clear_pending_sync", None)
        if callable(clearer):
            clearer(file_path)

        if not defer_cross_file:
            polyglot = self.get_polyglot_profile(scope)  # type: ignore[attr-defined]
            self.store.append_event(
                self._event(
                    "FileIngested",
                    scope,
                    actor_id,
                    correlation_id,
                    idempotency_key,
                    {
                        "file_id": file_id,
                        "file_path": file_path,
                        "language": language,
                        "hash_version": hash_version,
                        "parser_version": parser_ver,
                        "symbols_indexed": len(symbol_ids) + 1,
                        "symbols_changed": len(changed_ids),
                        "symbols_documented": documented,
                        "polyglot": {
                            "is_polyglot": polyglot.is_polyglot,
                            "languages": polyglot.languages,
                            "relatedness": polyglot.relatedness,
                            "cross_language_edge_count": polyglot.cross_language_edge_count,
                            "summary": polyglot.summary,
                        },
                    },
                )
            )
            if polyglot.is_polyglot:
                self.store.append_event(
                    self._event(
                        "ProjectLanguageProfileUpdated",
                        scope,
                        actor_id,
                        correlation_id,
                        idempotency_key,
                        polyglot.to_dict(),
                    )
                )
        else:
            self.store.append_event(
                self._event(
                    "FileIngested",
                    scope,
                    actor_id,
                    correlation_id,
                    idempotency_key,
                    {
                        "file_id": file_id,
                        "file_path": file_path,
                        "language": language,
                        "hash_version": hash_version,
                        "parser_version": parser_ver,
                        "symbols_indexed": len(symbol_ids) + 1,
                        "symbols_changed": len(changed_ids),
                        "symbols_documented": documented,
                        "cross_file_deferred": True,
                    },
                )
            )
        if changed_ids:
            self.store.append_event(
                self._event(
                    "SymbolsDocumented",
                    scope,
                    actor_id,
                    correlation_id,
                    idempotency_key,
                    {"symbol_ids": changed_ids, "count": documented},
                )
            )
        self._mark_file_ingest_complete(scope, file_id)
        self.store.complete_idempotency(scope, idempotency_key, "ingest_file", file_id)
        return IngestResult(
            file_id=file_id,
            symbols_indexed=len(symbol_ids) + 1,
            symbols_changed=len(changed_ids),
            symbols_documented=documented,
            edges_written=edges_written,
            changed_symbol_ids=changed_ids,
        )
