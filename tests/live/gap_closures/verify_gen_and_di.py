#!/usr/bin/env python3
"""Verify generation-context + Neo4j DI with correct CODE_REL query."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/Astloom")
OUT = ROOT / "tests" / "artifacts" / "gap-live"
ASTLOOM = str(ROOT / ".venv" / "bin" / "astloom")

env = os.environ.copy()
env.update(
    {
        "ASTLOOM_EMBEDDING_PROVIDER": "stub",
        "ASTLOOM_LITELLM_ENABLED": "false",
        "ASTLOOM_NEO4J_PASSWORD": "astloom-local-dev-secret",
        "ASTLOOM_NEO4J_BOLT_PORT": "32287",
        "PATH": "/opt/Astloom/.venv/bin:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/root"),
    }
)

gen = subprocess.run(
    [
        ASTLOOM,
        "graph",
        "generation-context",
        "--tenant",
        "mir",
        "--workspace",
        "dev",
        "--project",
        "gap-live-002",
        "--qualified-name",
        "com.acme.OrdersService",
        "--max-symbols",
        "6",
    ],
    cwd=str(ROOT),
    env=env,
    capture_output=True,
    text=True,
    timeout=120,
)
gout = gen.stdout + gen.stderr
print("gen_rc", gen.returncode)
print(gout[-1200:])

payload = None
try:
    payload = json.loads(gen.stdout.strip() or "{}")
except Exception:
    # CLI may print non-json noise; try last {...}
    start = gout.find("{")
    end = gout.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(gout[start : end + 1])
        except Exception:
            payload = None

from neo4j import GraphDatabase

with GraphDatabase.driver(
    "bolt://127.0.0.1:32287", auth=("neo4j", "astloom-local-dev-secret")
) as d:
    with d.session() as s:
        di = s.run(
            """
            MATCH (a)-[r:CODE_REL]->(b)
            WHERE r.rel_type = 'CALLS'
              AND r.project_id = 'gap-live-002'
              AND r.metadata_json CONTAINS '"provenance": "di_injection"'
            RETURN r.metadata_json AS meta, a.qualified_name AS aq, b.qualified_name AS bq
            """
        ).data()

frameworks = {json.loads(r["meta"]).get("framework") for r in di}
print("neo4j_di", len(di), frameworks)
for r in di:
    print(json.loads(r["meta"]).get("framework"), r["aq"], "->", r["bq"])

read_model = None
if isinstance(payload, dict):
    read_model = payload.get("read_model_id") or (payload.get("context") or {}).get(
        "read_model_id"
    )
    # dig
    blob = json.dumps(payload)
    if "read_model" in blob:
        print("payload_has_read_model_token", True)

results = {
    "generation_rc": gen.returncode,
    "generation_ok": gen.returncode == 0 and "com.acme.OrdersService" in gout,
    "read_model_id": read_model,
    "payload_keys": list(payload.keys()) if isinstance(payload, dict) else None,
    "neo4j_di_count": len(di),
    "neo4j_frameworks": sorted(x for x in frameworks if x),
    "neo4j_di_ok": frameworks >= {"spring", "wire"},
}
results["ok"] = bool(results["generation_ok"] and results["neo4j_di_ok"])
OUT.joinpath("live_round3_gen_di.json").write_text(
    json.dumps(results, indent=2)[:4000], encoding="utf-8"
)
# merge into live_round3
r3_path = OUT / "live_round3.json"
r3 = json.loads(r3_path.read_text()) if r3_path.exists() else {}
r3["generation_com_acme"] = results
r3["ok"] = bool(r3.get("ok") and results["ok"])
r3_path.write_text(json.dumps(r3, indent=2), encoding="utf-8")
print("RESULTS", json.dumps(results, indent=2))
print("OVERALL", "OK" if results["ok"] else "FAIL")
sys.exit(0 if results["ok"] else 1)
