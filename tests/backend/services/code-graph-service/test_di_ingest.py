"""Integration: ingest emits di_injection CALLS for FastAPI Depends."""

from __future__ import annotations

from code_graph_service.application.service import CodeGraphService
from code_graph_service.domain.models import Scope
from code_graph_service.testing import InMemoryStore


def test_ingest_emits_di_injection_edge():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p-di")
    source = """
from fastapi import Depends

def get_db():
    return 1

def read_item(db = Depends(get_db)):
    return db
"""
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c1",
        idempotency_key="k1",
        payload={"file_path": "api.py", "source": source, "language": "python"},
    )
    edges = [
        e
        for e in store.list_edges(scope)
        if e.rel_type == "CALLS" and (e.metadata or {}).get("provenance") == "di_injection"
    ]
    assert edges, "expected di_injection CALLS edge"
    assert edges[0].confidence.value == "probable"
    assert edges[0].metadata.get("framework") == "fastapi"


def test_ingest_emits_nestjs_di_injection_edge():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p-di-ts")
    provider = """
export class UsersService {
  find() { return 1; }
}
"""
    consumer = """
@Injectable()
export class OrdersService {
  constructor(private readonly users: UsersService) {}
  run() { return this.users.find(); }
}
"""
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c1",
        idempotency_key="k1",
        payload={"file_path": "users.ts", "source": provider, "language": "typescript"},
    )
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c2",
        idempotency_key="k2",
        payload={"file_path": "orders.ts", "source": consumer, "language": "typescript"},
    )
    edges = [
        e
        for e in store.list_edges(scope)
        if e.rel_type == "CALLS" and (e.metadata or {}).get("provenance") == "di_injection"
    ]
    assert edges
    assert any((e.metadata or {}).get("framework") in {"nestjs_or_ts", "nestjs"} for e in edges)


def test_ingest_emits_spring_di_injection_edge():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p-di-java")
    provider = """
package com.acme;
public class UsersService {
  public int find() { return 1; }
}
"""
    consumer = """
package com.acme;
import org.springframework.beans.factory.annotation.Autowired;
public class OrdersService {
  @Autowired
  private UsersService users;
  public int run() { return users.find(); }
}
"""
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c1",
        idempotency_key="k1",
        payload={"file_path": "UsersService.java", "source": provider, "language": "java"},
    )
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c2",
        idempotency_key="k2",
        payload={"file_path": "OrdersService.java", "source": consumer, "language": "java"},
    )
    edges = [
        e
        for e in store.list_edges(scope)
        if e.rel_type == "CALLS" and (e.metadata or {}).get("provenance") == "di_injection"
    ]
    assert edges
    assert any((e.metadata or {}).get("framework") == "spring" for e in edges)


def test_ingest_emits_wire_di_injection_edge():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p-di-wire")
    provider = """
package acme

func NewUsersService() *UsersService { return &UsersService{} }

type UsersService struct{}

func (s *UsersService) Find() int { return 1 }
"""
    consumer = """
package acme

import "github.com/google/wire"

func InitializeApp() *OrdersService {
        panic(wire.Build(NewUsersService, NewOrdersService))
}

type OrdersService struct{ users *UsersService }

func NewOrdersService(users *UsersService) *OrdersService {
        return &OrdersService{users: users}
}
"""
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c1",
        idempotency_key="k1",
        payload={"file_path": "users.go", "source": provider, "language": "go"},
    )
    svc.ingest_file(
        scope,
        actor_id="test",
        correlation_id="c2",
        idempotency_key="k2",
        payload={"file_path": "wire.go", "source": consumer, "language": "go"},
    )
    edges = [
        e
        for e in store.list_edges(scope)
        if e.rel_type == "CALLS" and (e.metadata or {}).get("provenance") == "di_injection"
    ]
    assert edges
    assert any((e.metadata or {}).get("framework") == "wire" for e in edges)
