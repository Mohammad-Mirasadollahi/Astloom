import assert from "node:assert/strict";
import test from "node:test";

import {
  parseRunDetailTab,
  runDetailTabHref,
} from "../../../archives/hackathon/frontend/lib/run-detail-tabs.ts";

test("parseRunDetailTab defaults to guide", () => {
  assert.equal(parseRunDetailTab(undefined), "guide");
  assert.equal(parseRunDetailTab("bogus"), "guide");
  assert.equal(parseRunDetailTab("metrics"), "reports");
});

test("runDetailTabHref encodes run id", () => {
  assert.match(runDetailTabHref("run_a b", "queue"), /run_a%20b/);
  assert.match(runDetailTabHref("run_x", "technical"), /tab=request/);
});

test("story tab is canonical and legacy flow alias resolves", () => {
  assert.equal(parseRunDetailTab("story"), "story");
  assert.equal(parseRunDetailTab("flow"), "story");
  assert.match(runDetailTabHref("run_1", "story"), /tab=story/);
});
