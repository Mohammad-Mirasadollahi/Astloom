"""Store export/import ports (one adapter per store_id; orchestrator sequences them)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import psycopg

from astloom_backup.neo4j_store import export_neo4j, import_neo4j, require_neo4j_for_export
from astloom_backup.pg import export_table, import_table
from astloom_backup.remap import remap_row
from astloom_backup.scope import Scope
from astloom_backup.tables import STORE_ORDER, TableSpec, tables_for_store


class StorePort(Protocol):
    store_id: str

    def export_scope(self, conn: psycopg.Connection, scope: Scope, dest: Path) -> int: ...

    def import_scope(
        self,
        conn: psycopg.Connection,
        store_dir: Path,
        *,
        source: Scope,
        target: Scope,
        require_insert: bool,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class PgStorePort:
    store_id: str
    tables: tuple[TableSpec, ...]

    def export_scope(self, conn: psycopg.Connection, scope: Scope, dest: Path) -> int:
        total = 0
        dest.mkdir(parents=True, exist_ok=True)
        for spec in self.tables:
            path = dest / f"{spec.table}.jsonl"
            n = export_table(conn, spec, scope, path)
            total += n
            if n == 0 and path.exists() and path.stat().st_size == 0:
                path.unlink(missing_ok=True)
        if self.store_id == "code_graph":
            require_neo4j_for_export()
            total += export_neo4j(scope, dest / "neo4j")
        return total

    def import_scope(
        self,
        conn: psycopg.Connection,
        store_dir: Path,
        *,
        source: Scope,
        target: Scope,
        require_insert: bool,
    ) -> int:
        total = 0
        for spec in self.tables:
            path = store_dir / f"{spec.table}.jsonl"
            if not path.is_file():
                continue
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"invalid row in {path}")
                rows.append(remap_row(row, source=source, target=target))
            total += import_table(
                conn, spec, iter(rows), require_insert=require_insert
            )
        if self.store_id == "code_graph":
            neo_dir = store_dir / "neo4j"
            if neo_dir.is_dir():
                total += import_neo4j(neo_dir, source=source, target=target)
        return total


def build_ports() -> list[StorePort]:
    ports: list[StorePort] = []
    for store_id in STORE_ORDER:
        if store_id == "local":
            continue
        tables = tuple(tables_for_store(store_id))
        if tables:
            ports.append(PgStorePort(store_id=store_id, tables=tables))
    return ports
