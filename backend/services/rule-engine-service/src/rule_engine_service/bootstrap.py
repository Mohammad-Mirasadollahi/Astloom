from __future__ import annotations

from dataclasses import dataclass
import os

from .core import HeuristicJudge, RuleEngineService
from .domain.judge import Judge
from .postgres_store import PostgresStore


@dataclass(frozen=True)
class Settings:
    database_url: str
    rule_judge: str = "heuristic"

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("ASTLOOM_RULE_ENGINE_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("ASTLOOM_RULE_ENGINE_DATABASE_URL is required")
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("ASTLOOM_RULE_ENGINE_DATABASE_URL must use PostgreSQL")
        judge = os.environ.get("ASTLOOM_RULE_JUDGE", "heuristic").strip().lower() or "heuristic"
        return cls(database_url=database_url, rule_judge=judge)


@dataclass(frozen=True)
class ServiceContainer:
    """Process-scoped composition root output."""

    service: RuleEngineService
    settings: Settings | None = None

    def close(self) -> None:
        store = getattr(self.service, "store", None)
        closer = getattr(store, "close", None) if store is not None else None
        if callable(closer):
            closer()


def build_judge(settings: Settings) -> Judge:
    """Select Judge adapter: HeuristicJudge default; LiteLLM when ASTLOOM_RULE_JUDGE=litellm."""
    if settings.rule_judge == "litellm":
        from llm_gateway import LiteLlmGateway

        from .litellm_judge import LiteLLMJudge

        return LiteLLMJudge(LiteLlmGateway())
    if settings.rule_judge in {"", "heuristic", "default"}:
        return HeuristicJudge()
    raise RuntimeError(
        f"Unsupported ASTLOOM_RULE_JUDGE={settings.rule_judge!r}; expected heuristic or litellm"
    )


def build_container(settings: Settings | None = None) -> ServiceContainer:
    """Composition root: bind adapters and return a frozen service container."""
    resolved = settings or Settings.from_environment()
    return ServiceContainer(
        service=RuleEngineService(PostgresStore(resolved.database_url), build_judge(resolved)),
        settings=resolved,
    )


def build_service(settings: Settings | None = None) -> RuleEngineService:
    """Compatibility wrapper — prefer ``build_container`` for new wiring."""
    return build_container(settings).service


def shutdown_container(container: ServiceContainer | None) -> None:
    if container is not None:
        container.close()
