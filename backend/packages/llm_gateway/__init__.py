"""Astloom LiteLLM gateway — provider-agnostic LLM port + env settings."""

from __future__ import annotations

from .gateway import (
    FakeLlmGateway,
    LiteLlmGateway,
    LlmGateway,
    ProviderQuotaTripped,
    provider_quota_tripped,
    reset_provider_quota_trip,
)
from .providers import list_providers
from .rate_limit import HISTORY_SIZE, RpmLimiter, RpmSession, RpmSessionGate, SessionMeta
from .routing import (
    RouteDecision,
    clear_routing_profile_cache,
    docs_generation_enabled,
    embeddings_generation_enabled,
    load_routing_profile,
    resolve_route,
)
from .settings import LlmGatewaySettings, build_reasoning_payload, resolve_api_base
from .types import ChatMessage, CompletionRequest, CompletionResult, EmbeddingResult, ProviderInfo

__all__ = [
    "HISTORY_SIZE",
    "ChatMessage",
    "CompletionRequest",
    "CompletionResult",
    "EmbeddingResult",
    "FakeLlmGateway",
    "LiteLlmGateway",
    "LlmGateway",
    "LlmGatewaySettings",
    "ProviderInfo",
    "ProviderQuotaTripped",
    "RouteDecision",
    "RpmLimiter",
    "RpmSession",
    "RpmSessionGate",
    "SessionMeta",
    "build_reasoning_payload",
    "clear_routing_profile_cache",
    "docs_generation_enabled",
    "embeddings_generation_enabled",
    "list_providers",
    "load_routing_profile",
    "provider_quota_tripped",
    "reset_provider_quota_trip",
    "resolve_api_base",
    "resolve_route",
]
