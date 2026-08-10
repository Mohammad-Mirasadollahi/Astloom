"""GAP-A06: MCP guidance resolve fail-closed writes."""

from __future__ import annotations

import pytest

from mcp_gateway_service.backends import writes


class _Backends:
    def guidance_was_resolved(self, scope):
        return False


def test_write_fail_closed_when_guidance_required(monkeypatch):
    monkeypatch.setenv("ASTLOOM_GUIDANCE_RESOLVE_REQUIRED", "1")
    with pytest.raises(ValueError, match="guidance_resolve is required"):
        writes.write_resource(
            _Backends(),
            {"resource": "memory", "title": "t", "body": "b"},
            scope={"project_id": "p"},
            correlation_id="c1",
            base={"ok": True},
        )


def test_write_soft_mode_when_guidance_not_required(monkeypatch):
    monkeypatch.delenv("ASTLOOM_GUIDANCE_RESOLVE_REQUIRED", raising=False)

    class _Mem:
        def public(self):
            return {"id": "m1", "title": "t", "body": "b"}

    class _SoftBackends(_Backends):
        actor_id = "actor-1"

        def memory_scope(self, scope):
            return scope

        class memory:
            @staticmethod
            def create_memory(*_a, **_k):
                return _Mem()

    result = writes.write_resource(
        _SoftBackends(),
        {"resource": "memory", "title": "t", "body": "b"},
        scope={"project_id": "p"},
        correlation_id="c-soft",
        base={"ok": True},
    )
    assert result["written"] == "memory"
    assert "guidance_hint" in result
    assert "guidance_resolve" in result["guidance_hint"].lower()
