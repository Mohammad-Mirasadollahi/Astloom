"""LLM gateway CLI commands (sessions + connectivity test)."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.request import Request, urlopen

from astloom_cli.cli_defaults import load_dotenv_files
from astloom_cli.sync_progress import read_live_progress
from astloom_cli.util import print_json


def _fetch_sessions() -> tuple[str, dict[str, Any]]:
    load_dotenv_files()
    base = os.environ.get("ASTLOOM_CODE_GRAPH_URL", "").strip().rstrip("/")
    if not base:
        port = int(os.environ.get("ASTLOOM_CODE_GRAPH_PORT", "32140"))
        base = f"http://127.0.0.1:{port}"
    url = f"{base}/api/v1/llm/sessions"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=3.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"code-graph session endpoint unavailable at {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid session snapshot from {url}")
    return url, payload


def cmd_llm_sessions(_: argparse.Namespace) -> int:
    live = read_live_progress()
    if isinstance(live, dict) and isinstance(live.get("llm_sessions"), dict):
        snap = dict(live["llm_sessions"])
        if snap:
            print_json(
                {
                    "ok": True,
                    "source": f"sync-process:{int(live.get('pid') or 0)}",
                    "sessions": snap,
                }
            )
            return 0
    try:
        source, snap = _fetch_sessions()
    except RuntimeError as exc:
        print_json({"ok": False, "error": str(exc)})
        return 1
    print_json({"ok": True, "source": source, "sessions": snap})
    return 0


def cmd_llm_test(args: argparse.Namespace) -> int:
    """One-shot completion against the configured LiteLLM model (default prompt: Hi)."""
    load_dotenv_files()
    from llm_gateway import ChatMessage, CompletionRequest, LiteLlmGateway, LlmGatewaySettings

    settings = LlmGatewaySettings.from_environment()
    configured = (getattr(args, "model", None) or settings.default_model or "").strip()
    prompt = (getattr(args, "prompt", None) or "Hi").strip() or "Hi"
    public = settings.public_dict()
    base_payload = {
        "configured_model": configured,
        "api_base": public.get("api_base"),
        "enabled": public.get("enabled"),
        "api_key_configured": public.get("api_key_configured"),
        "prompt": prompt,
    }
    if not settings.enabled:
        print_json({**base_payload, "ok": False, "error": "LiteLLM disabled (ASTLOOM_LITELLM_ENABLED=false)"})
        return 1
    if not configured:
        print_json(
            {
                **base_payload,
                "ok": False,
                "error": "No model set: ASTLOOM_LITELLM_DEFAULT_MODEL or --model",
            }
        )
        return 1

    gateway = LiteLlmGateway(settings)
    try:
        result = gateway.complete(
            CompletionRequest(
                messages=(
                    ChatMessage(role="system", content="Reply briefly."),
                    ChatMessage(role="user", content=prompt),
                ),
                model=configured,
                max_tokens=64,
            )
        )
    except Exception as exc:
        print_json({**base_payload, "ok": False, "error": str(exc)})
        return 1

    print_json(
        {
            **base_payload,
            "ok": True,
            "model": result.model,
            "provider": result.provider,
            "reply": (result.content or "").strip(),
            "usage": result.usage,
        }
    )
    return 0
