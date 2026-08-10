#!/usr/bin/env python3
"""Smoke three society roles against the external LangGraph worker (signed webhook)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

_SUPPORT = Path(__file__).resolve().parents[2] / "support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
from hackathon_pack import pack_root  # noqa: E402

PACK = pack_root(Path(__file__))
WORKER_SRC = PACK / "examples" / "external-change-analyst-worker" / "src"
sys.path[:0] = [
    str(WORKER_SRC),
    str(PACK / "backend" / "change-society-service" / "src"),
    str(PACK / "sdk" / "python"),
]
env = PACK / ".env"
if env.is_file():
    for line in env.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault("ASTLOOM_WEBHOOK_SHARED_SECRET", "integrator-demo-secret-change-me")
os.environ["WORKER_LIVE_MODE"] = "1"

from fastapi.testclient import TestClient
from worker.main import create_app
from worker.settings import Settings

client = TestClient(create_app(Settings.load()))
for role, title in [
    ("context_scout", "ContextOutput"),
    ("policy_guardian", "RoleOutput"),
    ("coordinator_judge", "JudgeOutput"),
]:
    body = {
        "contract_version": "1.0",
        "ticket_id": f"t_{role}",
        "agent_id": "a",
        "role": role,
        "system_prompt": f"Return {title} JSON",
        "user_prompt": "REQUEST: checkout refactor\nEVIDENCE:\n[ev_api_diff] taxIncluded",
        "output_schema": {"title": title, "type": "object"},
        "correlation_id": "c",
    }
    enc = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(os.environ["ASTLOOM_WEBHOOK_SHARED_SECRET"].encode(), enc, hashlib.sha256).hexdigest()
    r = client.post(
        "/api/v1/agent-tickets:execute",
        content=enc,
        headers={"X-Astloom-Signature": sig, "Content-Type": "application/json"},
    )
    print(role, r.status_code, r.text[:200])
