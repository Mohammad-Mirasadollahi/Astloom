import assert from "node:assert/strict";
import test from "node:test";

import {buildAgentExchangeStory, plainExchangeLine} from "../../../archives/hackathon/frontend/lib/agent-exchange-story.ts";

const baseRun = {
  run_id: "run_test",
  state: "completed",
  version: 1,
  request_text: "Refactor checkout tax calculation",
  scenario_id: "pricing-refactor",
  message_count: 2,
  conflict_count: 1,
  approval: null,
  final_result: null,
  metrics: {},
  excluded_evidence: [],
  correlation_id: "corr_test",
};

test("plainExchangeLine explains specialist findings in judge language", () => {
  const line = plainExchangeLine(
    {
      message_id: "m1",
      message_type: "specialist_finding",
      sender_role: "change_analyst",
      recipient_role: "coordinator",
      capability: "interpret_ambiguous_software_change",
      risk_level: "high",
      payload: {
        summary: "Base price may change before tax",
        findings: ["Revenue impact on checkout"],
        impacts: ["billing tests"],
      },
      evidence_refs: ["ev1"],
      token_usage: {},
    },
    3,
  );
  assert.match(line.headline, /Change Analyst/i);
  assert.match(line.headline, /High risk/i);
  assert.match(line.detail, /Revenue impact/);
});

test("buildAgentExchangeStory includes scenario hook and conflict plain text", () => {
  const story = buildAgentExchangeStory(
    baseRun,
    [
      {
        message_id: "a",
        message_type: "specialist_finding",
        sender_role: "policy_guardian",
        recipient_role: "coordinator",
        capability: "evaluate_policy_and_approval_risk",
        risk_level: "high",
        payload: {summary: "Needs finance approval"},
        evidence_refs: [],
        token_usage: {},
        created_at: "2026-07-14T08:00:00Z",
      },
      {
        message_id: "b",
        message_type: "coordinator_decision",
        sender_role: "coordinator",
        recipient_role: "coordinator",
        capability: "decompose_route_reconcile",
        risk_level: "medium",
        payload: {verdict: "guarded_plan", summary: "Ship with approvals"},
        evidence_refs: [],
        token_usage: {},
        created_at: "2026-07-14T08:00:01Z",
      },
    ],
    [
      {
        conflict_id: "c1",
        topic: "risk",
        claim_a_risk: "high",
        claim_b_risk: "low",
        status: "resolved",
        rationale: "Policy tags require human gate",
        rebuttal_message_ids: [],
      },
    ],
    {
      scenario_id: "pricing-refactor",
      title: "Pricing refactor",
      default_request: "Refactor tax",
      evidence_count: 4,
      domain: "revenue_and_billing",
      governance_rules: ["revenue-impacting-change"],
      feature_demonstrations: [],
      expected_impacts: ["customer price"],
      required_policies: [],
      required_tasks: [],
      requires_negotiation: true,
    },
  );

  assert.equal(story.problem.title, "Pricing refactor");
  assert.match(story.problem.hook, /tax refactor/i);
  assert.ok(story.conflictPlain?.includes("high") || story.conflictPlain?.includes("High"));
  assert.ok(story.outcomePlain?.includes("extra approvals") || story.outcomePlain?.includes("Ship"));
  assert.ok(story.lines.length >= 2);
});
