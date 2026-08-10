"""LiteLLM provider / session / completion HTTP routes."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from ..core import CodeGraphService
from .common import is_loopback_request
from .schemas import LlmCompleteRequest


def register(api: FastAPI, service: CodeGraphService) -> None:
    @api.get("/api/v1/llm/providers")
    async def llm_providers() -> dict[str, Any]:
        """List LiteLLM providers (configured flags from env keys)."""
        providers = service.llm_providers()
        return {
            "providers": providers,
            "configured_count": sum(1 for p in providers if p.get("configured")),
        }

    @api.get("/api/v1/llm/config")
    async def llm_config() -> dict[str, Any]:
        """Public LiteLLM settings (Base URL, timeout, retries — no secrets)."""
        return service.llm_config()

    @api.get("/api/v1/llm/sessions")
    async def llm_sessions(request: Request) -> dict[str, Any]:
        """Return process-local RPM session details to local operators."""
        if not is_loopback_request(request):
            raise HTTPException(status_code=403, detail="LLM session details are local-only")
        return service.llm_sessions_snapshot()

    @api.post("/api/v1/llm/complete")
    async def llm_complete(body: LlmCompleteRequest) -> dict[str, Any]:
        if service.llm is None:
            raise HTTPException(status_code=503, detail="LLM gateway is not configured on this service")
        from llm_gateway import ChatMessage, CompletionRequest

        try:
            result = service.llm.complete(
                CompletionRequest(
                    messages=(
                        ChatMessage(role="system", content=body.system),
                        ChatMessage(role="user", content=body.prompt),
                    ),
                    model=body.model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    response_format_json=body.response_format_json,
                    reasoning_enabled=body.reasoning_enabled,
                    reasoning_effort=body.reasoning_effort,
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "content": result.content,
            "model": result.model,
            "provider": result.provider,
            "usage": result.usage,
        }
