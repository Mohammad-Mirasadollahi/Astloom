import assert from "node:assert/strict";
import test from "node:test";

import {buildHomeReportSnapshot, sumMessageTokens} from "../../../archives/hackathon/frontend/lib/home-reporting.ts";

test("sumMessageTokens adds numeric token_usage fields", () => {
  const total = sumMessageTokens([
    {token_usage: {input: 10, output: 5}} as never,
    {token_usage: {input: 3}} as never,
  ]);
  assert.equal(total, 18);
});

test("buildHomeReportSnapshot aggregates scenario domains without a run", () => {
  const snapshot = buildHomeReportSnapshot({
    scenarios: [
      {domain: "commerce"} as never,
      {domain: "commerce"} as never,
      {domain: "privacy"} as never,
    ],
    run: null,
    messages: [],
    tickets: [],
    agents: [],
    conflicts: [],
    viewState: "ready",
  });
  assert.equal(snapshot.summary.scenarios, 3);
  assert.deepEqual(snapshot.scenarioDomainBars, [
    {label: "commerce", value: 2},
    {label: "privacy", value: 1},
  ]);
  assert.equal(snapshot.qualityBars.every(row => row.value === 0), true);
});

test("buildHomeReportSnapshot builds quality and ticket slices for active runs", () => {
  const snapshot = buildHomeReportSnapshot({
    scenarios: [],
    run: {
      metrics: {critical_impact_recall: 0.8, policy_match_recall: 0.5, total_tokens: 900},
    } as never,
    messages: [
      {message_type: "specialist_finding", risk_level: "medium", token_usage: {input: 4}} as never,
      {message_type: "specialist_finding", risk_level: "high", token_usage: {output: 6}} as never,
    ],
    tickets: [{state: "completed"} as never, {state: "in_progress"} as never],
    agents: [{name: "Analyst", active_ticket_count: 2} as never],
    conflicts: [{status: "resolved"} as never, {status: "open"} as never],
    viewState: "active",
  });
  assert.equal(snapshot.summary.totalTokens, 900);
  assert.equal(snapshot.summary.openConflicts, 1);
  assert.equal(snapshot.qualityBars[0].value, 80);
  assert.equal(snapshot.qualityBars[1].value, 50);
  assert.equal(snapshot.qualityBars[2].value, 50);
  assert.equal(snapshot.ticketStateBars.length, 2);
  assert.equal(snapshot.agentLoadBars[0].label, "Analyst");
});
