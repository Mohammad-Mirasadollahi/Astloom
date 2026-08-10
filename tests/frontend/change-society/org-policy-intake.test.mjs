import assert from "node:assert/strict";
import test from "node:test";

import {
  allChallengesResolved,
  defaultCandidateIds,
  firstPendingChallenge,
} from "../../../archives/hackathon/frontend/lib/org-policy-intake.ts";

const sampleSession = {
  intake_session_id: "intake_1",
  scenario_id: "checkout-api-refactor",
  state: "challenges_pending",
  requirements_digest: ["digest"],
  coverage_map: {},
  candidate_policies: [
    {candidate_id: "cand_api-breaking-change", policy_tag: "api-breaking-change", title: "API", policy_text: "t", source: "inferred", risk: "low", confidence: 0.9},
  ],
  challenges: [
    {
      challenge_id: "challenge_scope",
      sequence: 1,
      type: "scope",
      title: "Scope",
      summary: "s",
      linked_candidate_ids: ["cand_api-breaking-change"],
      options: [{option_id: "scope_project", label: "Project", outcome: "o"}],
      default_recommendation: "scope_project",
      resolved: false,
      resolution: null,
    },
  ],
};

test("firstPendingChallenge returns unresolved challenge", () => {
  assert.equal(firstPendingChallenge(sampleSession)?.challenge_id, "challenge_scope");
  assert.equal(firstPendingChallenge(null), null);
  assert.equal(
    firstPendingChallenge({...sampleSession, challenges: [{...sampleSession.challenges[0], resolved: true, resolution: {option_id: "scope_project"}}]}),
    null,
  );
});

test("allChallengesResolved reflects session state", () => {
  assert.equal(allChallengesResolved(sampleSession), false);
  assert.equal(allChallengesResolved({...sampleSession, challenges: []}), true);
  assert.equal(
    allChallengesResolved({...sampleSession, challenges: [{...sampleSession.challenges[0], resolved: true, resolution: {option_id: "scope_project"}}]}),
    true,
  );
});

test("defaultCandidateIds maps candidate policies", () => {
  assert.deepEqual(defaultCandidateIds(sampleSession), ["cand_api-breaking-change"]);
  assert.deepEqual(defaultCandidateIds(null), []);
});
