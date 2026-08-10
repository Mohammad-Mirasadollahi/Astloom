"""MCP gateway entrypoints: stdio (default) or HTTP/HTTPS."""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mcp_gateway_service")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve Streamable HTTP / JSON-RPC MCP (Phase B)",
    )
    parser.add_argument("--host", default=os.environ.get("ASTLOOM_MCP_HTTP_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ASTLOOM_MCP_HTTP_PORT", "32500")),
    )
    parser.add_argument(
        "--ssl-certfile",
        default=os.environ.get("ASTLOOM_MCP_TLS_CERTFILE", ""),
        help="TLS certificate PEM (HTTPS). Env: ASTLOOM_MCP_TLS_CERTFILE",
    )
    parser.add_argument(
        "--ssl-keyfile",
        default=os.environ.get("ASTLOOM_MCP_TLS_KEYFILE", ""),
        help="TLS private key PEM (HTTPS). Env: ASTLOOM_MCP_TLS_KEYFILE",
    )
    args, _unknown = parser.parse_known_args(argv)
    if args.http:
        from .http_app import run_http_server

        run_http_server(
            host=str(args.host),
            port=int(args.port),
            ssl_certfile=str(args.ssl_certfile or "").strip() or None,
            ssl_keyfile=str(args.ssl_keyfile or "").strip() or None,
        )
        return 0
    from .server import main as stdio_main

    return stdio_main()


if __name__ == "__main__":
    raise SystemExit(main())
