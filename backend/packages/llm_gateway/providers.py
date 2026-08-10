"""Provider discovery for LiteLLM (env-aware catalog)."""

from __future__ import annotations

import os
from typing import Iterable

from .types import ProviderInfo

# Stable catalog — LiteLLM prefixes and typical env keys. Extended at runtime when litellm is importable.
_PROVIDER_CATALOG: tuple[dict[str, object], ...] = (
    {
        "id": "openai",
        "name": "OpenAI",
        "litellm_prefix": "openai/",
        "env_keys": ("OPENAI_API_KEY",),
        "sample_models": ("gpt-4o", "gpt-4o-mini", "text-embedding-3-small"),
    },
    {
        "id": "azure",
        "name": "Azure OpenAI",
        "litellm_prefix": "azure/",
        "env_keys": ("AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION"),
        "sample_models": ("azure/<deployment>",),
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "litellm_prefix": "anthropic/",
        "env_keys": ("ANTHROPIC_API_KEY",),
        "sample_models": ("claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"),
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "litellm_prefix": "ollama/",
        "env_keys": ("OLLAMA_API_BASE",),
        "sample_models": ("ollama/qwen2.5-coder", "ollama/llama3.2"),
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "litellm_prefix": "openrouter/",
        "env_keys": ("OPENROUTER_API_KEY",),
        "sample_models": ("openrouter/auto",),
    },
    {
        "id": "groq",
        "name": "Groq",
        "litellm_prefix": "groq/",
        "env_keys": ("GROQ_API_KEY",),
        "sample_models": ("groq/llama-3.3-70b-versatile",),
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "litellm_prefix": "gemini/",
        "env_keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "sample_models": ("gemini/gemini-2.0-flash",),
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "litellm_prefix": "mistral/",
        "env_keys": ("MISTRAL_API_KEY",),
        "sample_models": ("mistral/mistral-small-latest",),
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "litellm_prefix": "deepseek/",
        "env_keys": ("DEEPSEEK_API_KEY",),
        "sample_models": ("deepseek/deepseek-chat",),
    },
    {
        "id": "litellm_proxy",
        "name": "LiteLLM Proxy",
        "litellm_prefix": "",
        "env_keys": ("ASTLOOM_LITELLM_API_KEY", "LITELLM_API_KEY", "ASTLOOM_LITELLM_API_BASE"),
        "sample_models": ("<proxy-model-alias>",),
    },
)


def _env_configured(keys: Iterable[str]) -> bool:
    for key in keys:
        if os.environ.get(key, "").strip():
            return True
    return False


def list_providers(*, include_litellm_dynamic: bool = True) -> list[ProviderInfo]:
    """Return known providers with configured=true when related env keys are set."""
    providers: list[ProviderInfo] = []
    for row in _PROVIDER_CATALOG:
        env_keys = tuple(str(k) for k in (row["env_keys"] or ()))  # type: ignore[index]
        samples = tuple(str(m) for m in (row.get("sample_models") or ()))
        providers.append(
            ProviderInfo(
                id=str(row["id"]),
                name=str(row["name"]),
                litellm_prefix=str(row["litellm_prefix"]),
                env_keys=env_keys,
                configured=_env_configured(env_keys),
                sample_models=samples,
            )
        )

    if include_litellm_dynamic:
        providers.extend(_dynamic_litellm_providers({p.id for p in providers}))
    return providers


def _dynamic_litellm_providers(known_ids: set[str]) -> list[ProviderInfo]:
    """Optionally extend catalog from litellm.models_by_provider when installed."""
    try:
        import litellm
    except ImportError:
        return []

    by_provider = getattr(litellm, "models_by_provider", None)
    if not isinstance(by_provider, dict):
        return []

    extra: list[ProviderInfo] = []
    for name, models in sorted(by_provider.items(), key=lambda item: str(item[0])):
        provider_id = str(name).strip().lower().replace(" ", "_")
        if not provider_id or provider_id in known_ids:
            continue
        model_list = models if isinstance(models, (list, tuple, set)) else []
        samples = tuple(str(m) for m in list(model_list)[:5])
        extra.append(
            ProviderInfo(
                id=provider_id,
                name=str(name),
                litellm_prefix=f"{provider_id}/",
                env_keys=(),
                configured=False,
                sample_models=samples,
            )
        )
    return extra
