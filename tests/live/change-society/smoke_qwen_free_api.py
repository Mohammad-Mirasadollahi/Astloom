#!/usr/bin/env python3
"""Operational smoke test for Qwen Cloud free-tier compatible-mode API.

Verifies:
  1) Raw chat/completions reachability (minimal tokens).
  2) Same path Change Society uses: structured RoleOutput via QwenCloudClient.

Loads `.env` in the pack root when present (do not commit keys). Writes redacted evidence JSON.

Usage:
  bash tests/live/change-society/smoke-qwen-free-api.sh
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

_SUPPORT = Path(__file__).resolve().parents[2] / "support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
from hackathon_pack import init_script  # noqa: E402

PACK = init_script(__file__)

from change_society.contracts.messages import RoleOutput  # noqa: E402
from change_society.infrastructure.qwen_client import QwenCloudClient  # noqa: E402

DEFAULT_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-flash"
EVIDENCE_PATH = PACK / "evidence" / "live" / "qwen-free-api-smoke.json"


def load_pack_env() -> None:
    env_file = PACK / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def require_config() -> tuple[str, str, str]:
    load_pack_env()
    api_key = os.getenv("QWEN_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("QWEN_API_KEY is missing. Set it in .env or the environment.")
    base_url = os.getenv("QWEN_BASE_URL", DEFAULT_BASE).strip()
    model = os.getenv("QWEN_FREE_API_MODEL", os.getenv("QWEN_MODEL", DEFAULT_MODEL)).strip()
    return api_key, base_url, model


def smoke_raw_chat(api_key: str, base_url: str, model: str) -> dict:
    started = time.perf_counter()
    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
            "max_tokens": 16,
            "temperature": 0,
        },
        timeout=float(os.getenv("QWEN_TIMEOUT_SECONDS", "60")),
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        raise RuntimeError(f"free API chat failed HTTP {response.status_code}: {response.text[:500]}")
    data = response.json()
    usage = data.get("usage") or {}
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {
        "ok": True,
        "duration_ms": duration_ms,
        "model": model,
        "input_tokens": int(usage.get("prompt_tokens", 0)),
        "output_tokens": int(usage.get("completion_tokens", 0)),
        "reply_excerpt": str(content)[:80],
    }


def smoke_society_structured(api_key: str, base_url: str, model: str) -> dict:
    client = QwenCloudClient(
        api_key,
        base_url,
        model,
        float(os.getenv("QWEN_TIMEOUT_SECONDS", "60")),
        int(os.getenv("QWEN_FREE_API_MAX_TOKENS", "512")),
        float(os.getenv("QWEN_TEMPERATURE", "0.1")),
        int(os.getenv("QWEN_MAX_RETRIES", "2")),
        enable_tools=False,
        max_tool_rounds=0,
    )
    try:
        started = time.perf_counter()
        result = client.complete(
            "policy_guardian",
            "You are Policy Guardian. Return JSON only matching RoleOutput schema.",
            "Synthetic check: checkout API removes taxIncluded field. One sentence summary.",
            RoleOutput,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "duration_ms": duration_ms,
            "risk_level": result.payload.get("risk_level"),
            "summary_excerpt": str(result.payload.get("summary", ""))[:120],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "model": result.model,
        }
    finally:
        client.close()


def main() -> int:
    api_key, base_url, model = require_config()
    host = urlparse(base_url).netloc or base_url

    report = {
        "test": "qwen_free_api_smoke",
        "status": "passed",
        "executed_at": datetime.now(UTC).isoformat(),
        "api_host": host,
        "model": model,
        "compatible_mode_base": base_url.rstrip("/"),
        "secrets_included": False,
        "steps": {},
    }

    try:
        report["steps"]["raw_chat_completion"] = smoke_raw_chat(api_key, base_url, model)
        report["steps"]["society_role_output"] = smoke_society_structured(api_key, base_url, model)
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)[:500]
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "failed", "evidence": str(EVIDENCE_PATH), "error": report["error"]}, indent=2))
        return 1

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "evidence": str(EVIDENCE_PATH.relative_to(PACK)),
                "model": model,
                "host": host,
                "tokens": {
                    "raw": report["steps"]["raw_chat_completion"]["input_tokens"]
                    + report["steps"]["raw_chat_completion"]["output_tokens"],
                    "structured": report["steps"]["society_role_output"]["input_tokens"]
                    + report["steps"]["society_role_output"]["output_tokens"],
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
