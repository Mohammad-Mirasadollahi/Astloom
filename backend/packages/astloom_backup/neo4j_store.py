"""Neo4j scoped graph export/import for code-graph SoR."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import re

from astloom_backup.remap import remap_row
from astloom_backup.scope import Scope
from astloom_backup.secrets import assert_no_secrets

_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_token(value: str) -> str:
    return value if _TOKEN.match(value or "") else ""


def neo4j_configured(env: dict[str, str] | None = None) -> bool:
    e = env if env is not None else os.environ
    pwd = str(e.get("ASTLOOM_NEO4J_PASSWORD") or "").strip()
    if not pwd or pwd in {"replace-with-a-local-secret", "changeme", "password", "neo4j"}:
        return False
    return True


def graph_store_expects_neo4j(env: dict[str, str] | None = None) -> bool:
    e = env if env is not None else os.environ
    mode = (
        str(e.get("ASTLOOM_CODE_GRAPH_STORE") or "").strip().lower()
        or str(e.get("ASTLOOM_MCP_GRAPH_MODE") or "").strip().lower()
    )
    return mode == "neo4j"


def require_neo4j_for_export(env: dict[str, str] | None = None) -> None:
    """Fail closed when host graph SoR is Neo4j but credentials are missing."""
    if graph_store_expects_neo4j(env) and not neo4j_configured(env):
        raise RuntimeError(
            "code graph store is neo4j but ASTLOOM_NEO4J_PASSWORD is unset/placeholder; "
            "refuse export that would silently omit graph data"
        )


def _driver():
    from neo4j import GraphDatabase

    uri = os.environ.get("ASTLOOM_NEO4J_URI", "bolt://127.0.0.1:7687").strip()
    user = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j").strip() or "neo4j"
    password = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "").strip()
    return GraphDatabase.driver(uri, auth=(user, password))


def count_scope_nodes(scope: Scope) -> int:
    if not neo4j_configured():
        return 0
    driver = _driver()
    database = os.environ.get("ASTLOOM_NEO4J_DATABASE", "neo4j").strip() or "neo4j"
    try:
        with driver.session(database=database) as session:
            rec = session.run(
                """
                MATCH (n)
                WHERE n.tenant_id = $tenant_id
                  AND n.workspace_id = $workspace_id
                  AND n.project_id = $project_id
                RETURN count(n) AS c
                """,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            ).single()
            return int((rec or {}).get("c") or 0)
    finally:
        driver.close()


def export_neo4j(scope: Scope, dest_dir: Path) -> int:
    if not neo4j_configured():
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    driver = _driver()
    database = os.environ.get("ASTLOOM_NEO4J_DATABASE", "neo4j").strip() or "neo4j"
    nodes_path = dest_dir / "nodes.jsonl"
    rels_path = dest_dir / "relationships.jsonl"
    node_count = 0
    try:
        with driver.session(database=database) as session:
            with nodes_path.open("w", encoding="utf-8") as nf:
                for rec in session.run(
                    """
                    MATCH (n)
                    WHERE n.tenant_id = $tenant_id
                      AND n.workspace_id = $workspace_id
                      AND n.project_id = $project_id
                    RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props
                    """,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                ):
                    row = {
                        "element_id": rec["eid"],
                        "labels": list(rec["labels"] or []),
                        "properties": dict(rec["props"] or {}),
                    }
                    assert_no_secrets(row, context="neo4j.nodes")
                    nf.write(json.dumps(row, sort_keys=True, default=str) + "\n")
                    node_count += 1
            with rels_path.open("w", encoding="utf-8") as rf:
                for rec in session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE a.tenant_id = $tenant_id AND a.workspace_id = $workspace_id
                      AND a.project_id = $project_id
                      AND b.tenant_id = $tenant_id AND b.workspace_id = $workspace_id
                      AND b.project_id = $project_id
                    RETURN elementId(a) AS start_eid, elementId(b) AS end_eid,
                           type(r) AS type, properties(r) AS props
                    """,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                ):
                    row = {
                        "start_element_id": rec["start_eid"],
                        "end_element_id": rec["end_eid"],
                        "type": rec["type"],
                        "properties": dict(rec["props"] or {}),
                    }
                    assert_no_secrets(row, context="neo4j.relationships")
                    rf.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    finally:
        driver.close()
    if node_count == 0:
        nodes_path.unlink(missing_ok=True)
        rels_path.unlink(missing_ok=True)
    return node_count


