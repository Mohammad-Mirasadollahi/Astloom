import assert from "node:assert/strict";
import test from "node:test";

import {
  parseBaselineEvaluation,
  pct,
  variantRows,
} from "../../../archives/hackathon/frontend/lib/evaluation-view.ts";

test("pct formats recall as percentage", () => {
  assert.equal(pct(0.9643), "96%");
  assert.equal(pct(undefined), "—");
});

test("variantRows prefers ablation variants when present", () => {
  const rows = variantRows({
    ablation: {
      variants: [
        {variant_id: "single_agent", label: "Single", metrics: {critical_impact_recall: 0.25}},
        {variant_id: "full_change_society", label: "Full", metrics: {critical_impact_recall: 1}},
      ],
    },
  });
  assert.equal(rows.length, 2);
  assert.equal(rows[1].variant_id, "full_change_society");
});

test("variantRows falls back to baseline vs society when ablation missing", () => {
  const rows = variantRows({
    baseline: {critical_impact_recall: 0.2},
    society: {critical_impact_recall: 0.9},
  });
  assert.equal(rows.length, 2);
  assert.equal(rows[0].variant_id, "single_agent");
  assert.equal(rows[1].metrics.critical_impact_recall, 0.9);
});

test("parseBaselineEvaluation passes through structured payload", () => {
  const payload = {scenario_id: "demo", society: {total_tokens: 100}};
  assert.deepEqual(parseBaselineEvaluation(payload), payload);
  assert.equal(parseBaselineEvaluation(null), null);
});
