from __future__ import annotations

import os
from uuid import uuid4

from . import _paths  # noqa: F401 — side effect: service path bootstrap

from code_graph_service.core import CodeGraphService, Scope as GraphScope
from common_context_service.core import CommonContextService, Scope as CommonContextScope
from core_data_service.core import CoreData, Scope as CoreScope
from docs_sync_service.core import DocsSyncService, Scope as DocsScope
from memory_service.core import MemoryService, Scope as MemoryScope

from ..store_factory import StoreBundle, build_container, build_stores


def _seed_enabled(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    raw = str(env.get("ASTLOOM_MCP_GRAPH_SEED", "true")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


class PlatformBackends:
    """In-process Astloom service facades used by the MCP gateway."""

    def __init__(self, stores: StoreBundle | None = None) -> None:
        self._stores = stores or build_stores()
        self.core = CoreData(self._stores.core)
        self.memory = MemoryService(self._stores.memory)
        if self._stores.graph_service is not None:
            self.graph = self._stores.graph_service
        else:
            self.graph = CodeGraphService(self._stores.graph)
        self.docs = DocsSyncService(self._stores.docs)
        self.common_context = CommonContextService(self._stores.common_context)
        self.actor_id = "mcp-gateway"
        self.store_mode = self._stores.mode
        self.graph_mode = self._stores.graph_mode
        # Soft MCP-first gate: projects that called guidance_resolve this process
        self._guidance_resolved_projects: set[str] = set()

    def mark_guidance_resolved(self, scope: dict[str, str]) -> None:
        pid = str(scope.get("project_id") or "").strip()
        if pid:
            self._guidance_resolved_projects.add(pid)

    def guidance_was_resolved(self, scope: dict[str, str]) -> bool:
        pid = str(scope.get("project_id") or "").strip()
        return bool(pid) and pid in self._guidance_resolved_projects

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> PlatformBackends:
        """Composition-root entry: build stores via ``build_container`` and return backends."""
        return build_container(environ).backends

    def close(self) -> None:
        self._stores.close()

    def core_scope(self, scope: dict[str, str]) -> CoreScope:
        return CoreScope(scope["tenant_id"], scope["workspace_id"], scope["project_id"])

    def memory_scope(self, scope: dict[str, str]) -> MemoryScope:
        return MemoryScope(scope["tenant_id"], scope["workspace_id"], scope["project_id"])

    def graph_scope(self, scope: dict[str, str]) -> GraphScope:
        return GraphScope(scope["tenant_id"], scope["workspace_id"], scope["project_id"])

    def docs_scope(self, scope: dict[str, str]) -> DocsScope:
        return DocsScope(scope["tenant_id"], scope["workspace_id"], scope["project_id"])

    def common_context_scope(self, scope: dict[str, str]) -> CommonContextScope:
        return CommonContextScope(scope["tenant_id"], scope["workspace_id"], scope["project_id"])

    def ensure_guidance_seed(self, scope: dict[str, str], correlation_id: str) -> None:
        self.common_context.ensure_mcp_first_seed(
            self.common_context_scope(scope),
            self.actor_id,
            correlation_id,
        )

    def ensure_memory_seed(self, scope: dict[str, str], query: str) -> None:
        mem_scope = self.memory_scope(scope)
        if self.memory.store.list_memory(mem_scope):
            return
        self.memory.create_memory(
            mem_scope,
            self.actor_id,
            str(uuid4()),
            f"seed-memory:{scope['project_id']}",
            {
                "kind": "semantic",
                "state": "active",
                "title": "Project coding conventions",
                "body": f"Prefer Astloom scoped APIs and idempotency keys. Context query seed: {query}",
                "tags": ["programming", "conventions"],
                "evidence_refs": ["usage-profile:programming-cursor-mcp"],
                "source_refs": ["mcp-gateway"],
                "confidence": 0.95,
            },
        )

    def ensure_graph_seed(self, scope: dict[str, str]) -> None:
        """Seed a tiny demo graph only for ephemeral memory/postgres demo stores.

        Never seed into Neo4j — that would pollute the real indexed project graph.
        """
        if self.graph_mode == "neo4j":
            return
        if not _seed_enabled():
            return
        graph_scope = self.graph_scope(scope)
        if self.graph.store.list_symbols(graph_scope):
            return
        self.graph.ingest_file(
            graph_scope,
            self.actor_id,
            str(uuid4()),
            f"seed-graph:{scope['project_id']}",
            {
                "file_path": "src/auth/hash.py",
                "language": "python",
                "source": (
                    "def hash_password(value: str) -> str:\n"
                    "    return value\n\n"
                    "def verify_password(value: str, hashed: str) -> bool:\n"
                    "    return hash_password(value) == hashed\n"
                ),
            },
        )

    def ensure_docs_symbol(self, scope: dict[str, str], symbol: str, file_path: str | None) -> str:
        docs_scope = self.docs_scope(scope)
        repo = scope["project_id"]
        path = file_path or "src/module.py"
        existing = self.docs.store.find_symbol(docs_scope, repo, path, symbol)
        if existing is not None:
            return existing.id
        for candidate in self.docs.store.list_symbols(docs_scope):
            if candidate.symbol_path == symbol:
                return candidate.id
        indexed = self.docs.index_symbol(
            docs_scope,
            self.actor_id,
            str(uuid4()),
            f"docs-symbol:{repo}:{path}:{symbol}",
            {
                "repo": repo,
                "file_path": path,
                "symbol_path": symbol,
                "kind": "function",
                "body": f"def {symbol.split('.')[-1]}():\n    pass\n",
                "doc_required": True,
            },
        )
        return indexed.id
