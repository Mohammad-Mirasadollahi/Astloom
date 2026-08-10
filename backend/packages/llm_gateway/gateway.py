"""
Module contract: LiteLLM application port for Astloom.

Role: Sole LLM egress via LiteLLM; optional native context compression before complete().
SoT/invariants: Settings from env; RPM gate; no third-party LLM proxy; no cloud compress.
Allowed failures: provider timeout/quota; ImportError/skip when compress package missing.
Forbidden: bypass LiteLLM; cross-tenant context retrieve; shipping secrets in prompts intentionally.
"""

from __future__ import annotations

import threading
from typing import Any, Protocol

from .providers import list_providers
from .rate_limit import RpmSessionGate, SessionMeta
from .settings import LlmGatewaySettings
from .types import CompletionRequest, CompletionResult, EmbeddingResult, ProviderInfo


class LlmGateway(Protocol):
    def complete(self, request: CompletionRequest) -> CompletionResult: ...

    def embed(self, text: str, *, model: str | None = None) -> EmbeddingResult: ...

    def list_providers(self) -> list[ProviderInfo]: ...

    def settings_public(self) -> dict[str, Any]: ...

    def rpm_sessions_snapshot(self) -> dict[str, Any]: ...


class ProviderQuotaTripped(RuntimeError):
    """Provider rate/quota limit tripped for this process; stop calling the LLM."""


def _maybe_compress_message_content(content: str) -> str:
    """Native Astloom compression before LiteLLM (doc 54). Opt-out: ASTLOOM_CONTEXT_COMPRESS=0."""
    import os

    flag = os.environ.get("ASTLOOM_CONTEXT_COMPRESS", "1").strip().lower()
    if flag in {"0", "false", "off", "no"}:
        return content
    if not isinstance(content, str) or len(content) < 2000:
        return content
    try:
        from context_compression import compress_payload, default_store
    except ImportError:
        return content
    result = compress_payload(content, content_type="auto")
    if result.skipped or result.compressed_chars >= result.original_chars:
        return content
    handle = default_store().put(
        content,
        scope={"tenant_id": "llm", "workspace_id": "local", "project_id": "process"},
        content_type=result.content_type,
        lossy=result.lossy,
        ttl_seconds=3600,
    )
    return (
        f"{result.compressed}\n\n"
        f"[astloom_context: handle={handle} chars_saved={result.chars_saved} "
        f"lossy={result.lossy}; retrieve via astloom_context_retrieve]"
    )


def _provider_from_model(model: str) -> str:
    if "/" in model:
        return model.split("/", 1)[0]
    return "openai"


