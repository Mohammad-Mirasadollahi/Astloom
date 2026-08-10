"""Memory embeddings SoR helpers (GAP-T03).

Role: durable memory embedding rows + Stage-1 cosine retrieve; optional Stage-2 ANN.
SoT: in-memory / PostgreSQL memory_embeddings (pgvector); turbovec is replica only.
Allowed: fail-open Stage-2. Forbidden: cross-tenant search; treating ANN as SoR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


@dataclass
class MemoryEmbeddingRow:
    memory_id: str
    tenant_id: str
    workspace_id: str
    project_id: str
    vector: list[float]
    model: str
    dims: int
    kind: str = "semantic"

    def scope_key(self) -> tuple[str, str, str]:
        return (self.tenant_id, self.workspace_id, self.project_id)


class MemoryEmbeddingStore(Protocol):
    def upsert(self, row: MemoryEmbeddingRow) -> None: ...

    def delete(self, scope: Any, memory_id: str) -> None: ...

    def search(
        self,
        scope: Any,
        vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[tuple[str, float]]: ...

    def list_models(self, scope: Any) -> dict[str, str]: ...


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


class InMemoryMemoryEmbeddingStore:
    """Unit-test / offline SoR stand-in for memory.memory_embeddings."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str, str], MemoryEmbeddingRow] = {}

    def upsert(self, row: MemoryEmbeddingRow) -> None:
        key = (*row.scope_key(), row.memory_id)
        self._rows[key] = MemoryEmbeddingRow(
            memory_id=row.memory_id,
            tenant_id=row.tenant_id,
            workspace_id=row.workspace_id,
            project_id=row.project_id,
            vector=list(row.vector),
            model=row.model,
            dims=row.dims,
            kind=row.kind,
        )

    def delete(self, scope: Any, memory_id: str) -> None:
        key = (scope.tenant_id, scope.workspace_id, scope.project_id, memory_id)
        self._rows.pop(key, None)

    def get_vector(self, scope: Any, memory_id: str) -> list[float] | None:
        key = (scope.tenant_id, scope.workspace_id, scope.project_id, memory_id)
        row = self._rows.get(key)
        return list(row.vector) if row is not None else None

    def list_models(self, scope: Any) -> dict[str, str]:
        out: dict[str, str] = {}
        for (tenant, workspace, project, memory_id), row in self._rows.items():
            if (tenant, workspace, project) != (scope.tenant_id, scope.workspace_id, scope.project_id):
                continue
            out[memory_id] = row.model
        return out

    def search(
        self,
        scope: Any,
        vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []
        for (tenant, workspace, project, memory_id), row in self._rows.items():
            if (tenant, workspace, project) != (scope.tenant_id, scope.workspace_id, scope.project_id):
                continue
            scored.append((memory_id, _cosine(vector, row.vector)))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [(mid, score) for mid, score in scored[: max(1, top_k)] if score > 0]


@dataclass
class Stage1RetrieveResult:
    hits: list[dict[str, Any]] = field(default_factory=list)
    retrieval: str = "stage1_pgvector"
    stage2_used: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "hits": list(self.hits),
            "retrieval": self.retrieval,
            "stage2_used": self.stage2_used,
        }


def stage1_retrieve(
    store: MemoryEmbeddingStore,
    scope: Any,
    query_vector: list[float],
    *,
    top_k: int = 5,
    vector_index: Any | None = None,
    entity_id_map: Any | None = None,
) -> Stage1RetrieveResult:
    """Stage-1 cosine search over SoR; optional fail-open Stage-2 turbovec rerank.

    Stage-2 is wired only when memory SoR embeddings already produced hits and both
    ``vector_index`` + ``entity_id_map`` are injected (composition root).
    """
    hits = store.search(scope, query_vector, top_k=top_k)
    result = Stage1RetrieveResult(
        hits=[{"memory_id": mid, "score": score, "retrieval": "stage1"} for mid, score in hits],
        retrieval="stage1_pgvector",
    )
    if vector_index is None or entity_id_map is None or not hits:
        return result
    try:
        import numpy as np

        allow: list[int] = []
        id_to_mid: dict[int, str] = {}
        vectors: list[list[float]] = []
        getter = getattr(store, "get_vector", None)
        for mid, _score in hits:
            vec = getter(scope, mid) if callable(getter) else None
            if vec is None:
                continue
            uid = int(entity_id_map.get_or_assign(mid))
            allow.append(uid)
            id_to_mid[uid] = mid
            vectors.append(list(vec))
        if not allow:
            return result
        arr = np.asarray(vectors, dtype=np.float32)
        vector_index.upsert(allow, arr)
        scores_arr, uids = vector_index.search(
            np.asarray(query_vector, dtype=np.float32),
            max(1, top_k),
            allowlist=allow,
        )
        if len(uids) == 0:
            return result
        reranked: list[dict[str, Any]] = []
        for score, uid in zip(scores_arr.tolist(), uids.tolist(), strict=False):
            mid = id_to_mid.get(int(uid))
            if mid:
                reranked.append(
                    {
                        "memory_id": mid,
                        "score": float(score),
                        "retrieval": "stage1+turbovec",
                    }
                )
        if reranked:
            result.hits = reranked
            result.stage2_used = True
            result.retrieval = "stage1_pgvector+turbovec"
    except Exception:
        return result
    return result
