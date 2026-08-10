from __future__ import annotations

from dataclasses import dataclass
import os

from .core import IdentityAccessService
from .postgres_store import PostgresStore


@dataclass(frozen=True)
class Settings:
    database_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("ASTLOOM_IDENTITY_ACCESS_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("ASTLOOM_IDENTITY_ACCESS_DATABASE_URL is required")
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("ASTLOOM_IDENTITY_ACCESS_DATABASE_URL must use PostgreSQL")
        return cls(database_url=database_url)


@dataclass(frozen=True)
class ServiceContainer:
    """Process-scoped composition root output."""

    service: IdentityAccessService
    settings: Settings | None = None

    def close(self) -> None:
        store = getattr(self.service, "store", None)
        closer = getattr(store, "close", None) if store is not None else None
        if callable(closer):
            closer()


def build_container(settings: Settings | None = None) -> ServiceContainer:
    """Composition root: bind adapters and return a frozen service container."""
    resolved = settings or Settings.from_environment()
    return ServiceContainer(service=IdentityAccessService(PostgresStore(resolved.database_url)), settings=resolved)


def build_service(settings: Settings | None = None) -> IdentityAccessService:
    """Compatibility wrapper — prefer ``build_container`` for new wiring."""
    return build_container(settings).service


def shutdown_container(container: ServiceContainer | None) -> None:
    if container is not None:
        container.close()
