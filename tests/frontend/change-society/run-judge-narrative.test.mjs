import assert from "node:assert/strict";
import test from "node:test";

import {buildJudgeRunBrief, explainRunState, explainTicket} from "../../../archives/hackathon/frontend/lib/run-judge-narrative.ts";

test("explainRunState speaks in plain language for judges", () => {
  const approval = explainRunState("awaiting_approval");
  assert.match(approval.body, /human/i);
  assert.match(approval.judgeTip, /Review/i);
});

test("explainTicket maps coordinator capability", () => {
  const brief = explainTicket({
    title: "Coordinator reconciliation",
    capability: "decompose_route_reconcile",
    state: "completed",
  });
  assert.equal(brief.roleLabel, "Coordinator");
  assert.match(brief.whyItMatters, /control plane/i);
});

test("buildJudgeRunBrief includes value bullets", () => {
  const brief = buildJudgeRunBrief(
    {
      run_id: "run_x",
      state: "completed",
      scenario_id: "pricing-refactor",
      request_text: "Refactor tax logic",
      version: 1,
      message_count: 3,
      conflict_count: 1,
      approval: null,
      final_result: null,
      metrics: {},
      excluded_evidence: [],
      correlation_id: "c",
    },
    {messages: 3, tickets: 5, conflicts: 1, openConflicts: 0},
  );
  assert.ok(brief.valueBullets.length >= 3);
  assert.match(brief.paragraphs.join(" "), /governed multi-agent/i);
});
