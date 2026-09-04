"""Tests for HTTP MCP fragment materialization."""

import pytest

from astloom_cli.mcp_client_targets import materialize_http_mcp_fragment


def test_materialize_http_mcp_fragment_insecure_lab_default():
    frag = materialize_http_mcp_fragment(
        url="https://astloom.example.internal:32500/mcp",
        headers={"Authorization": "Bearer t", "X-Tenant-Id": "a"},
        tls_verify=False,
    )
    server = frag["mcpServers"]["Astloom-Programming"]
    assert server["command"] == "npx"
    assert "mcp-remote" in server["args"]
    assert server["env"]["NODE_TLS_REJECT_UNAUTHORIZED"] == "0"
    assert "NODE_EXTRA_CA_CERTS" not in server["env"]


def test_materialize_http_mcp_fragment_verify_needs_ca():
    with pytest.raises(SystemExit, match="tls_verify is true but no CA"):
        materialize_http_mcp_fragment(
            url="https://astloom.example.internal:32500/mcp",
            headers={"Authorization": "Bearer t"},
            tls_verify=True,
        )
