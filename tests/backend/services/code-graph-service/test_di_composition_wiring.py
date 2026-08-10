"""Unit tests for code-graph ServiceContainer wiring."""

from __future__ import annotations

from code_graph_service.api import build_app
from code_graph_service.bootstrap import ServiceContainer, build_service
from code_graph_service.core import CodeGraphService
from code_graph_service.testing import InMemoryStore


def test_build_app_attaches_container_for_injected_service():
    service = CodeGraphService(InMemoryStore())
    api = build_app(service)
    container = api.state.container
    assert isinstance(container, ServiceContainer)
    assert container.graph is service


def test_build_service_is_compat_wrapper_callable():
    # Constructor injection path remains for unit tests; build_service needs env for real stores.
    # Verify the symbol exists and ServiceContainer can wrap a fake.
    wrapped = ServiceContainer(graph=CodeGraphService(InMemoryStore()), settings=None)
    assert wrapped.graph.store is not None
    assert callable(build_service)


def test_service_close_releases_owned_resources_once():
    class Resource:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    store = Resource()
    embedding_index = Resource()
    service = CodeGraphService(
        store,
        embedding_index=embedding_index,
        vector_index=embedding_index,
    )

    service.close()

    assert store.closed == 1
    assert embedding_index.closed == 1
