#!/usr/bin/env python3
"""Finish round3 after hung service restart."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/opt/Astloom")
OUT = ROOT / "tests" / "artifacts" / "gap-live"
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / "backend" / "packages")]
ASTLOOM = str(ROOT / ".venv" / "bin" / "astloom")


def run(cmd: list[str], env: dict | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def ensure_mcp() -> None:
    import httpx

    try:
        if httpx.get("http://127.0.0.1:32500/health", timeout=2.0).status_code == 200:
            return
    except Exception:
        pass
    env = os.environ.copy()
    env["ASTLOOM_GUIDANCE_RESOLVE_REQUIRED"] = "0"
    # stop mcp only if needed then start
    run([ASTLOOM, "service", "start", "--json"], env=env, timeout=240)
    for _ in range(60):
        try:
            if httpx.get("http://127.0.0.1:32500/health", timeout=2.0).status_code == 200:
                return
        except Exception:
            time.sleep(1)
    raise SystemExit("MCP not healthy")


def main() -> int:
    log = (ROOT / ".astloom/run/mcp-http.log").read_text(errors="ignore")
    ok_fail = (
        "GUIDANCE_RESOLVE_REQUIRED=1" in log
        and "is required before durable writes" in log
    )
    print("fail_closed_from_log", ok_fail)

    print("ensure_mcp...")
    ensure_mcp()
    print("mcp_ok")

    env = os.environ.copy()
    env["ASTLOOM_EMBEDDING_PROVIDER"] = "stub"
    env["ASTLOOM_LITELLM_ENABLED"] = "false"
    ingest = run(
        [
            ASTLOOM,
            "graph",
            "ingest",
            "--tenant",
            "mir",
            "--workspace",
            "dev",
            "--project",
            "gap-live-cli",
            "--path",
            str(ROOT / ".astloom/gap-live-fixtures"),
            "--max-files",
            "5",
        ],
        env=env,
        timeout=300,
    )
    print("ingest_rc", ingest.returncode)
    print((ingest.stdout + ingest.stderr)[-500:])

    gen = run(
        [
            ASTLOOM,
            "graph",
            "generation-context",
            "--tenant",
            "mir",
            "--workspace",
            "dev",
            "--project",
            "gap-live-cli",
            "--qualified-name",
            "OrdersService",
            "--max-symbols",
            "4",
        ],
        env=env,
        timeout=120,
    )
    gout = gen.stdout + gen.stderr
    print("gen_rc", gen.returncode)
    print(gout[-500:])

    import httpx
    from usage_profile.mcp_tokens import mint_connect_token

    secret = Path("/opt/Astloom/.astloom/mcp-http.secret").read_text().strip()
    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = secret
    token = mint_connect_token(
        tenant_id="mir", workspace_id="dev", project_id="astloom", ttl_seconds=600
    )

    def rpc(method, params=None, rid=1):
        r = httpx.post(
            "http://127.0.0.1:32500/mcp",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}},
            timeout=60,
        )
        return r.json()

    rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "r3b", "version": "0"},
        },
    )
    w = rpc(
        "tools/call",
        {
            "name": "mcp_execute_tool",
            "arguments": {
                "server_name": "Astloom-Programming",
                "tool_name": "astloom_write",
                "arguments": {"resource": "memory", "title": "soft-ok", "body": "soft mode"},
            },
        },
        2,
    )
    wj = json.dumps(w)
    soft_ok = "written" in wj and "guidance_resolve is required" not in wj.lower()
    print("soft_write_ok", soft_ok, wj[:250])

    results = {
        "fail_closed_from_log": ok_fail,
        "cli_ingest_ok": ingest.returncode == 0,
        "generation_rc": gen.returncode,
        "generation_has_payload": bool(gout.strip()),
        "soft_write_ok": soft_ok,
        "ok": bool(ok_fail and ingest.returncode == 0 and soft_ok),
        "gen_tail": gout[-400:],
        "ingest_tail": (ingest.stdout + ingest.stderr)[-300:],
    }
    OUT.joinpath("live_round3.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("OVERALL", "OK" if results["ok"] else "FAIL")
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
