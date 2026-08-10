def test_managed_agent_template_endpoint_syncs_on_ensure():
    from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter
    from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry, WebhookAgentAdapter
    from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository
    from change_society.infrastructure.fake_model import DeterministicModelClient
    from change_society.domain.models import Scope

    class FixedClock:
        def now(self):
            return "2026-07-12T00:00:00+00:00"

    class SequenceIds:
        def __init__(self):
            self.n = 0

        def new(self, prefix: str) -> str:
            self.n += 1
            return f"{prefix}_{self.n}"

    scope = Scope("t", "w", "p")
    repo = InMemoryControlPlaneRepository()
    templates = (
        AgentTemplate("change-analyst", "Change", "ext", "webhook", ("interpret_ambiguous_software_change",), "change_analyst", "desc", "http://localhost:32510"),
    )
    plane = AgentControlPlane(
        repo,
        StaticAgentAdapterRegistry({"model": ModelAgentAdapter(DeterministicModelClient()), "webhook": WebhookAgentAdapter("secret", 5)}),
        CapabilityRouter(),
        FixedClock(),
        SequenceIds(),
        templates,
    )
    agents = plane.ensure_agents(scope)
    assert agents[0].endpoint == "http://localhost:32510"
    assert agents[0].adapter_type == "webhook"

    templates_updated = (
        AgentTemplate("change-analyst", "Change", "ext", "webhook", ("interpret_ambiguous_software_change",), "change_analyst", "desc", "http://localhost:32511"),
    )
    plane2 = AgentControlPlane(
        repo,
        StaticAgentAdapterRegistry({"model": ModelAgentAdapter(DeterministicModelClient()), "webhook": WebhookAgentAdapter("secret", 5)}),
        CapabilityRouter(),
        FixedClock(),
        SequenceIds(),
        templates_updated,
    )
    agents2 = plane2.ensure_agents(scope)
    assert agents2[0].endpoint == "http://localhost:32511"
