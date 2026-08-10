import assert from "node:assert/strict";
import test from "node:test";

import {beatById, beatFromSignals, CINEMATIC_BEATS} from "../../../archives/hackathon/frontend/lib/cinematic-beats.ts";

test("cinematic story has eight beats including frontend handoff", () => {
  assert.equal(CINEMATIC_BEATS.length, 8);
  assert.equal(CINEMATIC_BEATS[0].id, "intro");
  assert.equal(CINEMATIC_BEATS.at(-1)?.id, "outcome");
  assert.ok(CINEMATIC_BEATS.some(item => item.id === "frontend-handoff"));
});

test("beatFromSignals follows society run progression", () => {
  assert.equal(beatFromSignals({hasRun: false, ticketCount: 0, messageCount: 0, conflictCount: 0, awaitingApproval: false, completed: false}), "intro");
  assert.equal(beatFromSignals({hasRun: true, ticketCount: 2, messageCount: 0, conflictCount: 0, awaitingApproval: false, completed: false}), "routing");
  assert.equal(beatFromSignals({hasRun: true, ticketCount: 2, messageCount: 3, conflictCount: 1, awaitingApproval: false, completed: false}), "conflict");
  assert.equal(beatFromSignals({hasRun: true, ticketCount: 7, messageCount: 10, conflictCount: 1, awaitingApproval: true, completed: false}), "approval");
  assert.equal(beatFromSignals({hasRun: true, ticketCount: 7, messageCount: 12, conflictCount: 1, awaitingApproval: false, completed: true, hasFrontendHandoff: true}), "outcome");
});

test("beatById returns intro for unknown ids", () => {
  assert.equal(beatById("approval").id, "approval");
  assert.equal(beatById("not-a-beat").id, "intro");
});