def _is_timeout(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "timeout" in name or "timeout" in text or "timed out" in text


def _is_provider_quota_error(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    markers = (
        "rate limit",
        "ratelimit",
        "quota",
        "free-models-per-day",
        "tokens per day",
        "429",
    )
    return any(m in text for m in markers)


def _error_detail(exc: BaseException) -> str:
    return type(exc).__name__


def _effective_num_retries(configured: int) -> int:
    """LiteLLM retries need tenacity; without it, retries become a hard failure."""
    if configured <= 0:
        return 0
    import importlib.util

    if importlib.util.find_spec("tenacity") is None:
        return 0
    return int(configured)


_litellm_debug_on = False
_quota_lock = threading.Lock()
_quota_tripped = False
_quota_reason = ""


def reset_provider_quota_trip() -> None:
    """Test helper: clear the process-wide provider quota circuit breaker."""
    global _quota_tripped, _quota_reason
    with _quota_lock:
        _quota_tripped = False
        _quota_reason = ""


def provider_quota_tripped() -> bool:
    with _quota_lock:
        return _quota_tripped


def _raise_if_quota_tripped() -> None:
    with _quota_lock:
        if _quota_tripped:
            raise ProviderQuotaTripped(_quota_reason or "provider quota tripped")


def _maybe_trip_quota(exc: BaseException) -> None:
    global _quota_tripped, _quota_reason
    if isinstance(exc, ProviderQuotaTripped) or not _is_provider_quota_error(exc):
        return
    reason = str(exc).strip()[:300] or type(exc).__name__
    with _quota_lock:
        if _quota_tripped:
            return
        _quota_tripped = True
        _quota_reason = reason
    print(
        f"   !  LiteLLM provider quota/rate-limit — skipping further LLM calls this run "
        f"({reason})",
        flush=True,
    )


def _apply_litellm_runtime(litellm: Any, settings: LlmGatewaySettings) -> None:
    """Apply process-wide LiteLLM module knobs from gateway settings."""
    global _litellm_debug_on
    # Always suppress the noisy "Give Feedback / Get Help" tip; we log real errors.
    litellm.suppress_debug_info = True
    litellm.drop_params = settings.drop_params
    if settings.debug and not _litellm_debug_on:
        turn_on = getattr(litellm, "_turn_on_debug", None)
        if callable(turn_on):
            turn_on()
        else:
            litellm.set_verbose = True
        _litellm_debug_on = True


class LiteLlmGateway:
    """Infrastructure adapter: Astloom LLM port → LiteLLM SDK."""

    def __init__(self, settings: LlmGatewaySettings | None = None) -> None:
        self.settings = settings or LlmGatewaySettings.from_environment()
        self._rpm = RpmSessionGate(self.settings.rpm)

    def settings_public(self) -> dict[str, Any]:
        return self.settings.public_dict()

    def rpm_sessions_snapshot(self) -> dict[str, Any]:
        return self._rpm.snapshot()

    def list_providers(self) -> list[ProviderInfo]:
        return list_providers(include_litellm_dynamic=True)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if not self.settings.enabled:
            raise RuntimeError("LiteLLM gateway is disabled (ASTLOOM_LITELLM_ENABLED=false)")
        _raise_if_quota_tripped()
        model = (request.model or self.settings.default_model or "").strip()
        if not model:
            raise RuntimeError(
                "No model configured: set ASTLOOM_LITELLM_DEFAULT_MODEL or pass request.model"
            )
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "litellm package is required for LiteLlmGateway; install project dependencies"
            ) from exc

        session = self._rpm.acquire("complete", SessionMeta(model=model))
        try:
            _apply_litellm_runtime(litellm, self.settings)
            messages = [
                {"role": m.role, "content": _maybe_compress_message_content(m.content)}
                for m in request.messages
            ]
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": request.temperature,
                "timeout": self.settings.timeout_seconds,
                "num_retries": _effective_num_retries(self.settings.num_retries),
                "api_base": self.settings.api_base,
            }
            if self.settings.api_key:
                kwargs["api_key"] = self.settings.api_key
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens
            if request.response_format_json:
                kwargs["response_format"] = {"type": "json_object"}

            reasoning = self.settings.reasoning_payload(
                enabled_override=request.reasoning_enabled,
                effort_override=request.reasoning_effort,
            )
            if reasoning is not None:
                kwargs["extra_body"] = {"reasoning": reasoning}

            response = litellm.completion(**kwargs)
            content = _message_content(response)
            usage = {}
            raw_usage = getattr(response, "usage", None)
            if raw_usage is not None:
                usage = {
                    "prompt_tokens": getattr(raw_usage, "prompt_tokens", None),
                    "completion_tokens": getattr(raw_usage, "completion_tokens", None),
                    "total_tokens": getattr(raw_usage, "total_tokens", None),
                }
            used_model = getattr(response, "model", None) or model
            self._rpm.release(session, "ok", model=str(used_model))
            return CompletionResult(
                content=content,
                model=str(used_model),
                provider=_provider_from_model(str(used_model)),
                usage={k: v for k, v in usage.items() if v is not None},
                raw={"id": getattr(response, "id", None)},
            )
        except Exception as exc:
            _maybe_trip_quota(exc)
            status = "cancelled" if _is_timeout(exc) else "error"
            self._rpm.release(session, status, error_detail=_error_detail(exc))
            raise

    def embed(self, text: str, *, model: str | None = None) -> EmbeddingResult:
        if not self.settings.enabled:
            raise RuntimeError("LiteLLM gateway is disabled (ASTLOOM_LITELLM_ENABLED=false)")
        _raise_if_quota_tripped()
        resolved = (model or self.settings.default_model or "").strip()
        if not resolved:
            raise RuntimeError(
                "No embedding model configured: set ASTLOOM_LITELLM_MODEL_EMBED "
                "or ASTLOOM_LITELLM_DEFAULT_MODEL"
            )
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "litellm package is required for LiteLlmGateway; install project dependencies"
            ) from exc

        session = self._rpm.acquire("embed", SessionMeta(model=resolved))
        try:
            _apply_litellm_runtime(litellm, self.settings)
            kwargs: dict[str, Any] = {
                "model": resolved,
                "input": [text],
                "timeout": self.settings.timeout_seconds,
                "num_retries": _effective_num_retries(self.settings.num_retries),
                "api_base": self.settings.api_base,
            }
            if self.settings.api_key:
                kwargs["api_key"] = self.settings.api_key
            response = litellm.embedding(**kwargs)
            data = getattr(response, "data", None) or []
            if not data:
                raise RuntimeError("LiteLLM embedding returned no data")
            first = data[0]
            vector = getattr(first, "embedding", None)
            if vector is None and isinstance(first, dict):
                vector = first.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("LiteLLM embedding vector missing")
            used_model = getattr(response, "model", None) or resolved
            usage: dict[str, Any] = {}
            raw_usage = getattr(response, "usage", None)
            if raw_usage is not None:
                usage = {
                    "prompt_tokens": getattr(raw_usage, "prompt_tokens", None),
                    "total_tokens": getattr(raw_usage, "total_tokens", None),
                }
            self._rpm.release(session, "ok", model=str(used_model))
            return EmbeddingResult(
                vector=[float(v) for v in vector],
                model=str(used_model),
                provider=_provider_from_model(str(used_model)),
                usage={k: v for k, v in usage.items() if v is not None},
            )
        except Exception as exc:
            _maybe_trip_quota(exc)
            status = "cancelled" if _is_timeout(exc) else "error"
            self._rpm.release(session, status, error_detail=_error_detail(exc))
            raise


