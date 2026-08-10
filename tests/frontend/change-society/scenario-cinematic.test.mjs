import assert from "node:assert/strict";
import test from "node:test";

import {
  domainLabel,
  scenarioBeatCaption,
  scenarioBeatNarration,
} from "../../../archives/hackathon/frontend/lib/scenario-cinematic.ts";

test("domainLabel uses catalog labels and falls back to spaced ids", () => {
  assert.equal(domainLabel("software_engineering_api"), "Software engineering / API");
  assert.equal(domainLabel("custom_domain"), "custom domain");
});

test("scenarioBeatNarration returns scenario copy on request beat only", () => {
  const scenario = {
    scenario_id: "checkout-api-refactor",
    domain: "software_engineering_api",
    default_request: "Refactor checkout handler",
  };
  assert.ok(scenarioBeatNarration(scenario, "request")?.includes("checkout"));
  assert.equal(scenarioBeatNarration(scenario, "intro"), null);
  assert.equal(scenarioBeatNarration(null, "request"), null);
});

test("scenarioBeatCaption combines domain label and scenario id", () => {
  assert.equal(scenarioBeatCaption(null), "Demo scenario");
  assert.match(
    scenarioBeatCaption({scenario_id: "pricing-refactor", domain: "revenue_and_billing", default_request: "x"}),
    /Revenue & billing · pricing-refactor/,
  );
});
