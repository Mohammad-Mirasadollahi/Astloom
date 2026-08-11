"""Wire LiteLLM docs generation and embeddings into code-graph-service."""

from __future__ import annotations

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


class LlmBackedDocGenerator:
    """Generate symbol docs via LiteLLM; fall back to heuristic on failure/stub."""

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
        if not docs_generation_enabled() or not getattr(self.settings, "enabled", False):
            return self.fallback.generate(symbol, neighbors)

        route = resolve_route(
            "docs.generate",
            default_model=getattr(self.settings, "default_model", "") or "",
        )
        models = route.models_in_order()
        if not models:
            return self.fallback.generate(symbol, neighbors)

        neighbor_text = ", ".join(neighbors[:12]) if neighbors else "none"
        prompt = (
            "Write concise developer documentation for a code symbol. "
            "Use plain text with short lines. Do not invent APIs.\n\n"
            f"kind: {symbol.kind.value}\n"
            f"qualified_name: {symbol.qualified_name}\n"
            f"signature: {symbol.signature or symbol.name}\n"
            f"file_path: {symbol.file_path}\n"
            f"related: {neighbor_text}\n"
            f"body:\n{(symbol.body or '')[:4000]}\n"
        )
        last_error: Exception | None = None
        for model in models:
            try:
                result = self.gateway.complete(
                    CompletionRequest(
                        messages=(
                            ChatMessage(
                                role="system",
                                content="You document code symbols for a knowledge graph.",
                            ),
                            ChatMessage(role="user", content=prompt),
                        ),
                        model=model,
                        temperature=0.0,
                        max_tokens=route.max_tokens,
                    )
                )
                text = (result.content or "").strip()
                if text:
                    return text
            except Exception as exc:  # noqa: BLE001 — fall back / try next model
                last_error = exc
                continue

        if route.allow_stub or last_error is not None:
            return self.fallback.generate(symbol, neighbors)
        raise RuntimeError(f"LiteLLM docs generation failed: {last_error}")


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
        if self.local is not None:
            embed_fn = getattr(self.local, "embed", None)
            if callable(embed_fn):
                try:
                    try:
                        result = embed_fn(text, is_query=is_query)  # type: ignore[call-arg]
                    except TypeError:
                        result = embed_fn(text)
                    self.model = result.model
                    self._backend = "local_bge"
                    return result
                except Exception:  # noqa: BLE001 — offline/cache miss → LiteLLM/stub
                    # Drop broken local so subsequent calls skip repeated HF loads.
                    self.local = None
            else:
                result = self.stub.embed(text)
                self.model = result.model
                self._backend = "stub"
                return result

        if (
            self.gateway is None
            or not embeddings_generation_enabled()
            or not getattr(self.settings, "enabled", False)
        ):
            self._backend = "stub"
            return self.stub.embed(text)

        route = resolve_route(
            "embed.symbol",
            default_model=getattr(self.settings, "default_model", "") or "",
        )
        models = route.models_in_order()
        if not models:
            self._backend = "stub"
            return self.stub.embed(text)

        last_error: Exception | None = None
        for model in models:
            try:
                result = self.gateway.embed(text, model=model)
                vector = reduce_dims(list(result.vector), self.dims)
                self.model = result.model
                self._backend = "litellm"
                return EmbeddingResult(vector, "ready", result.model, self.dims)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        if route.allow_stub or last_error is not None:
            self._backend = "stub"
            return self.stub.embed(text)
        raise RuntimeError(f"LiteLLM embedding failed: {last_error}")

    def embed_many(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[EmbeddingResult]:
        if self.local is not None:
            batch = getattr(self.local, "embed_many", None)
            if callable(batch):
                try:
                    results = list(batch(texts, is_query=is_query))
                    if results:
                        self.model = results[0].model
                        self._backend = "local_bge"
                    return results
                except Exception:  # noqa: BLE001 — offline/cache miss → per-text fallback
                    self.local = None
        return [self.embed(text, is_query=is_query) for text in texts]

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
