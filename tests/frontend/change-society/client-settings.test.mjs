import assert from "node:assert/strict";
import test from "node:test";

import {
  buildDefaultClientSettings,
  normalizeClientSettings,
  validateClientSettings,
} from "../../../archives/hackathon/frontend/lib/client-settings.ts";

test("validateClientSettings checks LLM fields only", () => {
  const base = buildDefaultClientSettings();
  assert.equal(validateClientSettings(base).ok, true);
  assert.equal(validateClientSettings({...base, llmBaseUrl: ""}).ok, false);
  assert.equal(validateClientSettings({...base, llmModel: ""}).ok, false);
});

test("normalizeClientSettings keeps fixed workspace defaults", () => {
  const base = buildDefaultClientSettings();
  const mutated = {
    ...base,
    projectId: "custom",
    apiMode: "direct",
    llmModel: "qwen-turbo",
  };
  const out = normalizeClientSettings(mutated);
  assert.equal(out.projectId, base.projectId);
  assert.equal(out.apiMode, base.apiMode);
  assert.equal(out.llmModel, "qwen-turbo");
});
