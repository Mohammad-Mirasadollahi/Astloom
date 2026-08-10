from __future__ import annotations

import json

import httpx
import pytest

from change_society.application.qwen_role_tools import RoleToolExecutor
from change_society.contracts.messages import RoleOutput
from change_society.domain.models import DependencyError
from change_society.infrastructure.qwen_client import QwenCloudClient


PAYLOAD = {
    "summary": "Brief analyst view", "risk_level": "medium", "findings": [], "impacts": [], "policies": [],
    "tasks": [], "evidence_refs": [], "assumptions": [], "unresolved_questions": [],
    "confidence": 0.5, "recommended_action": "review",
}


def test_qwen_health_exposes_role_tools_configuration():
    client = QwenCloudClient("k", "https://q.example/v1", "m", 5, 100, 0.0, 0, enable_tools=True, max_tool_rounds=3)
    health = client.health()
    assert health["role_tools_enabled"] is True
    assert health["max_tool_rounds"] == 3


def test_qwen_complete_without_tools_for_change_analyst():
    seen = {}

    def handler(request):
        body = json.loads(request.content)
        seen["has_tools"] = "tools" in body
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(PAYLOAD)}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}},
        )

    client = QwenCloudClient("k", "https://q.example/v1", "m", 5, 100, 0.0, 0, httpx.Client(transport=httpx.MockTransport(handler)))
    client.complete("change_analyst", "sys", "user", RoleOutput)
    assert seen["has_tools"] is False


def test_qwen_empty_final_content_raises_schema_invalid():
    client = QwenCloudClient(
        "k",
        "https://q.example/v1",
        "m",
        5,
        100,
        0.0,
        0,
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {}}]}))),
        enable_tools=False,
    )
    with pytest.raises(DependencyError) as exc:
        client.complete("change_analyst", "s", "u", RoleOutput)
    assert exc.value.code == "qwen_schema_invalid"


def test_qwen_tool_loop_exhausted_when_model_never_returns_json():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {"name": "fetch_evidence_by_id", "arguments": "{}"},
                                }
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client = QwenCloudClient(
        "k",
        "https://q.example/v1",
        "m",
        5,
        100,
        0.0,
        0,
        httpx.Client(transport=httpx.MockTransport(handler)),
        tool_executor=RoleToolExecutor(),
        max_tool_rounds=1,
    )
    with pytest.raises(DependencyError) as exc:
        client.complete("context_scout", "s", "EVIDENCE:\n[ev_a] T: c", RoleOutput)
    assert exc.value.code == "qwen_tool_loop_exhausted"
