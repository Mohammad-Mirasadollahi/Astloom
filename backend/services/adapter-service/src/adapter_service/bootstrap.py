from __future__ import annotations

from dataclasses import dataclass
import os

from .core import AdapterService
from .postgres_store import PostgresStore
from .trackers import build_tracker_registry


@dataclass(frozen=True)
class Settings:
    database_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("ASTLOOM_ADAPTER_SERVICE_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("ASTLOOM_ADAPTER_SERVICE_DATABASE_URL is required")
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("ASTLOOM_ADAPTER_SERVICE_DATABASE_URL must use PostgreSQL")
        return cls(database_url=database_url)


@dataclass(frozen=True)
class ServiceContainer:
    """Process-scoped composition root output."""

    service: AdapterService
    settings: Settings | None = None

    def close(self) -> None:
        store = getattr(self.service, "store", None)
        closer = getattr(store, "close", None) if store is not None else None
        if callable(closer):
            closer()


def build_container(settings: Settings | None = None) -> ServiceContainer:
    """Composition root: bind adapters and return a frozen service container."""
    resolved = settings or Settings.from_environment()
    service = AdapterService(
        PostgresStore(resolved.database_url),
        tracker_adapters=build_tracker_registry(),
    )
    return ServiceContainer(service=service, settings=resolved)


def build_service(settings: Settings | None = None) -> AdapterService:
    """Compatibility wrapper — prefer ``build_container`` for new wiring."""
    return build_container(settings).service


def shutdown_container(container: ServiceContainer | None) -> None:
    if container is not None:
        container.close()
