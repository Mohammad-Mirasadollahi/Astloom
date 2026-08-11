"""Upsert parsed symbols and living-documentation nodes for one file."""

from __future__ import annotations

from typing import Any

from ...domain.code_metadata_bridge import (
    build_file_metadata_record,
    build_symbol_metadata_record,
    merge_code_metadata,
)
from ...domain.enums import DocStatus, SymbolKind
from ...domain.hashing import content_hash, digest
from ...domain.models import GraphSymbol, ParseResult, Scope


class FileSymbolsMixin:
    """Write FILE / code / DOCUMENTATION symbols and prune stale embeddings."""

    def _backfill_file_language(
        self,
        scope: Scope,
        *,
        file_path: str,
        language: str,
        stamp: str,
    ) -> int:
        symbols = self.store.list_symbols_for_file(scope, file_path)
        updated = 0
        for symbol in symbols:
            if str(symbol.language or "").strip():
                continue
            symbol.language = language
            symbol.updated_at = stamp
            self.store.put_symbol(symbol)
            updated += 1
        return updated

    def _upsert_file_symbol(
        self,
        scope: Scope,
        *,
        file_id: str,
        file_path: str,
        source: str,
        file_hash: str,
        language: str,
        stamp: str,
        previous_file: GraphSymbol | None,
        ai_documentation: str = "",
        hash_version: str = "",
        parser_version: str = "",
        reuse_unchanged_embedding: bool = False,
        repository_id: str | None = None,
    ) -> GraphSymbol:
        reused_embedding = bool(
            reuse_unchanged_embedding
            and previous_file is not None
            and previous_file.hash_value == file_hash
            and previous_file.embedding
        )
        file_embedding = (
            list(previous_file.embedding)
            if reused_embedding and previous_file is not None
            else list(self.embeddings.embed(file_path).vector)
        )
        confidence = 0.9 if ai_documentation else 0.7
        meta = merge_code_metadata(
            {
                "hash_version": hash_version,
                "parser_version": parser_version,
            },
            build_file_metadata_record(
                file_id=file_id,
                project_id=scope.project_id,
                path=file_path,
                language=language,
                content_hash=file_hash,
                repository_id=repository_id,
                confidence_score=confidence,
            ),
            kind="file",
        )
        file_symbol = GraphSymbol(
            id=file_id,
            scope=scope,
            kind=SymbolKind.FILE,
            file_path=file_path,
            name=file_path.rsplit("/", 1)[-1],
            qualified_name=file_path,
            signature=file_path,
            body=source,
            hash_value=file_hash,
            ai_documentation=ai_documentation or "",
            doc_status=DocStatus.UNCHANGED,
            embedding=file_embedding,
            created_at=stamp,
            updated_at=stamp,
            language=language,
            hash_version=hash_version,
            parser_version=parser_version,
            metadata=meta,
        )
        if previous_file is not None:
            file_symbol.version = previous_file.version + 1
            file_symbol.created_at = previous_file.created_at
        self.store.put_symbol(file_symbol)
        if not reused_embedding:
            self._index_embedding(
                scope,
                file_id,
                file_embedding,
                kind=SymbolKind.FILE.value,
            )
        return file_symbol

    def _upsert_parsed_symbols(
        self,
        scope: Scope,
        *,
        parsed: ParseResult,
        file_path: str,
        language: str,
        stamp: str,
        prefer_heuristic_docs: bool = False,
        reuse_unchanged_embeddings: bool = False,
        on_progress: Any | None = None,
    ) -> tuple[list[str], list[str], int, list[tuple[str, str]]]:
        """Return ``(symbol_ids, changed_ids, documented_count, documented_pairs)``.

        Phase 1 builds docs + embeddings (CPU/network). Phase 2 writes to the store so
        parallel workers spend wall time on embed rather than waiting on Neo4j.
        """
        from ...domain.documentation import HeuristicDocGenerator

        changed_ids: list[str] = []
        documented = 0
        symbol_ids: list[str] = []
        documented_pairs: list[tuple[str, str]] = []
        heuristic = HeuristicDocGenerator() if prefer_heuristic_docs else None
        doc_origin = "heuristic" if heuristic is not None else "llm"
        # (symbol, kind_for_index, optional_doc_symbol)
        pending: list[tuple[GraphSymbol, str, GraphSymbol | None]] = []
        embedding_requests: list[tuple[GraphSymbol, str]] = []
        generated_embedding_ids: set[str] = set()
        language_fixes: list[GraphSymbol] = []
        file_id = f"file:{scope.project_id}:{file_path}"

        def _progress(*, symbols_done: int, status: str = "symbol") -> None:
            if not callable(on_progress):
                return
            try:
                on_progress(
                    {
                        "file_path": file_path,
                        "symbols_done": symbols_done,
                        "symbols_total": len(parsed.symbols),
                        "status": status,
                        "doc_origin": doc_origin,
                    }
                )
            except Exception:  # noqa: BLE001 — progress must never break ingest
                return

        for item in parsed.symbols:
            symbol_id = f"sym:{scope.project_id}:{item.qualified_name}"
            symbol_ids.append(symbol_id)
            hashed = content_hash(item.body, language)
            hash_value = hashed["hash"]
            hash_version = hashed["hash_version"]
            parser_ver = hashed["parser_version"]
            previous = self._maybe_get(symbol_id, scope)
            changed = previous is None or previous.hash_value != hash_value
            neighbors = item.calls + item.bases + item.imports
            doc = previous.ai_documentation if previous and not changed else ""
            status = DocStatus.UNCHANGED
            doc_symbol: GraphSymbol | None = None
            if changed:
                changed_ids.append(symbol_id)
                draft = GraphSymbol(
                    id=symbol_id,
                    scope=scope,
                    kind=item.kind,
                    file_path=file_path,
                    name=item.name,
                    qualified_name=item.qualified_name,
                    signature=item.signature,
                    body=item.body,
                    hash_value=hash_value,
                    ai_documentation="",
                    doc_status=DocStatus.MISSING,
                    embedding=[],
                    visibility=item.visibility,
                    version=(previous.version + 1) if previous else 1,
                    created_at=previous.created_at if previous else stamp,
                    updated_at=stamp,
                    language=language,
                    hash_version=hash_version,
                    parser_version=parser_ver,
                    metadata={
                        "hash_version": hash_version,
                        "parser_version": parser_ver,
                    },
                )
                # Prefer heuristic only when living LLM docs are disabled (caller).
                # When LLM docs are on, each changed symbol hits the docs route (RPM).
                if heuristic is not None:
                    doc = heuristic.generate(draft, neighbors)
                else:
                    doc = self.docs.generate(draft, neighbors)
                status = DocStatus.GENERATED
                documented += 1
                doc_id = f"doc:{scope.project_id}:{item.qualified_name}"
                doc_symbol = GraphSymbol(
                    id=doc_id,
                    scope=scope,
                    kind=SymbolKind.DOCUMENTATION,
                    file_path=file_path,
                    name=f"{item.name}.md",
                    qualified_name=f"{item.qualified_name}::__doc__",
                    signature=item.signature,
                    body=doc,
                    hash_value=digest(doc),
                    ai_documentation=doc,
                    doc_status=DocStatus.GENERATED,
                    embedding=[],
                    created_at=stamp,
                    updated_at=stamp,
                    language=language,
                    metadata={"doc_origin": doc_origin},
                )
                embedding_requests.append((doc_symbol, doc))
                documented_pairs.append((symbol_id, doc_id))
                _progress(symbols_done=len(changed_ids), status="documented")
            elif previous and previous.ai_documentation:
                doc_id = f"doc:{scope.project_id}:{item.qualified_name}"
                doc_prev = self._maybe_get(doc_id, scope)
                if doc_prev is not None:
                    documented_pairs.append((symbol_id, doc_id))
                    if not str(doc_prev.language or "").strip():
                        doc_prev.language = language
                        doc_prev.updated_at = stamp
                        language_fixes.append(doc_prev)
            reuse_embedding = bool(
                reuse_unchanged_embeddings
                and not changed
                and previous is not None
                and previous.embedding
            )
            confidence = 0.9 if doc else 0.5
            hash_meta = merge_code_metadata(
                {
                    "hash_version": hash_version,
                    "parser_version": parser_ver,
                    "doc_origin": doc_origin if changed else (
                        (previous.metadata or {}).get("doc_origin") if previous else ""
                    ),
                },
                build_symbol_metadata_record(
                    symbol_id=symbol_id,
                    file_id=file_id,
                    qualified_name=item.qualified_name,
                    symbol_type=item.kind.value,
                    confidence_score=confidence,
                ),
                kind="symbol",
            )
            symbol = GraphSymbol(
                id=symbol_id,
                scope=scope,
                kind=item.kind,
                file_path=file_path,
                name=item.name,
                qualified_name=item.qualified_name,
                signature=item.signature,
                body=item.body,
                hash_value=hash_value,
                ai_documentation=doc,
                doc_status=status if changed else DocStatus.UNCHANGED,
                embedding=list(previous.embedding) if reuse_embedding and previous else [],
                visibility=item.visibility,
                version=(previous.version + 1)
                if previous and changed
                else (previous.version if previous else 1),
                created_at=previous.created_at if previous else stamp,
                updated_at=stamp,
                language=language,
                hash_version=hash_version,
                parser_version=parser_ver,
                metadata=hash_meta,
            )
            if not reuse_embedding:
                embedding_requests.append((symbol, f"{item.qualified_name}\n{doc}"))
            pending.append((symbol, item.kind.value, doc_symbol))

        texts = [text for _, text in embedding_requests]
        batch = getattr(self.embeddings, "embed_many", None)
        results = (
            (
                list(batch(texts))
                if callable(batch)
                else [self.embeddings.embed(text) for text in texts]
            )
            if texts
            else []
        )
        if len(results) != len(embedding_requests):
            raise RuntimeError(
                "embedding batch returned "
                f"{len(results)} results for {len(embedding_requests)} symbols"
            )
        for (symbol, _), result in zip(embedding_requests, results, strict=True):
            symbol.embedding = list(result.vector)
            generated_embedding_ids.add(symbol.id)
        if embedding_requests:
            _progress(symbols_done=len(changed_ids), status="embedded")

        for fix in language_fixes:
            self.store.put_symbol(fix)
        for symbol, kind, doc_symbol in pending:
            if doc_symbol is not None:
                self.store.put_symbol(doc_symbol)
                self._index_embedding(
                    scope,
                    doc_symbol.id,
                    doc_symbol.embedding,
                    kind=SymbolKind.DOCUMENTATION.value,
                )
            self.store.put_symbol(symbol)
            if symbol.id in generated_embedding_ids:
                self._index_embedding(scope, symbol.id, symbol.embedding, kind=kind)

        return symbol_ids, changed_ids, documented, documented_pairs

    def _prune_stale_file_embeddings(
        self,
        scope: Scope,
        *,
        file_path: str,
        file_id: str,
        symbol_ids: list[str],
        documented_pairs: list[tuple[str, str]],
    ) -> None:
        active_ids = set(symbol_ids) | {doc_id for _, doc_id in documented_pairs} | {file_id}
        lister = getattr(self.store, "list_symbols_for_file", None)
        existing_symbols = (
            lister(scope, file_path)
            if callable(lister)
            else [s for s in self.store.list_symbols(scope) if s.file_path == file_path]
        )
        for existing in existing_symbols:
            if existing.id in active_ids:
                continue
            if existing.kind == SymbolKind.FILE:
                continue
            self._delete_embedding(scope, existing.id)
            deleter = getattr(self.store, "delete_symbol", None)
            if callable(deleter):
                deleter(existing.id, scope)
