"""Wire LiteLLM docs generation and embeddings into code-graph-service."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from llm_gateway import ChatMessage, CompletionRequest, LlmGatewaySettings
from llm_gateway.routing import (
    docs_generation_enabled,
    embeddings_generation_enabled,
    resolve_route,
)

from .domain.documentation import HeuristicDocGenerator
from .domain.embeddings import LocalEmbeddingStub
from .domain.models import EmbeddingResult, GraphSymbol


class _DocGenerator(Protocol):
    def generate(self, symbol: GraphSymbol, neighbors: list[str]) -> str: ...

    def generate_many(self, items: list[tuple[GraphSymbol, list[str]]]) -> list[str]: ...


class _Embedder(Protocol):
    model: str

    def embed(self, text: str) -> EmbeddingResult: ...


def reduce_dims(vector: list[float], dims: int) -> list[float]:
    """Down-project an embedding to `dims` for the pgvector column width."""
    if dims <= 0:
        raise ValueError("dims must be > 0")
    if len(vector) == dims:
        return list(vector)
    if len(vector) < dims:
        return list(vector) + [0.0] * (dims - len(vector))
    # Average-pool contiguous chunks into `dims` buckets.
    out = [0.0] * dims
    counts = [0] * dims
    for idx, value in enumerate(vector):
        bucket = min(dims - 1, idx * dims // len(vector))
        out[bucket] += float(value)
        counts[bucket] += 1
    for i in range(dims):
        if counts[i]:
            out[i] /= counts[i]
    norm = sum(v * v for v in out) ** 0.5 or 1.0
    return [round(v / norm, 6) for v in out]


def _is_embed_context_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "context length" in msg or "input tokens" in msg


def _embed_char_budget(
    *,
    max_tokens: int | None = None,
    chars_per_token: float | None = None,
) -> int:
    """Max characters per hosted-BGE request (hard cap 512 tokens)."""
    import os

    if max_tokens is None:
        raw = str(os.environ.get("ASTLOOM_EMBEDDING_MAX_INPUT_TOKENS", "360")).strip()
        try:
            max_tokens = int(raw) if raw else 360
        except ValueError:
            max_tokens = 360
    if chars_per_token is None:
        raw_cpt = str(os.environ.get("ASTLOOM_EMBEDDING_CHARS_PER_TOKEN", "2.5")).strip()
        try:
            chars_per_token = float(raw_cpt) if raw_cpt else 2.5
        except ValueError:
            chars_per_token = 2.5
    if max_tokens <= 0:
        return 10**9
    return max(8, int(max_tokens * float(chars_per_token)))


def truncate_embedding_input(
    text: str,
    *,
    max_tokens: int | None = None,
    chars_per_token: float | None = None,
) -> str:
    """Clamp one embed window under the model context (BGE-large hosted = 512).

    Do not use this to drop document tails — ``chunk_embedding_input`` keeps
    the full text as consecutive windows. Stored symbol/doc bodies are never
    truncated here.
    """
    max_chars = _embed_char_budget(
        max_tokens=max_tokens, chars_per_token=chars_per_token
    )
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def chunk_embedding_input(
    text: str,
    *,
    max_tokens: int | None = None,
    chars_per_token: float | None = None,
) -> list[str]:
    """Split text into full-coverage windows that each fit the embed cap."""
    budget = _embed_char_budget(
        max_tokens=max_tokens, chars_per_token=chars_per_token
    )
    if not text:
        return [""]
    if len(text) <= budget:
        return [text]
    return [text[i : i + budget] for i in range(0, len(text), budget)]


def _mean_pool_vectors(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dims = len(vectors[0])
    out = [0.0] * dims
    for vec in vectors:
        for i, value in enumerate(vec[:dims]):
            out[i] += float(value)
    n = float(len(vectors))
    return [value / n for value in out]


class LlmBackedDocGenerator:
    """Generate symbol docs via LiteLLM; fall back to heuristic on failure/stub.

    Prefer ``generate_many`` for ingest: one completion documents every changed
    symbol in a file (root cause of sync RPM cost was one complete per symbol).
    """

    _BATCH_CHUNK = 8

    def __init__(
        self,
        gateway: Any,
        *,
        fallback: _DocGenerator | None = None,
        settings: LlmGatewaySettings | None = None,
    ) -> None:
        self.gateway = gateway
        self.fallback = fallback or HeuristicDocGenerator()
        self.settings = settings or getattr(gateway, "settings", None) or LlmGatewaySettings.from_environment()

    def generate(self, symbol: GraphSymbol, neighbors: list[str]) -> str:
        return self.generate_many([(symbol, neighbors)])[0]

    def generate_many(self, items: list[tuple[GraphSymbol, list[str]]]) -> list[str]:
        if not items:
            return []
        if not docs_generation_enabled() or not getattr(self.settings, "enabled", False):
            return [self.fallback.generate(symbol, neighbors) for symbol, neighbors in items]

        out: list[str] = []
        for start in range(0, len(items), self._BATCH_CHUNK):
            chunk = items[start : start + self._BATCH_CHUNK]
            out.extend(self._generate_many_chunk(chunk))
        return out

    def _generate_many_chunk(self, items: list[tuple[GraphSymbol, list[str]]]) -> list[str]:
        route = resolve_route(
            "docs.generate",
            default_model=getattr(self.settings, "default_model", "") or "",
        )
        models = route.models_in_order()
        if not models:
            return [self.fallback.generate(symbol, neighbors) for symbol, neighbors in items]

        entries: list[str] = []
        for index, (symbol, neighbors) in enumerate(items):
            neighbor_text = ", ".join(neighbors[:8]) if neighbors else "none"
            body = (symbol.body or "")[:1200]
            entries.append(
                f"[{index}] kind={symbol.kind.value}\n"
                f"qualified_name={symbol.qualified_name}\n"
                f"signature={symbol.signature or symbol.name}\n"
                f"file_path={symbol.file_path}\n"
                f"related={neighbor_text}\n"
                f"body:\n{body}\n"
            )
        prompt = (
            "Document each code symbol below for a knowledge graph. "
            "Return ONLY a JSON object mapping each qualified_name string to a "
            "short plain-text doc string. Do not invent APIs. Keep each value concise.\n\n"
            + "\n---\n".join(entries)
        )
        max_tokens = max(int(route.max_tokens or 512), min(4096, 180 * len(items)))
        for model in models:
            try:
                result = self.gateway.complete(
                    CompletionRequest(
                        messages=(
                            ChatMessage(
                                role="system",
                                content=(
                                    "You document code symbols for a knowledge graph. "
                                    "Respond with JSON only: "
                                    '{"docs": {"qualified.name": "doc text", ...}}'
                                ),
                            ),
                            ChatMessage(role="user", content=prompt),
                        ),
                        model=model,
                        temperature=0.0,
                        max_tokens=max_tokens,
                        response_format_json=True,
                    )
                )
                parsed = _parse_docs_batch_json(result.content or "", items)
                if parsed is not None:
                    return [
                        text or self.fallback.generate(symbol, neighbors)
                        for text, (symbol, neighbors) in zip(parsed, items, strict=True)
                    ]
            except Exception:  # noqa: BLE001 — next model, then heuristic
                continue

        # Provider hang/timeout/error: keep ingest moving with heuristic docs.
        return [self.fallback.generate(symbol, neighbors) for symbol, neighbors in items]


def _parse_docs_batch_json(
    content: str,
    items: list[tuple[GraphSymbol, list[str]]],
) -> list[str] | None:
    """Map model JSON onto items; None means unusable payload (caller falls back).

    Missing keys become empty strings so the caller can heuristic-fill per symbol.
    """
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    docs_map: dict[str, str] = {}
    if isinstance(payload, dict):
        raw = payload.get("docs", payload)
        if isinstance(raw, dict):
            docs_map = {str(k): str(v).strip() for k, v in raw.items() if str(v).strip()}
        elif isinstance(raw, list):
            for row in raw:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("qualified_name") or row.get("name") or "").strip()
                val = str(row.get("doc") or row.get("documentation") or row.get("text") or "").strip()
                if key and val:
                    docs_map[key] = val
    if not docs_map:
        return None
    out: list[str] = []
    matched = 0
    for symbol, _neighbors in items:
        doc = docs_map.get(symbol.qualified_name) or docs_map.get(symbol.name) or ""
        if doc:
            matched += 1
        out.append(doc)
    return out if matched else None


class HybridEmbeddings:
    """Prefer local BGE, then LiteLLM embeddings, else LocalEmbeddingStub.

    Local BGE is the Stage-1 production path (dims=1024 for bge-large-en-v1.5).
    LiteLLM vectors are projected to ``dims`` only when lengths differ.
    """

    def __init__(
        self,
        gateway: Any | None = None,
        *,
        stub: LocalEmbeddingStub | None = None,
        dims: int = 1024,
        settings: LlmGatewaySettings | None = None,
        local: _Embedder | None = None,
    ) -> None:
        self.gateway = gateway
        self.stub = stub or LocalEmbeddingStub(dims=dims)
        self.dims = dims
        self.settings = settings or (
            getattr(gateway, "settings", None) if gateway is not None else None
        ) or LlmGatewaySettings.from_environment()
        self.local = local
        self.model = getattr(local, "model", None) or self.stub.model
        self._backend = "local_bge" if local is not None else "stub"

    def preload(self) -> None:
        """Force local BGE load at process start when configured.

        On failure, drop ``local`` so later ``embed`` / ``embed_many`` use LiteLLM/stub
        instead of hanging every parallel sync worker on a missing HF download.
        """
        if self.local is None:
            return
        preload_fn = getattr(self.local, "preload", None)
        if not callable(preload_fn):
            return
        try:
            preload_fn()
        except Exception:  # noqa: BLE001 — soft-fail to stub/LiteLLM for sync
            self.local = None
            self._backend = "stub"

    @property
    def backend_name(self) -> str:
        if getattr(self, "_backend", "") == "stub":
            return f"stub:{self.stub.model}"
        if self.local is not None and getattr(self, "_backend", "") == "local_bge":
            return f"local_bge:{getattr(self.local, 'model_name', self.model)}"
        if self.local is not None and not getattr(self, "_backend", ""):
            return f"local_bge:{getattr(self.local, 'model_name', self.model)}"
        if (
            self.gateway is not None
            and embeddings_generation_enabled()
            and getattr(self.settings, "enabled", False)
        ):
            return f"litellm:{getattr(self.settings, 'default_model', '') or 'embed'}"
        return f"stub:{self.stub.model}"

    def embed(self, text: str, *, is_query: bool = False) -> EmbeddingResult:
        rows = self.embed_many([text], is_query=is_query)
        return rows[0] if rows else self.stub.embed(text)

    def _pool_chunk_results(
        self,
        raw: list[EmbeddingResult],
        owners: list[int],
        count: int,
    ) -> list[EmbeddingResult]:
        buckets: list[list[list[float]]] = [[] for _ in range(count)]
        model = raw[0].model if raw else self.stub.model
        for item, owner in zip(raw, owners, strict=True):
            buckets[owner].append(list(item.vector))
        out: list[EmbeddingResult] = []
        for vecs in buckets:
            if not vecs:
                out.append(self.stub.embed(""))
                continue
            pooled = reduce_dims(_mean_pool_vectors(vecs), self.dims)
            out.append(EmbeddingResult(pooled, "ready", model, self.dims))
        return out

    def _embed_sized_many(
        self,
        chunks: list[str],
        *,
        is_query: bool = False,
    ) -> list[EmbeddingResult]:
        """Embed windows that already fit the model cap. Does not call embed()."""
        if not chunks:
            return []
        if self.local is not None:
            batch = getattr(self.local, "embed_many", None)
            if callable(batch):
                try:
                    results = list(batch(chunks, is_query=is_query))
                    if results:
                        self.model = results[0].model
                        self._backend = "local_bge"
                    return results
                except Exception:  # noqa: BLE001 — offline/cache miss → LiteLLM/stub
                    self.local = None
            else:
                embed_fn = getattr(self.local, "embed", None)
                if callable(embed_fn):
                    try:
                        out = []
                        for chunk in chunks:
                            try:
                                out.append(embed_fn(chunk, is_query=is_query))
                            except TypeError:
                                out.append(embed_fn(chunk))
                        if out:
                            self.model = out[0].model
                            self._backend = "local_bge"
                        return out
                    except Exception:  # noqa: BLE001
                        self.local = None
        if (
            self.gateway is not None
            and embeddings_generation_enabled()
            and getattr(self.settings, "enabled", False)
        ):
            route = resolve_route(
                "embed.symbol",
                default_model=getattr(self.settings, "default_model", "") or "",
            )
            models = route.models_in_order()
            if not models:
                raise RuntimeError(
                    "LiteLLM embeddings enabled but no embed model configured "
                    "(set ASTLOOM_LITELLM_MODEL_EMBED)"
                )
            gw_batch = getattr(self.gateway, "embed_many", None)
            if models and callable(gw_batch):
                last_error: Exception | None = None
                for model in models:
                    try:
                        raw = list(gw_batch(chunks, model=model))
                        out = [
                            EmbeddingResult(
                                reduce_dims(list(item.vector), self.dims),
                                "ready",
                                item.model,
                                self.dims,
                            )
                            for item in raw
                        ]
                        if out:
                            self.model = out[0].model
                            self._backend = "litellm"
                        return out
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        continue
                if last_error is not None:
                    raise RuntimeError(
                        f"LiteLLM embedding batch failed: {last_error}"
                    ) from last_error
            last_error = None
            for model in models:
                try:
                    out = []
                    for chunk in chunks:
                        result = self.gateway.embed(chunk, model=model)
                        out.append(
                            EmbeddingResult(
                                reduce_dims(list(result.vector), self.dims),
                                "ready",
                                result.model,
                                self.dims,
                            )
                        )
                    if out:
                        self.model = out[0].model
                        self._backend = "litellm"
                    return out
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    continue
            if last_error is not None and embeddings_generation_enabled():
                raise RuntimeError(f"LiteLLM embedding failed: {last_error}") from last_error
        if embeddings_generation_enabled() and (
            self.gateway is None or not getattr(self.settings, "enabled", False)
        ):
            raise RuntimeError(
                "LiteLLM embeddings enabled but gateway/settings unavailable"
            )
        self._backend = "stub"
        return [self.stub.embed(chunk) for chunk in chunks]

    def embed_many(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[EmbeddingResult]:
        if not texts:
            return []
        attempts = (
            {},
            {"max_tokens": 280, "chars_per_token": 2.0},
        )
        last_error: Exception | None = None
        for extra in attempts:
            groups = [chunk_embedding_input(text, **extra) for text in texts]
            flat: list[str] = []
            owners: list[int] = []
            for index, parts in enumerate(groups):
                for part in parts:
                    flat.append(part)
                    owners.append(index)
            try:
                raw = self._embed_sized_many(flat, is_query=is_query)
                if len(raw) != len(flat):
                    raise RuntimeError(
                        f"embedding batch returned {len(raw)} results for {len(flat)} chunks"
                    )
                pooled = self._pool_chunk_results(raw, owners, len(texts))
                if pooled:
                    self.model = pooled[0].model
                return pooled
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_embed_context_error(exc):
                    break
        if last_error is not None and embeddings_generation_enabled():
            raise RuntimeError(
                f"LiteLLM embedding batch failed: {last_error}"
            ) from last_error
        self._backend = "stub"
        return [self.stub.embed(text) for text in texts]

def build_embeddings(
    gateway: Any | None = None,
    *,
    settings: LlmGatewaySettings | None = None,
    environ: dict[str, str] | None = None,
) -> HybridEmbeddings:
    """Construct HybridEmbeddings from ASTLOOM_EMBEDDING_* / LiteLLM flags."""
    from .local_embeddings import LocalBgeEmbeddings, embedding_settings_from_env

    cfg = embedding_settings_from_env(environ)
    dims = int(cfg["dims"])
    local = None
    provider = str(cfg["provider"])
    if provider == "stub":
        return HybridEmbeddings(
            gateway,
            dims=dims,
            settings=settings,
            local=None,
            stub=LocalEmbeddingStub(dims=dims),
        )
    if cfg["local_enabled"] and provider == "local_bge":
        try:
            local = LocalBgeEmbeddings(
                model_name=str(cfg["model"]),
                cache_dir=str(cfg["cache_dir"]),
                dims=dims,
                device=str(cfg["device"]),
            )
        except Exception:  # noqa: BLE001 — keep stub if ST/torch unavailable at construct time
            local = None
    return HybridEmbeddings(
        gateway,
        dims=dims,
        settings=settings,
        local=local,
        stub=LocalEmbeddingStub(dims=dims),
    )


def maybe_preload_embeddings(embeddings: HybridEmbeddings, environ: dict[str, str] | None = None) -> bool:
    """If ASTLOOM_EMBEDDING_PRELOAD is set, load BGE at process start. Returns whether preload ran."""
    from .local_embeddings import embedding_settings_from_env

    if not embedding_settings_from_env(environ).get("preload"):
        return False
    embeddings.preload()
    return True