def wipe_neo4j(scope: Scope, *, batch_size: int = 500) -> dict[str, int]:
    """Delete scoped graph data in batches (full-scope DETACH DELETE OOMs on large graphs)."""
    if not neo4j_configured():
        return {"nodes": 0, "relationships": 0}
    limit = max(1, int(batch_size))
    driver = _driver()
    database = os.environ.get("ASTLOOM_NEO4J_DATABASE", "neo4j").strip() or "neo4j"
    deleted_nodes = 0
    try:
        with driver.session(database=database) as session:
            while True:
                rec = session.run(
                    """
                    MATCH (n)
                    WHERE n.tenant_id = $tenant_id
                      AND n.workspace_id = $workspace_id
                      AND n.project_id = $project_id
                    WITH n LIMIT $limit
                    DETACH DELETE n
                    RETURN count(*) AS c
                    """,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                    limit=limit,
                ).single()
                batch = int((rec or {}).get("c") or 0)
                deleted_nodes += batch
                if batch == 0:
                    break
        return {"relationships": 0, "nodes": deleted_nodes}
    finally:
        driver.close()


def import_neo4j(
    neo_dir: Path,
    *,
    source: Scope,
    target: Scope,
) -> int:
    nodes_path = neo_dir / "nodes.jsonl"
    rels_path = neo_dir / "relationships.jsonl"
    if not nodes_path.is_file():
        return 0
    if not neo4j_configured():
        raise RuntimeError("Neo4j is required to restore code_graph neo4j payload")

    driver = _driver()
    database = os.environ.get("ASTLOOM_NEO4J_DATABASE", "neo4j").strip() or "neo4j"
    eid_map: dict[str, Any] = {}
    imported = 0
    try:
        with driver.session(database=database) as session:
            for line in nodes_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                props = remap_row(dict(row.get("properties") or {}), source=source, target=target)
                assert_no_secrets(props, context="neo4j.nodes")
                labels = [
                    _safe_token(str(x))
                    for x in (row.get("labels") or [])
                    if _safe_token(str(x))
                ]
                label_sql = ":".join(labels) if labels else "BackupNode"
                rec = session.run(
                    f"CREATE (n:{label_sql}) SET n = $props RETURN elementId(n) AS eid",
                    props=props,
                ).single()
                eid_map[str(row["element_id"])] = rec["eid"]
                imported += 1
            if rels_path.is_file():
                missing_ends = 0
                for line in rels_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    start = eid_map.get(str(row["start_element_id"]))
                    end = eid_map.get(str(row["end_element_id"]))
                    if start is None or end is None:
                        missing_ends += 1
                        continue
                    rel_type = _safe_token(str(row.get("type") or "RELATED")) or "RELATED"
                    props = dict(row.get("properties") or {})
                    assert_no_secrets(props, context="neo4j.relationships")
                    session.run(
                        f"""
                        MATCH (a), (b)
                        WHERE elementId(a) = $start AND elementId(b) = $end
                        CREATE (a)-[r:{rel_type}]->(b)
                        SET r = $props
                        """,
                        start=start,
                        end=end,
                        props=props,
                    )
                if missing_ends:
                    raise RuntimeError(
                        f"neo4j restore dropped {missing_ends} relationship(s) "
                        "(endpoint nodes missing from eid map)"
                    )
    finally:
        driver.close()
    return imported