def _message_content(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None and isinstance(choices[0], dict):
        message = choices[0].get("message")
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return str(content or "")


class FakeLlmGateway:
    """Network-emulating gateway test double with RPM sessions but no external I/O."""

    def __init__(
        self,
        settings: LlmGatewaySettings | None = None,
        *,
        canned: str = "fake-completion",
    ) -> None:
        self.settings = settings or LlmGatewaySettings(
            enabled=True,
            api_base="http://127.0.0.1:32400",
            api_base_override="",
            api_base_is_auto=True,
            api_key="",
            default_model="fake/model",
            timeout_seconds=180.0,
            num_retries=3,
            rpm=30,
            host="127.0.0.1",
            port=32400,
            drop_params=True,
            debug=False,
            reasoning_enabled=False,
            reasoning_effort="",
        )
        self.canned = canned
        self.calls: list[CompletionRequest] = []
        self._rpm = RpmSessionGate(self.settings.rpm)

    def settings_public(self) -> dict[str, Any]:
        return self.settings.public_dict()

    def rpm_sessions_snapshot(self) -> dict[str, Any]:
        return self._rpm.snapshot()

    def list_providers(self) -> list[ProviderInfo]:
        return list_providers(include_litellm_dynamic=False)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        model = request.model or self.settings.default_model
        session = self._rpm.acquire("complete", SessionMeta(model=model))
        try:
            self.calls.append(request)
            self._rpm.release(session, "ok", model=model)
            return CompletionResult(
                content=self.canned,
                model=model,
                provider=_provider_from_model(model),
                usage={"total_tokens": 1},
            )
        except Exception as exc:
            self._rpm.release(session, "error", error_detail=_error_detail(exc))
            raise

    def embed(self, text: str, *, model: str | None = None) -> EmbeddingResult:
        resolved = model or self.settings.default_model
        session = self._rpm.acquire("embed", SessionMeta(model=resolved))
        try:
            seed = sum(ord(c) for c in text) % 97
            vector = [((seed + i) % 10) / 10.0 for i in range(8)]
            self._rpm.release(session, "ok", model=resolved)
            return EmbeddingResult(
                vector=vector,
                model=resolved,
                provider=_provider_from_model(resolved),
                usage={"total_tokens": 1},
            )
        except Exception as exc:
            self._rpm.release(session, "error", error_detail=_error_detail(exc))
            raise
