import assert from "node:assert/strict";
import test from "node:test";

import {parseApiError} from "../../../archives/hackathon/frontend/lib/api.ts";

test("parseApiError prefers structured API messages", () => {
  assert.equal(parseApiError({error: {message: "Run is stale"}}, 409), "Run is stale");
  assert.equal(parseApiError({}, 503), "Request failed with 503");
});
