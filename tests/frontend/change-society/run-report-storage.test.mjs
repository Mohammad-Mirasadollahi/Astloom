import assert from "node:assert/strict";
import test from "node:test";

import {shouldPersistSocietyRunReport} from "../../../archives/hackathon/frontend/lib/run-report-storage.ts";
import {shouldPollSocietyRun} from "../../../archives/hackathon/frontend/lib/demo-state.ts";

test("shouldPollSocietyRun covers active coordinator phases", () => {
  assert.equal(shouldPollSocietyRun("analyzing"), true);
  assert.equal(shouldPollSocietyRun("completed"), false);
});

test("shouldPersistSocietyRunReport saves terminal milestones", () => {
  assert.equal(shouldPersistSocietyRunReport("completed"), true);
  assert.equal(shouldPersistSocietyRunReport("awaiting_approval"), true);
  assert.equal(shouldPersistSocietyRunReport("analyzing"), false);
});
