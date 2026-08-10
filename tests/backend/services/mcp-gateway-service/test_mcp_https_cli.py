"""Unit tests for MCP gateway HTTPS CLI flags."""

from __future__ import annotations

from mcp_gateway_service.__main__ import main


def test_main_http_passes_ssl_paths(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_http_server(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(
        "mcp_gateway_service.http_app.run_http_server",
        fake_run_http_server,
    )
    rc = main(
        [
            "--http",
            "--host",
            "127.0.0.1",
            "--port",
            "32500",
            "--ssl-certfile",
            "/tmp/cert.pem",
            "--ssl-keyfile",
            "/tmp/key.pem",
        ]
    )
    assert rc == 0
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 32500
    assert seen["ssl_certfile"] == "/tmp/cert.pem"
    assert seen["ssl_keyfile"] == "/tmp/key.pem"


def test_run_http_server_forwards_ssl_to_uvicorn(monkeypatch):
    import uvicorn

    from mcp_gateway_service import backends, http_app

    seen: dict[str, object] = {}

    class FakeBackends:
        @staticmethod
        def from_env():
            return object()

    monkeypatch.setattr(backends, "PlatformBackends", FakeBackends)
    monkeypatch.setattr(http_app, "create_http_app", lambda **_: object())

    def fake_uvicorn_run(app, **kwargs):
        seen["app"] = app
        seen.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_uvicorn_run)
    http_app.run_http_server(
        host="0.0.0.0",
        port=32500,
        ssl_certfile="/c.pem",
        ssl_keyfile="/k.pem",
    )
    assert seen["ssl_certfile"] == "/c.pem"
    assert seen["ssl_keyfile"] == "/k.pem"
    assert seen["port"] == 32500
