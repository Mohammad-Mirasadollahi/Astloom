def test_integrator_live_all_registry_webhook_only():
    from integrator_worker_support import ROOT, load_integrator_registry
    import json

    path = ROOT / "archives/hackathon/backend/change-society-service/config/managed-agents.integrator-live-all.example.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["agents"]) == 6
    for agent in data["agents"]:
        assert agent["adapter_type"] == "webhook"
        assert agent["endpoint"] == "http://localhost:32510"
        assert agent["provider"] == "langgraph-sdk-society-worker"
