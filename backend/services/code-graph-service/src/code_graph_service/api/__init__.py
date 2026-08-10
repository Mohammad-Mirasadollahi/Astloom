"""FastAPI composition root for code-graph-service.

Owns HTTP transport only: request schemas, route registration, and
``app.state.container``. Domain logic stays in ``application`` / ``domain``.
"""

from fastapi import FastAPI

from ..bootstrap import ServiceContainer, build_container
from ..core import CodeGraphService
from . import edit_session, generation, health, ingest, intelligence, llm, query
from .common import install_exception_handlers, is_loopback_request

# Tests import the private name historically used by the monolith.
_is_loopback_request = is_loopback_request

__all__ = ["app", "build_app", "_is_loopback_request"]


def build_app(
    service: CodeGraphService | None = None,
    *,
    container: ServiceContainer | None = None,
) -> FastAPI:
    """Compose FastAPI with a process-scoped ``ServiceContainer`` on ``app.state``."""
    if container is not None and service is not None and service is not container.graph:
        raise ValueError("pass either service or container, not conflicting both")
    if container is None:
        if service is not None:
            container = ServiceContainer(graph=service, settings=None)
        else:
            container = build_container()
    service = container.graph
    api = FastAPI(title="Astloom Code Graph API", version="1.0.0")
    api.state.container = container

    install_exception_handlers(api)
    ingest.register(api, service)
    query.register(api, service)
    intelligence.register(api, service)
    edit_session.register(api, service)
    generation.register(api, service)
    llm.register(api, service)
    health.register(api)

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
