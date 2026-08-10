import assert from "node:assert/strict";
import test from "node:test";

import {buildInteractionMermaid} from "../../../archives/hackathon/frontend/lib/agent-interaction-mermaid.ts";

test("buildInteractionMermaid emits chronological flowchart edges", () => {
  const messages = [
    {
      message_id: "msg_a",
      message_type: "task_assignment",
      sender_role: "coordinator",
      recipient_role: "change_analyst",
      capability: "analyze_change",
      risk_level: "low",
      payload: {summary: "assign"},
      evidence_refs: [],
      token_usage: {},
      created_at: "2026-07-14T08:13:31.100Z",
    },
    {
      message_id: "msg_b",
      message_type: "specialist_finding",
      sender_role: "change_analyst",
      recipient_role: "coordinator",
      capability: "analyze_change",
      risk_level: "high",
      payload: {summary: "reply"},
      evidence_refs: [],
      token_usage: {},
      created_at: "2026-07-14T08:13:31.200Z",
    },
  ];

  const chart = buildInteractionMermaid(messages);
  assert.match(chart, /^flowchart TD/m);
  assert.match(chart, /m0 --> m1/);
  assert.match(chart, /Coordinator/);
  assert.match(chart, /class m1 highRisk/);
});
