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


def truncate_embedding_input(
    text: str,
    *,
    max_tokens: int | None = None,
    chars_per_token: float | None = None,
) -> str:
    """Clamp embed text under the model context (BGE-large hosted = 512 tokens).

    Local SentenceTransformers silently truncates; OpenRouter BGE rejects over-limit
    prompts with HTTP 400. Use a conservative chars/token ratio — code+docs often
    tokenize denser than 4 chars/token (480×4 still produced 513-token rejects).
    """
    import os

    if max_tokens is None:
        raw = str(os.environ.get("ASTLOOM_EMBEDDING_MAX_INPUT_TOKENS", "480")).strip()
        try:
            max_tokens = int(raw) if raw else 480
        except ValueError:
            max_tokens = 480
    if chars_per_token is None:
        raw_cpt = str(os.environ.get("ASTLOOM_EMBEDDING_CHARS_PER_TOKEN", "3")).strip()
        try:
            chars_per_token = float(raw_cpt) if raw_cpt else 3.0
        except ValueError:
            chars_per_token = 3.0
    if max_tokens <= 0:
        return text
    max_chars = max(8, int(max_tokens * float(chars_per_token)))
    if len(text) <= max_chars:
        return text
    # Prefer keeping the head (qualified_name + start of docs).
    return text[: max_chars - 1].rstrip() + "…"


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
        text = truncate_embedding_input(text)
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
            if embeddings_generation_enabled() and (
                self.gateway is None or not getattr(self.settings, "enabled", False)
            ):
                raise RuntimeError(
                    "LiteLLM embeddings enabled but gateway/settings unavailable"
                )
            self._backend = "stub"
            return self.stub.embed(text)

        route = resolve_route(
            "embed.symbol",
            default_model=getattr(self.settings, "default_model", "") or "",
        )
        models = route.models_in_order()
        if not models:
            if embeddings_generation_enabled():
                raise RuntimeError(
                    "LiteLLM embeddings enabled but no embed model configured "
                    "(set ASTLOOM_LITELLM_MODEL_EMBED)"
                )
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
                # Hosted BGE-large is hard-capped at 512 tokens; shrink and retry once.
                msg = str(exc).lower()
                if "context length" in msg or "input tokens" in msg:
                    text = truncate_embedding_input(
                        text, max_tokens=360, chars_per_token=2.5
                    )
                    try:
                        result = self.gateway.embed(text, model=model)
                        vector = reduce_dims(list(result.vector), self.dims)
                        self.model = result.model
                        self._backend = "litellm"
                        return EmbeddingResult(
                            vector, "ready", result.model, self.dims
                        )
                    except Exception as retry_exc:  # noqa: BLE001
                        last_error = retry_exc
                continue

        # When LiteLLM embeddings are explicitly enabled, never silent-stub:
        # stub vectors (local-hash-v1) poison retrieval while looking "indexed".
        if last_error is not None and embeddings_generation_enabled():
            raise RuntimeError(f"LiteLLM embedding failed: {last_error}") from last_error
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
        texts = [truncate_embedding_input(t) for t in texts]
        if not texts:
            return []
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
        # Cloud path: one LiteLLM embedding call (+ one RPM acquire) per batch.
        if self.gateway is not None:
            route = resolve_route(
                "embeddings",
                settings=self.settings,
                allow_stub_default=True,
            )
            models = route.models_in_order()
            gw_batch = getattr(self.gateway, "embed_many", None)
            if models and callable(gw_batch):
                last_error: Exception | None = None
                for model in models:
                    try:
                        raw = list(gw_batch(texts, model=model))
                        out: list[EmbeddingResult] = []
                        for item in raw:
                            vector = reduce_dims(list(item.vector), self.dims)
                            out.append(
                                EmbeddingResult(
                                    vector, "ready", item.model, self.dims
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
                    raise RuntimeError(
                        f"LiteLLM embedding batch failed: {last_error}"
                    ) from last_error
                if route.allow_stub or last_error is not None:
                    self._backend = "stub"
                    return [self.stub.embed(text) for text in texts]
                raise RuntimeError(f"LiteLLM embedding batch failed: {last_error}")
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
