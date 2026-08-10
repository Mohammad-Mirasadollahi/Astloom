import assert from "node:assert/strict";
import test from "node:test";

import {formatMetricDisplayValue} from "../../../archives/hackathon/frontend/lib/metric-display.ts";

test("formatMetricDisplayValue treats unit fractions as percentages", () => {
  assert.equal(formatMetricDisplayValue(0.964), "96%");
  assert.equal(formatMetricDisplayValue(1), "100%");
});

test("formatMetricDisplayValue leaves larger numbers and empty as plain text", () => {
  assert.equal(formatMetricDisplayValue(0), "0");
  assert.equal(formatMetricDisplayValue(42), "42");
  assert.equal(formatMetricDisplayValue(undefined), "—");
  assert.equal(formatMetricDisplayValue("ok"), "ok");
});
