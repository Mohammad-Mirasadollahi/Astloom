import assert from "node:assert/strict";
import test from "node:test";

import {
  buildInteractionGraph,
  columnCenterX,
  stepRowY,
} from "../../../archives/hackathon/frontend/lib/agent-interaction-graph.ts";

test("orders steps by created_at and assigns role columns", () => {
  const messages = [
    {
      message_id: "msg_b",
      message_type: "specialist_finding",
      sender_role: "change_analyst",
      recipient_role: "coordinator",
      capability: "analyze_change",
      risk_level: "medium",
      payload: {summary: "second"},
      evidence_refs: [],
      token_usage: {},
      created_at: "2026-07-14T08:13:31.200Z",
    },
    {
      message_id: "msg_a",
      message_type: "task_assignment",
      sender_role: "coordinator",
      recipient_role: "change_analyst",
      capability: "analyze_change",
      risk_level: "low",
      payload: {},
      evidence_refs: [],
      token_usage: {},
      created_at: "2026-07-14T08:13:31.100Z",
    },
  ];

  const layout = buildInteractionGraph(messages);
  assert.equal(layout.steps.length, 2);
  assert.equal(layout.steps[0].messageId, "msg_a");
  assert.equal(layout.steps[1].messageId, "msg_b");
  assert.equal(layout.roles[0].role, "coordinator");
  assert.ok(layout.width > layout.height / 4);
  assert.ok(columnCenterX(layout, 0) < columnCenterX(layout, 1));
  assert.ok(stepRowY(layout, 1) > stepRowY(layout, 0));
});
