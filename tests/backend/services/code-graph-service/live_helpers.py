"""Helpers for live Neo4j/Postgres gates (shared by live/fuzzer/challenge suites)."""

from __future__ import annotations

import os
import socket

import pytest

NEO4J_BOLT_PORT = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
POSTGRES_PORT = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
NEO4J_PASSWORD = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "astloom-local-dev-secret")
NEO4J_USER = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j")
POSTGRES_PASSWORD = os.environ.get("ASTLOOM_POSTGRES_PASSWORD", "astloom-local-dev-secret")


def require_tcp(host: str, port: int) -> None:
    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect((host, port))
    except OSError as exc:
        pytest.skip(f"service not reachable at {host}:{port}: {exc}")
    finally:
        sock.close()


def skip_on_live_connect_error(exc: BaseException) -> None:
    """Convert Neo4j/Postgres auth or connect failures into one clear skip.

    Without this, a module-scoped fixture AuthError becomes N setup ERRORs
    (often reported as ~50 failed/errored tests in the UI).
    """
    name = type(exc).__name__
    msg = str(exc)
    authish = (
        name in {"AuthError", "ServiceUnavailable", "OperationalError"}
        or "Unauthorized" in msg
        or "AuthenticationRateLimit" in msg
        or "authentication failure" in msg.lower()
        or "password authentication failed" in msg.lower()
    )
    if authish:
        pytest.skip(
            f"live store unavailable ({name}): set ASTLOOM_NEO4J_PASSWORD / "
            f"ASTLOOM_POSTGRES_PASSWORD to the Compose secret "
            f"(local default: astloom-local-dev-secret). detail={msg[:200]}"
        )
    raise exc
