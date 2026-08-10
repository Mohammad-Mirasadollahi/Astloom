from __future__ import annotations

import pytest

from change_society.application.run_token_budget import BudgetEnforcingModelClient
from change_society.contracts.messages import RoleOutput
from change_society.domain.models import DependencyError
from change_society.infrastructure.fake_model import DeterministicModelClient


def test_run_token_budget_resets_per_society_run():
    inner = DeterministicModelClient()
    client = BudgetEnforcingModelClient(inner, 500)
    client.complete("policy_guardian", "s", "u", RoleOutput)
    assert client.tokens_used > 0
    client.reset_budget()
    assert client.tokens_used == 0


def test_run_token_budget_raises_when_exceeded():
    client = BudgetEnforcingModelClient(DeterministicModelClient(), 50)
    with pytest.raises(DependencyError) as exc:
        for _ in range(6):
            client.complete("policy_guardian", "s", "u", RoleOutput)
    assert exc.value.code == "qwen_budget_exceeded"
