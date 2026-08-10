import json

import httpx

from change_society.application.qwen_role_tools import RoleToolExecutor
from change_society.contracts.messages import RoleOutput
from change_society.infrastructure.qwen_client import QwenCloudClient


PAYLOAD = {
    "summary": "Evidence-backed risk analysis", "risk_level": "high", "findings": [], "impacts": [], "policies": [],
    "tasks": [], "evidence_refs": ["ev_1"], "assumptions": [], "unresolved_questions": [],
    "confidence": 0.9, "recommended_action": "approve",
}


def test_qwen_tool_loop_executes_tools_then_returns_schema_valid_json():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "model": "qwen-test",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "fetch_evidence_by_id",
                                            "arguments": json.dumps({"evidence_id": "ev_diff_price"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            )
        return httpx.Response(
            200,
            json={
                "model": "qwen-test",
                "choices": [{"message": {"role": "assistant", "content": json.dumps(PAYLOAD)}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )

    user_prompt = "EVIDENCE:\n[ev_diff_price] Diff: mutates base_price."
    client = QwenCloudClient(
        "secret",
        "https://qwen.example/v1",
        "qwen-test",
        30,
        800,
        0.1,
        0,
        httpx.Client(transport=httpx.MockTransport(handler)),
        enable_tools=True,
        tool_executor=RoleToolExecutor(),
        max_tool_rounds=2,
    )
    result = client.complete("context_scout", "Return JSON only.", user_prompt, RoleOutput)
    assert calls["n"] == 2
    assert result.output_tokens == 13
    assert result.payload["risk_level"] == "high"
    assert calls["n"] == 2


def test_mcp_gateway_local_handler():
    from change_society.infrastructure.mcp_tool_gateway import McpToolGateway

    gateway = McpToolGateway(local_handlers={"ping": lambda args: {"pong": args.get("x")}})
    assert gateway.call_tool("ping", {"x": 1})["pong"] == 1
