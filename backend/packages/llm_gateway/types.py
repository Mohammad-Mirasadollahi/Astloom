"""Types for the Astloom LLM gateway port."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    messages: tuple[ChatMessage, ...]
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    response_format_json: bool = False
    # None → use ASTLOOM_LITELLM_REASONING_*; True/False overrides for this call.
    reasoning_enabled: bool | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class CompletionResult:
    content: str
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderInfo:
    """One LLM provider entry for discovery / admin UIs."""

    id: str
    name: str
    litellm_prefix: str
    env_keys: tuple[str, ...]
    configured: bool
    sample_models: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "litellm_prefix": self.litellm_prefix,
            "env_keys": list(self.env_keys),
            "configured": self.configured,
            "sample_models": list(self.sample_models),
        }
