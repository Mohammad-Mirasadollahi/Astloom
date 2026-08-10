"""Round 3: MCP fail-closed + generation-context read_model + CLI ingest few files."""
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

results = {"ok": True, "checks": []}


def check(name: str, cond: bool, detail=None) -> None:
    results["checks"].append({"name": name, "ok": bool(cond), "detail": detail})
    if not cond:
        results["ok"] = False
    print(("PASS" if cond else "FAIL"), name, "" if detail is None else detail)


def mcp_rpc(token: str, method: str, params: dict | None = None, rid: int = 1) -> dict:
    import httpx

    r = httpx.post(
        "http://127.0.0.1:32500/mcp",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}},
        timeout=90.0,
    )
    r.raise_for_status()
    return r.json()


def mint() -> str:
    from usage_profile.mcp_tokens import mint_connect_token

    secret = Path("/opt/Astloom/.astloom/mcp-http.secret").read_text().strip()
    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = secret
    return mint_connect_token(
        tenant_id="mir", workspace_id="dev", project_id="astloom", ttl_seconds=3600
    )


def restart_mcp(*, guidance_required: bool) -> None:
    env = os.environ.copy()
    if guidance_required:
        env["ASTLOOM_GUIDANCE_RESOLVE_REQUIRED"] = "1"
    else:
        env.pop("ASTLOOM_GUIDANCE_RESOLVE_REQUIRED", None)
        env["ASTLOOM_GUIDANCE_RESOLVE_REQUIRED"] = "0"
    # Ensure packages on path for child
    env.setdefault(
        "PYTHONPATH",
        f"{ROOT}/backend/packages:{ROOT}/backend/services/mcp-gateway-service/src",
    )
    cmd = [str(ROOT / ".venv/bin/astloom"), "service", "restart", "--json"]
    subprocess.run(cmd, cwd=str(ROOT), env=env, check=False, capture_output=True, text=True)
    # wait health
    import httpx

    for _ in range(40):
        try:
            h = httpx.get("http://127.0.0.1:32500/health", timeout=2.0)
            if h.status_code == 200:
                return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("MCP health not ready after restart")


def main() -> int:
    print("=== restart MCP fail-closed ===")
    restart_mcp(guidance_required=True)
    token = mint()
    mcp_rpc(
        token,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "gap-r3", "version": "0"},
        },
        1,
    )
    write = mcp_rpc(
        token,
        "tools/call",
        {
            "name": "mcp_execute_tool",
            "arguments": {
                "server_name": "Astloom-Programming",
                "tool_name": "astloom_write",
                "arguments": {
                    "resource": "memory",
                    "title": "should-fail",
                    "body": "no guidance yet",
                },
            },
        },
        2,
    )
    blob = json.dumps(write).lower()
    check(
        "fail_closed_blocks_write",
        write.get("result", {}).get("isError") is True
        or "guidance_resolve" in blob
        or "required" in blob
        or "error" in write,
        str(write)[:400],
    )

    g = mcp_rpc(
        token,
        "tools/call",
        {
            "name": "mcp_execute_tool",
            "arguments": {
                "server_name": "Astloom-Programming",
                "tool_name": "astloom_guidance_resolve",
                "arguments": {"task_summary": "round3"},
            },
        },
        3,
    )
    check("guidance_then_ok_resolve", "result" in g and not g.get("result", {}).get("isError"), str(g)[:200])
    write2 = mcp_rpc(
        token,
        "tools/call",
        {
            "name": "mcp_execute_tool",
            "arguments": {
                "server_name": "Astloom-Programming",
                "tool_name": "astloom_write",
                "arguments": {
                    "resource": "memory",
                    "title": "after-guidance",
                    "body": "should work",
                },
            },
        },
        4,
    )
    w2 = json.dumps(write2)
    check(
        "write_after_guidance",
        '"written": "memory"' in w2 or '"written":"memory"' in w2,
        w2[:300],
    )

    print("=== restore soft MCP ===")
    restart_mcp(guidance_required=False)

    print("=== CLI ingest few fixtures ===")
    env = os.environ.copy()
    env["ASTLOOM_EMBEDDING_PROVIDER"] = "stub"
    env["ASTLOOM_LITELLM_ENABLED"] = "false"
    ingest = subprocess.run(
        [
            str(ROOT / ".venv/bin/astloom"),
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
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    check("cli_ingest_exit", ingest.returncode == 0, (ingest.stdout + ingest.stderr)[-500:])

    # generation-context if we can find a symbol via explore
    gen = subprocess.run(
        [
            str(ROOT / ".venv/bin/astloom"),
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
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    gout = gen.stdout + gen.stderr
    check(
        "generation_context_read_model",
        gen.returncode == 0 and ("read_model_id" in gout or "generation_context" in gout or "symbols" in gout.lower()),
        gout[-600:],
    )

    OUT.joinpath("live_round3.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("OVERALL", "OK" if results["ok"] else "FAIL")
    for c in results["checks"]:
        if not c["ok"]:
            print(" -", c["name"], c["detail"])
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
