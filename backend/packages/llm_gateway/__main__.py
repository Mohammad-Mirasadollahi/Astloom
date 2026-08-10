"""CLI: python -m llm_gateway [providers|config|complete]."""

from __future__ import annotations

import argparse
import json

from .gateway import LiteLlmGateway
from .settings import LlmGatewaySettings
from .types import ChatMessage, CompletionRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Astloom LiteLLM gateway helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("providers", help="List LiteLLM providers (env-aware configured flags)")
    sub.add_parser("config", help="Show public LiteLLM settings (no secrets)")

    complete = sub.add_parser("complete", help="Run a one-shot chat completion via LiteLLM")
    complete.add_argument("--prompt", required=True, help="User prompt text")
    complete.add_argument("--model", default=None, help="Override ASTLOOM_LITELLM_DEFAULT_MODEL")
    complete.add_argument("--system", default="You are a helpful assistant.", help="System message")
    complete.add_argument(
        "--reasoning",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override ASTLOOM_LITELLM_REASONING_ENABLED for this call",
    )
    complete.add_argument(
        "--reasoning-effort",
        default=None,
        help="Optional effort (e.g. low|medium|high); overrides ASTLOOM_LITELLM_REASONING_EFFORT",
    )

    args = parser.parse_args(argv)
    settings = LlmGatewaySettings.from_environment()
    gateway = LiteLlmGateway(settings)

    if args.command == "providers":
        payload = {
            "providers": [p.to_dict() for p in gateway.list_providers()],
            "configured_count": sum(1 for p in gateway.list_providers() if p.configured),
        }
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "config":
        print(json.dumps(gateway.settings_public(), indent=2))
        return 0

    if args.command == "complete":
        result = gateway.complete(
            CompletionRequest(
                messages=(
                    ChatMessage(role="system", content=args.system),
                    ChatMessage(role="user", content=args.prompt),
                ),
                model=args.model,
                reasoning_enabled=args.reasoning,
                reasoning_effort=args.reasoning_effort,
            )
        )
        print(json.dumps({"content": result.content, "model": result.model, "provider": result.provider, "usage": result.usage}, indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
