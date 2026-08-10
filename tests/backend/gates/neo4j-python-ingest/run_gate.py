#!/usr/bin/env python3
"""Neo4j Python ingest acceptance gate for code-graph-service."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _tcp_open(host: str, port: int) -> bool:
    import socket

    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Neo4j Python ingest acceptance gate")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Fail when Neo4j/Postgres ports are down (CI with Compose)",
    )
    args = parser.parse_args()

    bolt = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
    pg = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
    neo_up = _tcp_open("127.0.0.1", bolt)
    pg_up = _tcp_open("127.0.0.1", pg)

    checks: list[dict[str, object]] = [
        {"name": "neo4j_bolt_reachable", "status": "passed" if neo_up else "skipped", "port": bolt},
        {"name": "postgres_reachable", "status": "passed" if pg_up else "skipped", "port": pg},
    ]

    if args.require_live and (not neo_up or not pg_up):
        report = {"gate": "failed", "reason": "required live ports unavailable", "checks": checks}
        print(json.dumps(report, indent=2) if args.json else report)
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend" / "services" / "code-graph-service" / "src")
    targets = [
        "tests/backend/services/code-graph-service/test_code_graph_docker_live.py",
        "tests/backend/services/code-graph-service/test_code_graph_parity.py",
        "tests/backend/services/code-graph-service/test_code_graph_hybrid.py",
    ]
    cmd = [
        str(ROOT / ".venv" / "bin" / "python"),
        "-m",
        "pytest",
        *targets,
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    checks.append(
        {
            "name": "python_ingest_live_suite",
            "status": "passed" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-500:],
            "stderr_tail": proc.stderr[-500:],
        }
    )
    failed = [c for c in checks if c["status"] == "failed"]
    gate = "passed" if not failed else "failed"
    report = {"gate": gate, "checks": checks}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"gate={gate}")
        for item in checks:
            print(f"  {item['name']}: {item['status']}")
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
    return 0 if gate == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
