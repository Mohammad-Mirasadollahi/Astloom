"""HTTP (JSON-RPC) MCP gateway for concurrent coding-agent clients."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .server import McpGateway, McpGatewayError, handle_message
from .token_auth import extract_bearer, verify_connect_token


def _mcp_tool_timeout_seconds() -> float:
    raw = str(os.environ.get("ASTLOOM_MCP_TOOL_TIMEOUT_SECONDS", "25")).strip()
    try:
        value = float(raw)
    except ValueError:
        value = 25.0
    if value <= 0:
        return 25.0
    return min(value, 300.0)


async def _handle_message_bounded(gateway: Any, message: dict[str, Any]) -> dict[str, Any] | None:
    timeout = _mcp_tool_timeout_seconds()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(handle_message, gateway, message),
            timeout=timeout,
        )
    except TimeoutError:
        tool_hint = ""
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        nested = args.get("arguments") if isinstance(args.get("arguments"), dict) else {}
        for candidate in (
            args.get("tool_name"),
            args.get("tool"),
            params.get("name"),
            nested.get("tool_name") if nested else None,
        ):
            text = str(candidate or "").strip()
            if text and text not in {"mcp_execute_tool", "mcp_search_tools"}:
                tool_hint = f" ({text})"
                break
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32001,
                "message": (
                    f"tool timed out after {int(timeout)}s{tool_hint}; "
                    "retry with a smaller budget or check Neo4j/embeddings/filesystem"
                ),
            },
        }


def create_http_app(*, backends: Any | None = None) -> FastAPI:
    """Build FastAPI app. Optional shared *backends* for multi-request reuse."""
    api = FastAPI(title="Astloom MCP HTTP Gateway", version="1.0.0")
    shared_backends = backends

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mcp-gateway-http", "transport": "streamable_http"}

    @api.post("/mcp")
    async def mcp_jsonrpc(
        request: Request,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        x_workspace_id: str | None = Header(default=None),
        x_project_id: str | None = Header(default=None),
        x_usage_profile: str | None = Header(default=None),
    ) -> JSONResponse:
        token = extract_bearer(authorization)
        if not token:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "unauthorized"}},
                status_code=401,
            )
        try:
            scope = verify_connect_token(
                token,
                tenant_id=x_tenant_id,
                workspace_id=x_workspace_id,
                project_id=x_project_id,
            )
        except ValueError as exc:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": str(exc)}},
                status_code=401,
            )

        profile = (x_usage_profile or os.environ.get("ASTLOOM_USAGE_PROFILE") or "programming-cursor-mcp").strip()
        try:
            gateway = McpGateway(
                profile_id=profile,
                tenant_id=scope["tenant_id"],
                workspace_id=scope["workspace_id"],
                project_id=scope["project_id"],
                backends=shared_backends,
            )
        except McpGatewayError as exc:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": exc.code, "message": exc.message}},
                status_code=400,
            )
        except Exception as exc:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32000, "message": f"gateway start failed: {exc}"},
                },
                status_code=500,
            )

        try:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "parse error"},
                    },
                    status_code=400,
                )

            if isinstance(body, list):
                responses = []
                for message in body:
                    if not isinstance(message, dict):
                        continue
                    resp = await _handle_message_bounded(gateway, message)
                    if resp is not None:
                        responses.append(resp)
                return JSONResponse(responses)

            if not isinstance(body, dict):
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "invalid request"},
                    },
                    status_code=400,
                )
            response = await _handle_message_bounded(gateway, body)
            if response is None:
                return JSONResponse({})
            return JSONResponse(response)
        finally:
            gateway.close()

    return api


def run_http_server(
    *,
    host: str = "0.0.0.0",
    port: int = 32500,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
) -> None:
    import uvicorn

    from .backends import PlatformBackends

    backends = PlatformBackends.from_env()
    app = create_http_app(backends=backends)
    kwargs: dict = {"host": host, "port": port, "log_level": "info"}
    cert = (ssl_certfile or "").strip()
    key = (ssl_keyfile or "").strip()
    if cert and key:
        kwargs["ssl_certfile"] = cert
        kwargs["ssl_keyfile"] = key
    uvicorn.run(app, **kwargs)
