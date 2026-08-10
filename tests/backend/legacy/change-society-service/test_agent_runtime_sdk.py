import hashlib
import hmac
import json

from astloom_agent_sdk import (
    LangChainMessageTranslator, LangGraphMessageTranslator, RunnableAgentBridge,
    SignedWebhookWorker, TranslatorRegistry, UniversalAgentMessage,
)


def task_message():
    return UniversalAgentMessage(
        "1.0", "msg_1", "task_assignment", "tenant", "workspace", "project", "run_1", "corr_1",
        "coordinator", "researcher", "research", "ticket_1", "investigate", "assigned",
        {"content": "Find evidence"}, ("ev_1",), confidence=1.0, risk_level="low",
        requested_next_action="complete_ticket", idempotency_key="idem_1",
    )


def test_translator_registry_round_trips_langchain_and_langgraph_state():
    registry = TranslatorRegistry((LangChainMessageTranslator(), LangGraphMessageTranslator()))
    rendered = registry.render("langgraph", task_message())
    assert rendered["astloom"]["ticket_id"] == "ticket_1"
    normalized = registry.normalize("langchain", {"messages": [{"role": "ai", "content": "Evidence found"}]}, {
        "message_id": "msg_2", "message_type": "specialist_finding", "tenant_id": "tenant",
        "workspace_id": "workspace", "project_id": "project", "run_id": "run_1", "correlation_id": "corr_1",
        "sender_role": "researcher", "recipient_role": "coordinator", "capability": "research",
        "task_ref": "ticket_1", "intent": "report", "status": "completed", "risk_level": "low",
    })
    assert normalized.payload["content"] == "Evidence found"


def test_runnable_bridge_manages_compiled_graph_without_framework_dependency():
    class Graph:
        def invoke(self, value):
            assert value["astloom"]["ticket_id"] == "ticket_1"
            return {"output": "done", "messages": []}

    result = RunnableAgentBridge(Graph()).execute(task_message())
    assert result["output"] == "done"


def test_signed_webhook_worker_verifies_control_plane_request():
    body = json.dumps({
        "contract_version": "1.0", "ticket_id": "ticket_1", "agent_id": "agent_1", "role": "researcher",
        "system_prompt": "Return JSON", "user_prompt": "Analyze", "output_schema": {"type": "object"},
        "correlation_id": "corr_1",
    }, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    response = SignedWebhookWorker("secret", lambda task: {"summary": task.user_prompt}).handle(body, signature)
    assert response["output"] == {"summary": "Analyze"}
    assert response["execution_id"] == "external:ticket_1"
